"""Provider registry."""

from __future__ import annotations

from app.config import get_settings
from app.providers.anthropic import AnthropicProvider
from app.providers.base import LLMProvider
from app.providers.openai import OpenAIProvider

_providers: dict[str, LLMProvider] = {}


def get_provider(name: str) -> LLMProvider:
    key = name.lower()
    if key in _providers:
        return _providers[key]
    settings = get_settings()
    timeout = float(settings.limits.default_timeout_seconds)
    if key == "openai":
        provider: LLMProvider = OpenAIProvider(timeout=timeout)
    elif key == "anthropic":
        provider = AnthropicProvider(timeout=timeout)
    else:
        raise ValueError(f"Unknown provider: {name}")
    _providers[key] = provider
    return provider


def reset_providers() -> None:
    _providers.clear()
