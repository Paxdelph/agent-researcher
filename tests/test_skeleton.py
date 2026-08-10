"""Skeleton pipeline smoke test (no LLM)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.models import LLMResult, ResearchState, Stage, Status
from app.orchestration.skeleton import approve_skeleton, run_skeleton


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
async def test_run_skeleton_writes_file(tmp_path: Path):
    (tmp_path / "analysis-plan.md").write_text("# Plan\n", encoding="utf-8")
    (tmp_path / "data-review.md").write_text("# Review\n", encoding="utf-8")
    state = ResearchState(
        run_id="r1",
        workspace=str(tmp_path),
        stage=Stage.DATA_READY,
        status=Status.WAITING_FOR_USER,
        research_question="Где теряем в воронке?",
    )

    calls: list[str] = []

    async def fake_run_agent(**kwargs):
        calls.append(kwargs["agent_name"])
        name = kwargs["agent_name"]
        if name == "analyst":
            return _result("Слишком рано сегменты")
        if name == "storyteller":
            return _result("# Story skeleton\n\n## Narrative arc\nОт общего к частному.\n")
        if name == "bi_analyst":
            return _result(
                "# Story skeleton\n\n## Narrative arc\nОт общего к частному.\n\n"
                "### 1. Общая картина\n- **Графики / таблицы:** grouped bars, шаг × CR\n"
            )
        return _result("# Draft skeleton\n\n## Narrative arc\nЧерновик.\n")

    with (
        patch("app.orchestration.skeleton.run_agent", new=AsyncMock(side_effect=fake_run_agent)),
        patch("app.orchestration.skeleton.get_settings") as gs,
        patch("app.orchestration.skeleton.brief_block", return_value="RQ: test"),
    ):
        class R:
            plan_file = "analysis-plan.md"
            data_review_file = "data-review.md"
            skeleton_file = "skeleton.md"

        class W:
            path = str(tmp_path)
            data_dir = "data"
            context_path = str(tmp_path / "company-context.md")

        class S:
            research = R()
            workspace = W()

        gs.return_value = S()
        state = await run_skeleton(state, tmp_path)

    assert state.stage == Stage.SKELETON_READY
    assert (tmp_path / "skeleton.md").exists()
    assert "Story skeleton" in (tmp_path / "skeleton.md").read_text(encoding="utf-8")
    assert calls == ["lead", "analyst", "lead", "storyteller", "bi_analyst"]

    state = approve_skeleton(state)
    assert state.stage == Stage.SKELETON_APPROVED
