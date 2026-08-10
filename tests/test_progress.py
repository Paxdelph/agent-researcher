"""Progress announcement helpers and log updates."""

from __future__ import annotations

from pathlib import Path

from app.agents.runner import progress_chat_line
from app.state import StateStore


def test_progress_chat_line_strips_prefix():
    assert progress_chat_line("lead", "Lead: черновик скелета") == (
        "Lead работает: черновик скелета…"
    )
    assert progress_chat_line("analyst", "Analyst: критика скелета") == (
        "Analyst работает: критика скелета…"
    )
    assert progress_chat_line("storyteller") == "Storyteller работает…"


def test_update_log_replaces_running(tmp_path: Path):
    store = StateStore(tmp_path)
    store.append_log(
        {
            "id": "c1",
            "role": "lead",
            "status": "running",
            "summary": "Lead: draft",
            "model": "m",
            "input_tokens": 0,
            "output_tokens": 0,
        }
    )
    store.update_log(
        "c1",
        {
            "id": "c1",
            "role": "lead",
            "status": "completed",
            "summary": "Lead: draft",
            "model": "m",
            "input_tokens": 10,
            "output_tokens": 20,
        },
    )
    logs = store.read_logs()
    assert len(logs) == 1
    assert logs[0]["status"] == "completed"
    assert logs[0]["input_tokens"] == 10
