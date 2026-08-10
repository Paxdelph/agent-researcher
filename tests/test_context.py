"""Tests for shared orchestration context helpers."""

from __future__ import annotations

from pathlib import Path

from app.orchestration.context import artifact_excerpt, coding_context_block
from app.orchestration.render import report_data_warnings


def test_artifact_excerpt_keeps_head_and_tail():
    text = "A" * 5000 + "MIDDLE" + "B" * 5000
    out = artifact_excerpt(text, max_chars=200)
    assert out.startswith("A")
    assert out.endswith("B")
    assert "MIDDLE" not in out
    assert "середина опущена" in out


def test_coding_context_block_includes_fresh_profile(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_PATH", str(tmp_path))
    monkeypatch.setenv("STATE_DIR", str(tmp_path / ".state"))
    monkeypatch.setenv("CONTEXT_PATH", str(tmp_path / "context.md"))
    from app.config import clear_settings_cache

    clear_settings_cache()
    (tmp_path / "context.md").write_text("# ctx\n", encoding="utf-8")
    (tmp_path / "skeleton.md").write_text("# sk\n", encoding="utf-8")
    (tmp_path / "analysis-plan.md").write_text("# plan\n", encoding="utf-8")
    (tmp_path / "data-review.md").write_text("# review\n", encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    (data / "events.csv").write_text("user_id,event_name\nu1,cart\n", encoding="utf-8")

    block = coding_context_block(tmp_path)
    assert "skeleton.md" in block
    assert "data-review.md" in block
    assert "Fresh data profile" in block
    assert "`user_id`" in block


def test_report_data_warnings_detects_empty_shell(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text(
        "<p>Файл `data/events.csv` не найден или не содержит обязательных полей</p>",
        encoding="utf-8",
    )
    assert report_data_warnings(html)


def test_report_data_warnings_clean_report(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text("<html><body><h1>OK</h1></body></html>", encoding="utf-8")
    assert report_data_warnings(html) == []
