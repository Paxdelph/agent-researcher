"""Validate Coder output before writing report.qmd."""

from __future__ import annotations

import re

from app.models import AgentConfig, LLMResult

MIN_QMD_CHARS = 500


class QmdValidationError(ValueError):
    """report.qmd from the model failed sanity checks."""


def _fence_balance_errors(qmd: str) -> list[str]:
    r_opens = len(re.findall(r"^```\{r", qmd, flags=re.MULTILINE))
    if r_opens == 0:
        return []
    closes = len(re.findall(r"^```\s*$", qmd, flags=re.MULTILINE))
    if closes < r_opens:
        return ["незакрытый R-чанк ```{r} (ответ, вероятно, обрезан)"]
    return []


def validate_qmd_text(qmd: str) -> list[str]:
    """Return human-readable validation errors; empty list = OK."""
    text = qmd.strip()
    errors: list[str] = []
    if len(text) < MIN_QMD_CHARS:
        errors.append(f"report.qmd слишком короткий ({len(text)} символов)")
    if not text.startswith("---"):
        errors.append("нет YAML front matter (---)")
    if "```{r" not in text:
        errors.append("нет R-чанков ```{r}")
    if "format:" not in text[:800]:
        errors.append("нет format в YAML front matter")
    errors.extend(_fence_balance_errors(text))
    return errors


def output_truncated(result: LLMResult, agent: AgentConfig) -> bool:
    """True only when an explicit app-side cap was hit."""
    limit = agent.max_output_tokens
    if limit <= 0:
        return False
    return result.output_tokens >= limit - 32


def validate_coder_result(result: LLMResult, qmd: str, agent: AgentConfig) -> None:
    """Raise QmdValidationError if the Coder response must not be written."""
    errors: list[str] = []
    if not result.text.strip():
        errors.append("модель вернула пустой текст")
    if output_truncated(result, agent):
        errors.append(
            f"ответ обрезан по лимиту max_output_tokens={agent.max_output_tokens} "
            f"(output_tokens={result.output_tokens})"
        )
    errors.extend(validate_qmd_text(qmd))
    if errors:
        raise QmdValidationError("; ".join(errors))
