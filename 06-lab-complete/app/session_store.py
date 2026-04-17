"""Redis-backed session storage with optional in-memory fallback."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any


class SessionStore:
    def __init__(self, redis_url: str, allow_memory_fallback: bool, ttl_seconds: int):
        self.redis_url = redis_url
        self.allow_memory_fallback = allow_memory_fallback
        self.ttl_seconds = ttl_seconds
        self.backend = "uninitialized"
        self._last_error = ""
        self._redis = None
        self._memory: dict[str, dict[str, Any]] = {}

    def connect(self) -> None:
        self._last_error = ""
        if self.redis_url:
            try:
                import redis

                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                self._redis.ping()
                self.backend = "redis"
                return
            except Exception as exc:
                self._last_error = str(exc)
                self._redis = None

        if self.allow_memory_fallback:
            self.backend = "memory"
            return

        self.backend = "unavailable"

    def close(self) -> None:
        if self._redis is not None:
            try:
                self._redis.close()
            except Exception:
                pass

    def is_ready(self) -> bool:
        return self.backend in {"redis", "memory"}

    def health(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "ready": self.is_ready(),
            "last_error": self._last_error,
        }

    def stats(self) -> dict[str, Any]:
        if self.backend == "redis" and self._redis is not None:
            active_sessions = sum(1 for _ in self._redis.scan_iter(match="session:*"))
        else:
            active_sessions = len(self._memory)
        return {"backend": self.backend, "active_sessions": active_sessions}

    def create_session(self, provider: str) -> dict[str, Any]:
        if not self.is_ready():
            raise RuntimeError("Session store not ready")
        now = self._timestamp()
        session = {
            "session_id": uuid.uuid4().hex[:12],
            "provider": provider,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        self.save_session(session)
        return session

    def get_session(self, session_id: str) -> dict[str, Any]:
        if self.backend == "redis" and self._redis is not None:
            raw = self._redis.get(self._key(session_id))
            if not raw:
                raise KeyError(session_id)
            return json.loads(raw)
        session = self._memory.get(session_id)
        if not session:
            raise KeyError(session_id)
        return session.copy()

    def save_session(self, session: dict[str, Any]) -> None:
        session_id = session["session_id"]
        if self.backend == "redis" and self._redis is not None:
            self._redis.setex(self._key(session_id), self.ttl_seconds, json.dumps(session))
            return
        if self.backend == "memory":
            self._memory[session_id] = json.loads(json.dumps(session))
            return
        raise RuntimeError("Session store not ready")

    def delete_session(self, session_id: str) -> None:
        if self.backend == "redis" and self._redis is not None:
            deleted = self._redis.delete(self._key(session_id))
            if not deleted:
                raise KeyError(session_id)
            return
        if self.backend == "memory":
            if session_id not in self._memory:
                raise KeyError(session_id)
            del self._memory[session_id]
            return
        raise RuntimeError("Session store not ready")

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session:{session_id}"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
