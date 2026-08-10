"""Unit tests for chat heuristics and JSON parsing (no LLM)."""

from __future__ import annotations

from app.models import ChatAction, ResearchState, Stage, Status
from app.orchestration.chat import _heuristic_decision
from app.orchestration.parse import parse_chat_decision, strip_markdown_fence


def _state(**kwargs) -> ResearchState:
    base = dict(
        run_id="test",
        workspace="/tmp",
        stage=Stage.PLAN_READY,
        status=Status.WAITING_FOR_USER,
        research_question="Почему падает конверсия?",
        artifacts={"analysis_plan": "/tmp/analysis-plan.md"},
    )
    base.update(kwargs)
    return ResearchState.model_validate(base)


def test_heuristic_advance():
    d = _heuristic_decision(_state(), "едем дальше")
    assert d is not None
    assert d.action == ChatAction.ADVANCE


def test_heuristic_start_planning():
    d = _heuristic_decision(
        _state(stage=Stage.BRIEF, artifacts={}),
        "сделай план",
    )
    assert d is not None
    assert d.action == ChatAction.START_PLANNING


def test_heuristic_edit_falls_through():
    d = _heuristic_decision(_state(), "добавь сегмент платформы в раздел 6")
    assert d is None


def test_parse_chat_decision():
    raw = '{"action":"clarify","reply":"Что именно поправить?","artifact":null}'
    d = parse_chat_decision(raw)
    assert d.action == ChatAction.CLARIFY
    assert "поправить" in d.reply


def test_strip_fence():
    text = "```markdown\n# Plan\n\nHi\n```"
    assert strip_markdown_fence(text).startswith("# Plan")
