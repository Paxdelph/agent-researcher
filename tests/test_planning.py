"""Smoke test for Lead → Analyst → Lead planning without real LLM."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.models import LLMResult, ResearchState, Stage, Status
from app.orchestration.planning import approve_plan, run_planning


def _result(text: str) -> LLMResult:
    return LLMResult(
        text=text,
        provider="mock",
        model="mock",
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
        latency_ms=1,
    )


@pytest.mark.asyncio
async def test_run_planning_writes_plan(tmp_path: Path):
    state = ResearchState(
        run_id="r1",
        workspace=str(tmp_path),
        stage=Stage.BRIEF,
        status=Status.IDLE,
        research_question="Где теряем конверсию в checkout?",
        business_context="Мобильный трафик вырос",
    )

    calls: list[str] = []

    async def fake_run_agent(**kwargs):
        calls.append(kwargs["agent_name"] + ":" + (kwargs.get("summary") or ""))
        name = kwargs["agent_name"]
        if name == "lead" and "черновик" in (kwargs.get("summary") or ""):
            return _result("## Черновик\nГипотеза A")
        if name == "analyst":
            return _result("Слабая единица анализа")
        return _result("# Analysis Plan\n\n## 1. Центральный исследовательский вопрос\n\nГде теряем?\n")

    with (
        patch("app.orchestration.planning.run_agent", new=AsyncMock(side_effect=fake_run_agent)),
        patch("app.orchestration.planning.get_settings") as gs,
        patch(
            "app.orchestration.planning.company_context_path",
            return_value=tmp_path / "missing-company-context.md",
        ),
    ):
        class R:
            plan_file = "analysis-plan.md"

        class S:
            research = R()

        gs.return_value = S()

        state = await run_planning(state, tmp_path)

    assert state.stage == Stage.PLAN_READY
    assert (tmp_path / "analysis-plan.md").exists()
    assert "Где теряем" in (tmp_path / "analysis-plan.md").read_text(encoding="utf-8")
    assert calls[0].startswith("lead:")
    assert calls[1].startswith("analyst:")
    assert calls[2].startswith("lead:")

    state = approve_plan(state)
    assert state.stage == Stage.WAITING_FOR_DATA


def test_brief_block_reads_company_context(tmp_path: Path, monkeypatch):
    company = tmp_path / "shared" / "context.md"
    company.parent.mkdir(parents=True)
    company.write_text("Shared product facts\n", encoding="utf-8")
    workspace = tmp_path / "research"
    workspace.mkdir()
    (workspace / "context.md").write_text("WRONG local context\n", encoding="utf-8")

    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CONTEXT_PATH", str(company))
    from app.config import clear_settings_cache
    from app.orchestration.planning import brief_block

    clear_settings_cache()
    state = ResearchState(
        run_id="t",
        workspace=str(workspace),
        stage=Stage.BRIEF,
        status=Status.IDLE,
        research_question="RQ?",
        business_context="biz",
    )
    text = brief_block(state, workspace)
    assert "Shared product facts" in text
    assert "WRONG local context" not in text
    assert str(company) in text
