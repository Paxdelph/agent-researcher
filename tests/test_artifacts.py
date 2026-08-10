"""Artifact tabs / catalog."""

from __future__ import annotations

from pathlib import Path

from app.artifacts import build_tabs, load_preview, resolve_artifact
from app.models import ResearchState, Stage, Status


def test_resolve_defaults_to_plan():
    a = resolve_artifact(None)
    assert a.id == "plan"
    assert a.file.endswith(".md")


def test_tabs_mark_missing_and_active(tmp_path: Path, monkeypatch):
    company = tmp_path / "company" / "context.md"
    company.parent.mkdir(parents=True)
    company.write_text("# Company\n", encoding="utf-8")

    monkeypatch.setenv("WORKSPACE_PATH", str(tmp_path))
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CONTEXT_PATH", str(company))
    from app.config import clear_settings_cache

    clear_settings_cache()
    (tmp_path / "analysis-plan.md").write_text("# Plan\n", encoding="utf-8")

    active = resolve_artifact("plan")
    tabs = build_tabs(tmp_path, active)
    by_id = {t.id: t for t in tabs}
    assert by_id["plan"].exists is True
    assert by_id["plan"].active is True
    assert by_id["context"].exists is True
    assert by_id["skeleton"].exists is False


def test_load_preview_plan(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_PATH", str(tmp_path))
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
    from app.config import clear_settings_cache

    clear_settings_cache()
    (tmp_path / "analysis-plan.md").write_text("# Hello\n", encoding="utf-8")
    state = ResearchState(
        run_id="t",
        workspace=str(tmp_path),
        stage=Stage.PLAN_READY,
        status=Status.WAITING_FOR_USER,
    )
    loaded = load_preview(state, "plan")
    assert loaded["preview"]["exists"] is True
    assert "Hello" in (loaded["preview"]["html"] or "")
