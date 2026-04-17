"""
Provider registry for OpenAI-compatible backends.

Section 02 can run either in mock mode or against a real OpenAI-compatible
provider. The wrapper keeps provider selection explicit so the Docker demo can
switch between OpenAI, OpenRouter, and a custom endpoint.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI


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
        preview: dict[str, Any] = {
            "api_key": f'os.getenv("{self.api_key_env}")',
            "base_url": self.base_url,
            "model": f'os.getenv("{self.model_env}", "{self.default_model}")',
        }
        if self.default_headers:
            preview["default_headers"] = self.default_headers
        return preview

    def python_snippet(self) -> str:
        lines = [
            "from openai import OpenAI",
            "",
            "client = OpenAI(",
            f'    api_key=os.getenv("{self.api_key_env}"),',
            f'    base_url="{self.base_url}",',
        ]
        if self.default_headers:
            lines.append(f"    default_headers={self.default_headers!r},")
        lines.extend(
            [
                ")",
                "",
                "response = client.chat.completions.create(",
                f'    model=os.getenv("{self.model_env}", "{self.default_model}"),',
                '    messages=[{"role": "user", "content": "Hello"}],',
                ")",
            ]
        )
        return "\n".join(lines)

    def resolved_model(self) -> str:
        return os.getenv(self.model_env, self.default_model)

    def is_configured(self) -> bool:
        return bool(os.getenv(self.api_key_env))

    def build_client(self) -> OpenAI:
        kwargs: dict[str, Any] = {
            "api_key": os.getenv(self.api_key_env),
            "base_url": self.base_url,
        }
        if self.default_headers:
            kwargs["default_headers"] = self.default_headers
        return OpenAI(**kwargs)


_PROVIDER_REGISTRY = {
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
            "HTTP-Referer": "http://localhost:8080",
            "X-Title": "docker-multiturn-chatbot",
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
    if normalized not in _PROVIDER_REGISTRY:
        allowed = ", ".join(sorted(_PROVIDER_REGISTRY))
        raise ValueError(f"Unsupported provider '{name}'. Use one of: {allowed}")
    return _PROVIDER_REGISTRY[normalized]


def list_provider_configs() -> list[dict[str, Any]]:
    return [build_provider_payload(name) for name in _PROVIDER_REGISTRY]


def build_provider_payload(name: str | None) -> dict[str, Any]:
    config = get_provider_config(name)
    return {
        **config.public_dict(),
        "client_preview": config.client_preview(),
        "python_snippet": config.python_snippet(),
    }
