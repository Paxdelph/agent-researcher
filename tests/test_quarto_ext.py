"""Quarto researcher extension helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.orchestration.quarto_ext import (
    ensure_researcher_extension,
    researcher_extension_source,
)


def test_extension_source_exists():
    src = researcher_extension_source()
    assert (src / "_extension.yml").is_file()
    assert (src / "styles" / "report.scss").is_file()
    assert (src / "styles" / "_base.scss").is_file()
    assert (src / "styles" / "_components.scss").is_file()


def test_ensure_copies_into_workspace(tmp_path: Path):
    dest = ensure_researcher_extension(tmp_path)
    assert dest == tmp_path / "_extensions" / "researcher"
    assert (dest / "_extension.yml").is_file()
    assert (dest / "styles" / "report.scss").is_file()
    # idempotent second call
    ensure_researcher_extension(tmp_path)
    assert (dest / "_extension.yml").is_file()


def test_extension_yml_declares_html_format():
    text = (researcher_extension_source() / "_extension.yml").read_text(encoding="utf-8")
    assert "contributes:" in text
    assert "formats:" in text
    assert "report.scss" in text
