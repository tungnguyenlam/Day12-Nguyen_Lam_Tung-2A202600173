"""
In-memory multi-turn chatbot used by the Docker examples.
"""
from __future__ import annotations

import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from utils.mock_llm import ask as mock_ask
from utils.provider_wrapper import (
    build_provider_payload,
    get_provider_config,
)


CONTEXT_HINTS = (
    "again",
    "before",
    "context",
    "earlier",
    "history",
    "last",
    "previous",
    "recap",
    "summary",
    "tom tat",
    "truoc",
)


DEFAULT_SYSTEM_PROMPT = (
    "You are a concise, helpful coding assistant for a Docker deployment lab. "
    "Answer directly, keep useful technical detail, and use the conversation "
    "history when the user asks follow-up questions."
)


class MultiTurnMockChatbot:
    def __init__(self, default_provider: str = "openai") -> None:
        self.default_provider = default_provider
        self.force_mock = self._as_bool(os.getenv("CHATBOT_MOCK_ONLY", "false"))
        self.allow_mock_fallback = self._as_bool(
            os.getenv("CHATBOT_ALLOW_MOCK_FALLBACK", "false")
        )
        self.temperature = float(os.getenv("CHATBOT_TEMPERATURE", "0.2"))
        self.system_prompt = os.getenv("CHATBOT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def create_session(self, provider: str | None = None) -> dict[str, Any]:
        config = get_provider_config(provider or self.default_provider)
        now = self._timestamp()
        session = {
            "session_id": uuid.uuid4().hex[:12],
            "provider": config.name,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        with self._lock:
            self._sessions[session["session_id"]] = session
        return self._session_payload(session)

    def get_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(session_id)
            return self._session_payload(session)

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(session_id)
            del self._sessions[session_id]

    def chat(
        self,
        question: str,
        session_id: str | None = None,
        provider: str | None = None,
    ) -> dict[str, Any]:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("question required")

        created_new_session = False

        with self._lock:
            if session_id:
                session = self._sessions.get(session_id)
                if not session:
                    raise KeyError(session_id)
            else:
                created_new_session = True
                session = {
                    "session_id": uuid.uuid4().hex[:12],
                    "provider": self.default_provider,
                    "created_at": self._timestamp(),
                    "updated_at": self._timestamp(),
                    "messages": [],
                }
                self._sessions[session["session_id"]] = session

            config = get_provider_config(provider or session["provider"] or self.default_provider)
            session["provider"] = config.name
            existing_messages = deepcopy(session["messages"])

        answer, model_name, used_mock, mode_reason = self._compose_answer(
            question=cleaned_question,
            previous_messages=existing_messages,
            provider_name=config.name,
        )

        now = self._timestamp()
        user_message = {
            "role": "user",
            "content": cleaned_question,
            "timestamp": now,
        }
        assistant_message = {
            "role": "assistant",
            "content": answer,
            "timestamp": now,
            "model": model_name,
        }

        with self._lock:
            current_session = self._sessions.get(session["session_id"])
            if not current_session:
                raise KeyError(session["session_id"])
            current_session["provider"] = config.name
            current_session["messages"].extend([user_message, assistant_message])
            current_session["updated_at"] = now
            return self._chat_payload(
                current_session,
                answer,
                created_new_session,
                model_name,
                used_mock,
                mode_reason,
            )

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "active_sessions": len(self._sessions),
                "total_messages": sum(
                    len(session["messages"]) for session in self._sessions.values()
                ),
            }

    def _compose_answer(
        self,
        question: str,
        previous_messages: list[dict[str, Any]],
        provider_name: str,
    ) -> tuple[str, str, bool, str]:
        config = get_provider_config(provider_name)
        if self.force_mock:
            return self._mock_response(question, previous_messages, config.name, "forced_mock")

        if not config.is_configured():
            return self._mock_response(
                question,
                previous_messages,
                config.name,
                "missing_api_key",
            )

        try:
            return self._live_response(question, previous_messages, config.name)
        except Exception as exc:
            if self.allow_mock_fallback:
                return self._mock_response(
                    question,
                    previous_messages,
                    config.name,
                    f"live_error_fallback:{exc.__class__.__name__}",
                )
            raise RuntimeError(
                f"Live provider call failed for {config.name}: {exc}"
            ) from exc

    def _live_response(
        self,
        question: str,
        previous_messages: list[dict[str, Any]],
        provider_name: str,
    ) -> tuple[str, str, bool, str]:
        config = get_provider_config(provider_name)
        client = config.build_client()
        response = client.chat.completions.create(
            model=config.resolved_model(),
            messages=self._build_live_messages(previous_messages, question),
            temperature=self.temperature,
        )
        answer = self._extract_text(response.choices[0].message.content).strip()
        if not answer:
            raise RuntimeError("provider returned empty content")
        response_model = getattr(response, "model", None) or config.resolved_model()
        return answer, response_model, False, "live"

    def _mock_response(
        self,
        question: str,
        previous_messages: list[dict[str, Any]],
        provider_name: str,
        mode_reason: str,
    ) -> tuple[str, str, bool, str]:
        config = get_provider_config(provider_name)
        previous_user_questions = [
            message["content"]
            for message in previous_messages
            if message["role"] == "user"
        ]

        base_answer = mock_ask(question, delay=0.03)

        if not previous_user_questions:
            context_line = "This is the first turn in a new session."
        elif self._looks_like_context_question(question):
            recent_questions = "; ".join(
                f'"{self._shorten(item)}"' for item in previous_user_questions[-3:]
            )
            context_line = (
                f"I remember {len(previous_user_questions)} earlier user turns: "
                f"{recent_questions}."
            )
        else:
            context_line = (
                f"I still remember {len(previous_user_questions)} earlier user turns. "
                f'The latest question was "{self._shorten(previous_user_questions[-1])}".'
            )

        provider_line = (
            f"Provider wrapper selected {config.name} "
            f"({config.base_url}) with mock model {config.default_model}. "
            "No external API call was made."
        )

        return (
            f"{base_answer} {context_line} {provider_line}",
            f"mock::{config.resolved_model()}",
            True,
            mode_reason,
        )

    def _session_payload(self, session: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_id": session["session_id"],
            "provider": session["provider"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "turn_count": self._assistant_turns(session["messages"]),
            "message_count": len(session["messages"]),
            "messages": deepcopy(session["messages"][-8:]),
        }

    def _chat_payload(
        self,
        session: dict[str, Any],
        answer: str,
        created_new_session: bool,
        model_name: str,
        used_mock: bool,
        mode_reason: str,
    ) -> dict[str, Any]:
        provider_payload = build_provider_payload(session["provider"])
        return {
            "session_id": session["session_id"],
            "created_new_session": created_new_session,
            "provider": session["provider"],
            "model": model_name,
            "turn": self._assistant_turns(session["messages"]),
            "answer": answer,
            "mock_only": used_mock,
            "mode": "mock" if used_mock else "live",
            "mode_reason": mode_reason,
            "provider_details": provider_payload,
            "messages": deepcopy(session["messages"][-8:]),
            "timestamp": self._timestamp(),
        }

    def runtime_summary(self) -> dict[str, Any]:
        default_config = get_provider_config(self.default_provider)
        return {
            "force_mock": self.force_mock,
            "allow_mock_fallback": self.allow_mock_fallback,
            "default_provider": self.default_provider,
            "default_provider_configured": default_config.is_configured(),
            "default_provider_model": default_config.resolved_model(),
        }

    def _build_live_messages(
        self,
        previous_messages: list[dict[str, Any]],
        question: str,
    ) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": self.system_prompt}]
        for message in previous_messages[-12:]:
            role = message.get("role")
            content = message.get("content", "")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": question})
        return messages

    @staticmethod
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

    @staticmethod
    def _assistant_turns(messages: list[dict[str, Any]]) -> int:
        return sum(1 for message in messages if message["role"] == "assistant")

    @staticmethod
    def _looks_like_context_question(question: str) -> bool:
        question_lower = question.lower()
        return any(hint in question_lower for hint in CONTEXT_HINTS)

    @staticmethod
    def _shorten(text: str, max_length: int = 80) -> str:
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    @staticmethod
    def _as_bool(value: str | bool) -> bool:
        if isinstance(value, bool):
            return value
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
