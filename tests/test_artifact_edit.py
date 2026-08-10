"""Manual artifact save (no LLM)."""

from __future__ import annotations

from pathlib import Path

from app.models import ResearchState, Stage, Status
from app.orchestration.engine import Engine


def test_save_artifact_writes_plan(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_PATH", str(tmp_path))
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))

    from app.config import clear_settings_cache

    clear_settings_cache()

    # Build a minimal engine against tmp workspace
    class FakeSettings:
        class app:
            state_dir = str(tmp_path / "state")

        class workspace:
            path = str(tmp_path)
            data_dir = "data"

        class research:
            plan_file = "analysis-plan.md"

        class limits:
            default_timeout_seconds = 30

        agents = {}

    from app import state as state_mod
    from app.orchestration import engine as engine_mod

    clear_settings_cache()
    monkeypatch.setattr(engine_mod, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(state_mod, "get_settings", lambda: FakeSettings())
    state_mod.reset_store(tmp_path / "state")
    engine_mod._engine = None

    engine = Engine()
    engine.state.stage = Stage.PLAN_READY
    engine.state.status = Status.WAITING_FOR_USER
    engine.store.save(engine.state)

    engine.save_artifact("analysis-plan.md", "# Hello\n\nWorld")
    assert (tmp_path / "analysis-plan.md").read_text(encoding="utf-8").startswith("# Hello")
    assert engine.state.artifacts.analysis_plan
    assert any("вручную" in m.content for m in engine.state.chat)
