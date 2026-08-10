"""Resolve max output tokens for provider API calls."""

from __future__ import annotations

# When config says 0 (no app-side cap), ask the provider for its practical ceiling.
_PROVIDER_CEILING: dict[str, int] = {
    "anthropic": 128_000,
    "openai": 128_000,
}


def resolve_max_output_tokens(provider: str, configured: int) -> int:
    """Map app config to provider API limit. 0 = no artificial cap."""
    if configured > 0:
        return configured
    return _PROVIDER_CEILING.get(provider.lower(), 128_000)
