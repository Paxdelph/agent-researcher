"""Tests for CSV profiling and data-review heuristics."""

from __future__ import annotations

from pathlib import Path

from app.data_profile import profile_data_dir
from app.models import ChatAction, ResearchState, Stage, Status
from app.orchestration.chat import _heuristic_decision


def test_heuristic_build_skeleton_after_data():
    state = ResearchState(
        run_id="t",
        workspace="/tmp",
        stage=Stage.DATA_READY,
        status=Status.WAITING_FOR_USER,
        research_question="q",
        artifacts={"analysis_plan": "/tmp/p.md"},
    )
    d = _heuristic_decision(state, "едем дальше")
    assert d is not None
    assert d.action == ChatAction.BUILD_SKELETON


def test_profile_lists_columns(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "events.csv").write_text(
        "user_id,event_name\nu1,cart\nu2,purchase\n", encoding="utf-8"
    )
    md = profile_data_dir(data)
    assert "`events.csv`" in md
    assert "`user_id`" in md
    assert "Строк" in md


def test_heuristic_review_data():
    state = ResearchState(
        run_id="t",
        workspace="/tmp",
        stage=Stage.WAITING_FOR_DATA,
        status=Status.WAITING_FOR_USER,
        research_question="q",
        artifacts={"analysis_plan": "/tmp/analysis-plan.md"},
    )
    d = _heuristic_decision(state, "проверь данные, platform нет")
    assert d is not None
    assert d.action == ChatAction.REVIEW_DATA
