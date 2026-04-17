"""
Docker basic example with a multi-turn chatbot.
"""
import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import uvicorn

from utils.multiturn_chat import MultiTurnMockChatbot
from utils.provider_wrapper import list_provider_configs
from utils.ui_assets import resolve_chat_ui

app = FastAPI(title="Agent Basic Docker", version="2.0.0")
START_TIME = time.time()
DEFAULT_PROVIDER = os.getenv("CHATBOT_DEFAULT_PROVIDER", "openai")
chatbot = MultiTurnMockChatbot(default_provider=DEFAULT_PROVIDER)
UI_FILE = resolve_chat_ui(__file__)


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
        "message": "Docker chatbot is running.",
        "default_provider": DEFAULT_PROVIDER,
        **chatbot.runtime_summary(),
        "available_providers": [provider["name"] for provider in list_provider_configs()],
        "endpoints": {
            "ui": "GET /ui",
            "api_info": "GET /api-info",
            "providers": "GET /providers",
            "create_session": "POST /sessions",
            "chat": "POST /chat",
            "session_detail": "GET /sessions/{session_id}",
            "delete_session": "DELETE /sessions/{session_id}",
            "health": "GET /health",
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
async def chat(body: ChatRequest):
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
async def ask_agent(body: ChatRequest):
    return await chat(body)


@app.get("/health")
def health():
    stats: dict[str, Any] = chatbot.stats()
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "container": True,
        **chatbot.runtime_summary(),
        **stats,
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app="app:app", host="0.0.0.0", port=port)
