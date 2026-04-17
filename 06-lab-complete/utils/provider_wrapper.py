"""
Provider registry for OpenAI-compatible backends in Lab 06.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


CUSTOM_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    label: str
    api_key_env: str
    base_url: str
    default_model: str
    model_env: str
    default_headers: dict[str, str] = field(default_factory=dict)

    def resolved_model(self) -> str:
        return os.getenv(self.model_env, self.default_model)

    def is_configured(self) -> bool:
        return bool(os.getenv(self.api_key_env))

    def build_client(self):
        from openai import OpenAI

        kwargs: dict[str, Any] = {
            "api_key": os.getenv(self.api_key_env),
            "base_url": self.base_url,
        }
        if self.default_headers:
            kwargs["default_headers"] = self.default_headers
        return OpenAI(**kwargs)

    def public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "api_key_env": self.api_key_env,
            "base_url": self.base_url,
            "default_model": self.default_model,
            "model_env": self.model_env,
            "resolved_model": self.resolved_model(),
            "configured": self.is_configured(),
            "default_headers": self.default_headers,
        }

    def client_preview(self) -> dict[str, Any]:
        preview = {
            "api_key": f'os.getenv("{self.api_key_env}")',
            "base_url": self.base_url,
            "model": f'os.getenv("{self.model_env}", "{self.default_model}")',
        }
        if self.default_headers:
            preview["default_headers"] = self.default_headers
        return preview


_PROVIDERS = {
    "openai": ProviderConfig(
        name="openai",
        label="OpenAI",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        model_env="OPENAI_MODEL",
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        label="OpenRouter",
        api_key_env="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-4o-mini",
        model_env="OPENROUTER_MODEL",
        default_headers={
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "day12-final-agent",
        },
    ),
    "custom": ProviderConfig(
        name="custom",
        label="Custom Provider",
        api_key_env="SHOPAIKEY_API_KEY",
        base_url="https://api.shopaikey.com/v1",
        default_model="qwen3-coder-480b-a35b-instruct",
        model_env="CUSTOM_PROVIDER_MODEL",
        default_headers={"User-Agent": CUSTOM_USER_AGENT},
    ),
}


def get_provider_config(name: str | None) -> ProviderConfig:
    normalized = (name or "openai").strip().lower()
    if normalized not in _PROVIDERS:
        allowed = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"Unsupported provider '{name}'. Use one of: {allowed}")
    return _PROVIDERS[normalized]


def list_provider_configs() -> list[dict[str, Any]]:
    return [
        {
            **provider.public_dict(),
            "client_preview": provider.client_preview(),
        }
        for provider in _PROVIDERS.values()
    ]
