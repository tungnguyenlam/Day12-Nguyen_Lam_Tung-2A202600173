"""
Production AI Agent — final Day 12 deliverable.

Combines:
  - API key authentication
  - Rate limiting
  - Monthly cost guard
  - Multi-turn session chat
  - Redis-backed stateless session storage
  - Provider selection (OpenAI / OpenRouter / custom)
  - Basic browser UI
  - Health, readiness, metrics, and graceful shutdown
"""
from __future__ import annotations

import json
import logging
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import uvicorn

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import CostGuard
from app.rate_limiter import RateLimiter
from app.session_store import SessionStore
from utils.mock_llm import ask as mock_ask
from utils.provider_wrapper import get_provider_config, list_provider_configs
from utils.ui_assets import resolve_chat_ui


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
UI_FILE = resolve_chat_ui(__file__)

rate_limiter = RateLimiter(
    max_requests=settings.rate_limit_per_minute,
    window_seconds=60,
)
cost_guard = CostGuard(monthly_budget_usd=settings.monthly_budget_usd)
session_store = SessionStore(
    redis_url=settings.redis_url,
    allow_memory_fallback=settings.allow_in_memory_sessions,
    ttl_seconds=settings.session_ttl_seconds,
)

_is_ready = False
_request_count = 0
_error_count = 0


class SessionCreateRequest(BaseModel):
    provider: str = Field(default_factory=lambda: settings.chatbot_default_provider)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(default=None)
    provider: str = Field(default_factory=lambda: settings.chatbot_default_provider)


class AskResponse(BaseModel):
    session_id: str
    provider: str
    model: str
    answer: str
    turn: int
    mode: str
    mode_reason: str
    storage: str
    timestamp: str


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _not_found(entity: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{entity} not found")


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()) * 2)


def _validate_provider(name: str | None) -> str:
    provider = get_provider_config(name)
    return provider.name


def _context_sentence(previous_messages: list[dict[str, Any]]) -> str:
    previous_user_questions = [
        message["content"]
        for message in previous_messages
        if message.get("role") == "user"
    ]
    if not previous_user_questions:
        return "This is the first turn in the session."
    return (
        f'I remember {len(previous_user_questions)} earlier user turns. '
        f'Latest previous question: "{_shorten(previous_user_questions[-1])}".'
    )


def _mock_response(
    question: str,
    previous_messages: list[dict[str, Any]],
    provider_name: str,
    mode_reason: str,
) -> tuple[str, str, bool, str]:
    provider = get_provider_config(provider_name)
    answer = mock_ask(question, delay=0.03)
    answer = (
        f"{answer} {_context_sentence(previous_messages)} "
        f"Provider wrapper selected {provider.name} "
        f"({provider.base_url}) with mock model {provider.resolved_model()}."
    )
    return answer, f"mock::{provider.resolved_model()}", True, mode_reason


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content or "")


def _build_live_messages(
    previous_messages: list[dict[str, Any]],
    question: str,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": settings.chatbot_system_prompt}]
    for message in previous_messages[-12:]:
        role = message.get("role")
        content = message.get("content", "")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})
    return messages


def generate_answer(
    question: str,
    previous_messages: list[dict[str, Any]],
    provider_name: str,
) -> tuple[str, str, bool, str]:
    provider = get_provider_config(provider_name)

    if settings.chatbot_mock_only:
        return _mock_response(question, previous_messages, provider.name, "forced_mock")

    if not provider.is_configured():
        return _mock_response(question, previous_messages, provider.name, "missing_api_key")

    try:
        client = provider.build_client()
        response = client.chat.completions.create(
            model=provider.resolved_model(),
            messages=_build_live_messages(previous_messages, question),
            temperature=settings.chatbot_temperature,
        )
        answer = _extract_text(response.choices[0].message.content).strip()
        if not answer:
            raise RuntimeError("provider returned empty content")
        model_name = getattr(response, "model", None) or provider.resolved_model()
        return answer, model_name, False, "live"
    except Exception as exc:
        if settings.chatbot_allow_mock_fallback:
            return _mock_response(
                question,
                previous_messages,
                provider.name,
                f"live_error_fallback:{exc.__class__.__name__}",
            )
        raise RuntimeError(f"Live provider call failed for {provider.name}: {exc}") from exc


def _session_payload(session: dict[str, Any]) -> dict[str, Any]:
    messages = session.get("messages", [])
    return {
        "session_id": session["session_id"],
        "provider": session["provider"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "turn_count": sum(1 for message in messages if message.get("role") == "assistant"),
        "message_count": len(messages),
        "messages": messages[-8:],
    }


def _shorten(text: str, max_length: int = 80) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready

    logger.info(
        json.dumps(
            {
                "event": "startup",
                "app": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment,
            }
        )
    )
    session_store.connect()
    _is_ready = session_store.is_ready()
    if _is_ready:
        logger.info(json.dumps({"event": "ready", "backend": session_store.backend}))
    else:
        logger.error(json.dumps({"event": "not_ready", "backend": session_store.backend}))

    yield

    _is_ready = False
    session_store.close()
    logger.info(json.dumps({"event": "shutdown"}))


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count

    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
    except Exception:
        _error_count += 1
        raise

    duration_ms = round((time.time() - start) * 1000, 1)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers.pop("server", None)
    logger.info(
        json.dumps(
            {
                "event": "request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": duration_ms,
            }
        )
    )
    return response


@app.get("/", include_in_schema=False)
@app.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(UI_FILE, media_type="text/html")


@app.get("/api-info", tags=["Info"])
def api_info():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "default_provider": settings.chatbot_default_provider,
        "providers": [provider["name"] for provider in list_provider_configs()],
        "storage": session_store.health(),
        "endpoints": {
            "ui": "GET /ui",
            "chat": "POST /chat",
            "ask_alias": "POST /ask",
            "providers": "GET /providers",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }


@app.get("/providers", tags=["Info"])
def providers():
    return {
        "default_provider": settings.chatbot_default_provider,
        "mock_only": settings.chatbot_mock_only,
        "allow_mock_fallback": settings.chatbot_allow_mock_fallback,
        "providers": list_provider_configs(),
    }


@app.post("/sessions", tags=["Agent"])
def create_session(
    body: SessionCreateRequest,
    _key: str = Depends(verify_api_key),
):
    try:
        provider_name = _validate_provider(body.provider)
        return _session_payload(session_store.create_session(provider_name))
    except ValueError as exc:
        raise _bad_request(exc) from exc


@app.get("/sessions/{session_id}", tags=["Agent"])
def get_session(
    session_id: str,
    _key: str = Depends(verify_api_key),
):
    try:
        return _session_payload(session_store.get_session(session_id))
    except KeyError as exc:
        raise _not_found("session") from exc


@app.delete("/sessions/{session_id}", tags=["Agent"])
def delete_session(
    session_id: str,
    _key: str = Depends(verify_api_key),
):
    try:
        session_store.delete_session(session_id)
        return {"deleted": True, "session_id": session_id}
    except KeyError as exc:
        raise _not_found("session") from exc


@app.post("/chat", response_model=AskResponse, tags=["Agent"])
async def chat(
    body: ChatRequest,
    request: Request,
    api_key: str = Depends(verify_api_key),
):
    if not session_store.is_ready():
        raise HTTPException(status_code=503, detail="Session store not ready")

    rate_limiter.check(api_key)
    cost_guard.check_budget("service")

    created_new_session = False
    if body.session_id:
        try:
            session = session_store.get_session(body.session_id)
        except KeyError as exc:
            raise _not_found("session") from exc
    else:
        session = session_store.create_session(body.provider)
        created_new_session = True

    try:
        provider_name = _validate_provider(
            body.provider or session.get("provider") or settings.chatbot_default_provider
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    previous_messages = session.get("messages", [])

    logger.info(
        json.dumps(
            {
                "event": "chat_request",
                "provider": provider_name,
                "session_id": session["session_id"],
                "created_new_session": created_new_session,
                "q_len": len(body.question),
                "client": str(request.client.host) if request.client else "unknown",
            }
        )
    )

    try:
        answer, model_name, used_mock, mode_reason = generate_answer(
            body.question,
            previous_messages,
            provider_name,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    input_tokens = _estimate_tokens(body.question)
    output_tokens = _estimate_tokens(answer)
    usage = cost_guard.record_usage("service", input_tokens, output_tokens)

    now = datetime.now(timezone.utc).isoformat()
    session["provider"] = provider_name
    session["updated_at"] = now
    session.setdefault("messages", [])
    session["messages"].extend(
        [
            {"role": "user", "content": body.question, "timestamp": now},
            {
                "role": "assistant",
                "content": answer,
                "timestamp": now,
                "model": model_name,
                "mode": "mock" if used_mock else "live",
            },
        ]
    )
    session["messages"] = session["messages"][-20:]
    session_store.save_session(session)

    turn = sum(1 for message in session["messages"] if message.get("role") == "assistant")
    return AskResponse(
        session_id=session["session_id"],
        provider=provider_name,
        model=model_name,
        answer=answer,
        turn=turn,
        mode="mock" if used_mock else "live",
        mode_reason=mode_reason,
        storage=session_store.backend,
        timestamp=now,
    )


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: ChatRequest,
    request: Request,
    api_key: str = Depends(verify_api_key),
):
    return await chat(body, request, api_key)


@app.get("/health", tags=["Operations"])
def health():
    session_health = session_store.health()
    provider = get_provider_config(settings.chatbot_default_provider)
    status = "ok" if session_health["ready"] else "degraded"
    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": {
            "session_store": session_health,
            "default_provider": settings.chatbot_default_provider,
            "default_provider_configured": provider.is_configured(),
            "mock_only": settings.chatbot_mock_only,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready or not session_store.is_ready():
        raise HTTPException(status_code=503, detail="Not ready")
    return {"ready": True, "storage": session_store.backend}


@app.get("/metrics", tags=["Operations"])
def metrics(_key: str = Depends(verify_api_key)):
    usage = cost_guard.get_global_usage()
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "storage": session_store.stats(),
        "budget": usage,
    }


def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"API Key prefix: {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
