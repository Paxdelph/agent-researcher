"""Coding pipeline tests (mocked agents / render)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.models import LLMResult, ResearchState, Stage, Status
from app.orchestration.coding import approve_coding, run_coding
from app.orchestration.parse import extract_qmd


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


def test_extract_qmd_keeps_inner_chunks():
    raw = """```qmd
---
title: T
---

```{r}
1+1
```
```"""
    out = extract_qmd(raw)
    assert "```{r}" in out
    assert out.strip().startswith("---")


@pytest.mark.asyncio
async def test_run_coding_pipeline(tmp_path: Path):
    (tmp_path / "skeleton.md").write_text("# Skel\n", encoding="utf-8")
    (tmp_path / "analysis-plan.md").write_text("# Plan\n", encoding="utf-8")
    (tmp_path / "data-review.md").write_text("# Review\n", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "events.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    state = ResearchState(
        run_id="r1",
        workspace=str(tmp_path),
        stage=Stage.SKELETON_APPROVED,
        status=Status.WAITING_FOR_USER,
        research_question="Где теряем?",
    )

    qmd = """---
title: Test
format: html
---

# Hi

```{r}
1
```
"""

    calls: list[str] = []

    async def fake_run_agent(**kwargs):
        calls.append(kwargs["agent_name"])
        if kwargs["agent_name"] == "coder":
            return _result(qmd)
        return _result(
            '{"verdict":"revise","issues":["график прилип"],"notes":"нужен воздух"}'
            if len([c for c in calls if c == "designer"]) == 1
            else '{"verdict":"approve","issues":[],"notes":"ок"}'
        )

    def fake_render(workspace, qmd_file, html_file):
        path = workspace / html_file
        path.write_text("<html><body>ok</body></html>", encoding="utf-8")
        return path

    with (
        patch("app.orchestration.coding.run_agent", new=AsyncMock(side_effect=fake_run_agent)),
        patch("app.orchestration.coding.render_quarto", side_effect=fake_render),
        patch("app.orchestration.coding.report_data_warnings", return_value=[]),
        patch("app.orchestration.coding.screenshot_html", return_value=[]),
        patch("app.orchestration.coding.get_settings") as gs,
        patch("app.orchestration.coding.brief_block", return_value="RQ"),
    ):
        class R:
            plan_file = "analysis-plan.md"
            data_review_file = "data-review.md"
            skeleton_file = "skeleton.md"
            report_file = "report.qmd"
            report_html_file = "report.html"
            design_review_file = "design-review.md"

        class W:
            path = str(tmp_path)
            data_dir = "data"
            context_path = str(tmp_path / "company-context.md")

        class S:
            research = R()
            workspace = W()

        gs.return_value = S()
        state = await run_coding(state, tmp_path)

    assert state.stage == Stage.CODING_READY
    assert (tmp_path / "report.qmd").exists()
    assert (tmp_path / "report.html").exists()
    assert state.design_verdict in {"approve", "revise"}
    assert calls[0] == "coder"
    assert calls.count("designer") == 2
    assert calls.count("coder") == 2  # draft + one fix

    state = approve_coding(state)
    assert state.stage == Stage.CODING_APPROVED


@pytest.mark.asyncio
async def test_apply_coding_edit_surgical(tmp_path: Path):
    from app.orchestration.coding import apply_coding_edit

    (tmp_path / "report.qmd").write_text("---\ntitle: T\n---\n\n# Hi\n\nold\n", encoding="utf-8")
    state = ResearchState(
        run_id="r2",
        workspace=str(tmp_path),
        stage=Stage.CODING_READY,
        status=Status.WAITING_FOR_USER,
        research_question="q",
        artifacts={"report": str(tmp_path / "report.qmd")},
    )
    calls: list[str] = []

    async def fake_run_agent(**kwargs):
        calls.append(kwargs["agent_name"])
        assert kwargs.get("json_mode") is True
        return _result('{"edits":[{"find":"old","replace":"new section"}],"notes":"ok"}')

    def fake_render(workspace, qmd_file, html_file):
        path = workspace / html_file
        path.write_text("<html></html>", encoding="utf-8")
        return path

    with (
        patch("app.orchestration.coding.run_agent", new=AsyncMock(side_effect=fake_run_agent)),
        patch("app.orchestration.coding.render_quarto", side_effect=fake_render),
        patch("app.orchestration.coding.report_data_warnings", return_value=[]),
        patch("app.orchestration.coding.get_settings") as gs,
    ):
        class R:
            report_file = "report.qmd"
            report_html_file = "report.html"

        class S:
            research = R()

        gs.return_value = S()
        state = await apply_coding_edit(state, tmp_path, "Поправь old на new section")

    assert state.stage == Stage.CODING_READY
    assert calls == ["coder"]
    text = (tmp_path / "report.qmd").read_text(encoding="utf-8")
    assert "new section" in text
    assert "# Hi" in text
    assert (tmp_path / "report.html").exists()


def test_heuristic_build_report():
    from app.models import ChatAction
    from app.orchestration.chat import _heuristic_decision

    state = ResearchState(
        run_id="t",
        workspace="/tmp",
        stage=Stage.SKELETON_APPROVED,
        status=Status.WAITING_FOR_USER,
        research_question="q",
        artifacts={"skeleton": "/tmp/s.md"},
    )
    d = _heuristic_decision(state, "едем дальше")
    assert d is not None
    assert d.action == ChatAction.BUILD_REPORT
