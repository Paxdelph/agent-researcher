"""StateStore: per-research runs and log reset."""

from __future__ import annotations

from pathlib import Path

from app.models import Stage
from app.state import StateStore, reset_store, workspace_identity


def test_new_run_clears_logs_and_brief(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("RESEARCH_HOST_PATH", raising=False)
    store = reset_store(tmp_path / "state")
    first = store.new_run(str(tmp_path / "ws-a"))
    first.research_question = "old brief"
    first.business_context = "old ctx"
    store.save(first)
    store.append_log({"id": "c1", "summary": "old call"})
    assert store.log_path.is_file()

    second = store.new_run(str(tmp_path / "ws-b"))
    assert second.research_question == ""
    assert second.business_context == ""
    assert second.stage == Stage.BRIEF
    assert second.usage.total_tokens == 0
    assert second.chat == []
    assert not store.log_path.exists()
    assert store.read_logs() == []


def test_ensure_resets_when_host_path_changes(tmp_path: Path, monkeypatch):
    store = reset_store(tmp_path / "state")
    monkeypatch.setenv("RESEARCH_HOST_PATH", "/host/researches/one")
    one = store.ensure_for_workspace("/workspace")
    one.research_question = "keep me"
    store.save(one)
    store.append_log({"id": "x", "summary": "log"})

    monkeypatch.setenv("RESEARCH_HOST_PATH", "/host/researches/two")
    two = store.ensure_for_workspace("/workspace")
    assert two.run_id != one.run_id
    assert two.research_question == ""
    assert two.workspace == workspace_identity()
    assert store.read_logs() == []


def test_ensure_keeps_state_for_same_host_path(tmp_path: Path, monkeypatch):
    store = reset_store(tmp_path / "state")
    monkeypatch.setenv("RESEARCH_HOST_PATH", "/host/researches/same")
    first = store.ensure_for_workspace("/workspace")
    first.research_question = "same research"
    store.save(first)

    again = store.ensure_for_workspace("/workspace")
    assert again.run_id == first.run_id
    assert again.research_question == "same research"
