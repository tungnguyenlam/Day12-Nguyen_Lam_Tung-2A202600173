"""
Agent production-ready — dùng trong Docker production stack.
"""
import os
import time
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import uvicorn

from utils.multiturn_chat import MultiTurnMockChatbot
from utils.provider_wrapper import list_provider_configs
from utils.ui_assets import resolve_chat_ui

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
is_ready = False
DEFAULT_PROVIDER = os.getenv("CHATBOT_DEFAULT_PROVIDER", "custom")
chatbot = MultiTurnMockChatbot(default_provider=DEFAULT_PROVIDER)
UI_FILE = resolve_chat_ui(__file__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global is_ready
    logger.info("Starting agent...")
    time.sleep(0.1)  # simulate init
    is_ready = True
    logger.info("Agent ready")
    yield
    is_ready = False
    logger.info("Agent shutdown")


app = FastAPI(title="Agent (Docker Advanced)", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


class SessionCreateRequest(BaseModel):
    provider: str = Field(default=DEFAULT_PROVIDER)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(default=None)
    provider: str = Field(default=DEFAULT_PROVIDER)


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _not_found(entity: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{entity} not found")


@app.get("/", include_in_schema=False)
@app.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(UI_FILE, media_type="text/html")


@app.get("/api-info")
def root():
    return {
        "app": "AI Agent",
        "version": "2.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "default_provider": DEFAULT_PROVIDER,
        **chatbot.runtime_summary(),
        "available_providers": [
            provider["name"] for provider in list_provider_configs()
        ],
        "endpoints": {
            "ui": "GET /ui",
            "api_info": "GET /api-info",
            "providers": "GET /providers",
            "create_session": "POST /sessions",
            "chat": "POST /chat",
            "ask_alias": "POST /ask",
            "session_detail": "GET /sessions/{session_id}",
            "delete_session": "DELETE /sessions/{session_id}",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }


@app.get("/providers")
def providers():
    return {
        "default_provider": DEFAULT_PROVIDER,
        **chatbot.runtime_summary(),
        "providers": list_provider_configs(),
    }


@app.post("/sessions")
def create_session(body: SessionCreateRequest):
    try:
        return chatbot.create_session(provider=body.provider)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    try:
        return chatbot.get_session(session_id)
    except KeyError as exc:
        raise _not_found("session") from exc


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    try:
        chatbot.delete_session(session_id)
        return {"deleted": True, "session_id": session_id}
    except KeyError as exc:
        raise _not_found("session") from exc


@app.post("/chat")
async def chat(body: ChatRequest, request: Request):
    logger.info(
        json.dumps(
            {
                "event": "chat_request",
                "provider": body.provider,
                "session_id": body.session_id or "new",
                "q_len": len(body.question),
                "client": str(request.client.host) if request.client else "unknown",
            }
        )
    )
    try:
        return chatbot.chat(
            question=body.question,
            session_id=body.session_id,
            provider=body.provider,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except KeyError as exc:
        raise _not_found("session") from exc
    except ValueError as exc:
        raise _bad_request(exc) from exc


@app.post("/ask")
async def ask_agent(body: ChatRequest, request: Request):
    return await chat(body, request)


@app.get("/health")
def health():
    stats: dict[str, Any] = chatbot.stats()
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "version": "2.0.0",
        **chatbot.runtime_summary(),
        "providers": [provider["name"] for provider in list_provider_configs()],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **stats,
    }


@app.get("/ready")
def ready():
    if not is_ready:
        raise HTTPException(503, "not ready")
    return {"ready": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
