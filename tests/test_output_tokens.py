"""output token resolution tests."""

from app.providers.output_tokens import resolve_max_output_tokens


def test_zero_means_provider_ceiling():
    assert resolve_max_output_tokens("anthropic", 0) == 128_000
    assert resolve_max_output_tokens("openai", 0) == 128_000


def test_explicit_cap_preserved():
    assert resolve_max_output_tokens("anthropic", 8000) == 8000
