"""Production config — 12-Factor via environment variables."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: _as_bool(os.getenv("DEBUG", "false")))

    # App
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Production AI Agent"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "2.0.0"))
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            item.strip()
            for item in os.getenv("ALLOWED_ORIGINS", "*").split(",")
            if item.strip()
        ]
    )

    # Authentication
    agent_api_key: str = field(
        default_factory=lambda: os.getenv("AGENT_API_KEY", "dev-key-change-me")
    )

    # Session storage
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://redis:6379/0"))
    allow_in_memory_sessions: bool = field(
        default_factory=lambda: _as_bool(os.getenv("ALLOW_IN_MEMORY_SESSIONS", "false"))
    )
    session_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("SESSION_TTL_SECONDS", "86400"))
    )

    # Provider selection
    chatbot_default_provider: str = field(
        default_factory=lambda: os.getenv("CHATBOT_DEFAULT_PROVIDER", "custom")
    )
    chatbot_mock_only: bool = field(
        default_factory=lambda: _as_bool(os.getenv("CHATBOT_MOCK_ONLY", "false"))
    )
    chatbot_allow_mock_fallback: bool = field(
        default_factory=lambda: _as_bool(os.getenv("CHATBOT_ALLOW_MOCK_FALLBACK", "false"))
    )
    chatbot_temperature: float = field(
        default_factory=lambda: float(os.getenv("CHATBOT_TEMPERATURE", "0.2"))
    )
    chatbot_system_prompt: str = field(
        default_factory=lambda: os.getenv(
            "CHATBOT_SYSTEM_PROMPT",
            "You are a concise, helpful coding assistant for the Day 12 deployment lab.",
        )
    )

    # Provider credentials and models
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_model: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    )
    shopaikey_api_key: str = field(default_factory=lambda: os.getenv("SHOPAIKEY_API_KEY", ""))
    custom_provider_model: str = field(
        default_factory=lambda: os.getenv(
            "CUSTOM_PROVIDER_MODEL",
            "qwen3-coder-480b-a35b-instruct",
        )
    )

    # Rate limit and budget
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    )
    monthly_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("MONTHLY_BUDGET_USD", "10.0"))
    )

    def validate(self) -> "Settings":
        logger = logging.getLogger(__name__)
        allowed_providers = {"openai", "openrouter", "custom"}

        if self.environment == "production" and self.agent_api_key == "dev-key-change-me":
            raise ValueError("AGENT_API_KEY must be set in production")

        if self.rate_limit_per_minute <= 0:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be > 0")

        if self.monthly_budget_usd <= 0:
            raise ValueError("MONTHLY_BUDGET_USD must be > 0")

        if self.chatbot_default_provider not in allowed_providers:
            raise ValueError(
                "CHATBOT_DEFAULT_PROVIDER must be one of: "
                + ", ".join(sorted(allowed_providers))
            )

        configured = {
            "openai": bool(self.openai_api_key),
            "openrouter": bool(self.openrouter_api_key),
            "custom": bool(self.shopaikey_api_key),
        }

        if not configured.get(self.chatbot_default_provider, False) and not self.chatbot_mock_only:
            logger.warning(
                "Default provider %s has no API key configured. Live calls will fail unless mock fallback is enabled.",
                self.chatbot_default_provider,
            )

        if not self.redis_url and not self.allow_in_memory_sessions:
            logger.warning("REDIS_URL missing and in-memory fallback disabled")

        return self


settings = Settings().validate()
