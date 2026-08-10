"""qmd validation tests."""

from __future__ import annotations

import pytest

from app.models import AgentConfig, LLMResult
from app.orchestration.qmd_validate import (
    QmdValidationError,
    output_truncated,
    validate_coder_result,
    validate_qmd_text,
)


def _result(text: str, output_tokens: int = 100) -> LLMResult:
    return LLMResult(
        text=text,
        provider="mock",
        model="mock",
        input_tokens=1,
        output_tokens=output_tokens,
        total_tokens=output_tokens + 1,
        latency_ms=1,
    )


def _agent(limit: int = 8000) -> AgentConfig:
    return AgentConfig(provider="anthropic", model="m", prompt="p", max_output_tokens=limit)


def test_validate_qmd_rejects_empty():
    errors = validate_qmd_text("\n")
    assert any("слишком короткий" in e for e in errors)


def test_validate_qmd_accepts_minimal_complete():
    body = "# Hi\n\n```{r}\n1+1\n```\n" + ("x" * 450)
    qmd = f"""---
title: T
format:
  researcher-html: default
---

{body}"""
    assert validate_qmd_text(qmd) == []


def test_output_truncated_only_with_explicit_cap():
    agent = _agent(8000)
    assert output_truncated(_result("x", 8000), agent)
    assert not output_truncated(_result("x", 8000), _agent(0))


def test_validate_coder_result_raises_on_truncation():
    qmd = "x" * 600  # passes length but no structure
    with pytest.raises(QmdValidationError, match="обрезан"):
        validate_coder_result(_result(qmd, 8000), qmd, _agent(8000))


def test_validate_coder_result_raises_on_empty():
    with pytest.raises(QmdValidationError, match="пустой"):
        validate_coder_result(_result("", 10), "", _agent())
