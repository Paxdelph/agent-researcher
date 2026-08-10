"""Surgical qmd edit plan tests."""

from __future__ import annotations

import pytest

from app.orchestration.qmd_edits import (
    QmdEditError,
    apply_qmd_edits,
    parse_qmd_edit_plan,
    wants_full_report_rebuild,
)


def test_parse_and_apply_unique_replace():
    src = "# A\n\nhello\n\n# B\n"
    plan = parse_qmd_edit_plan(
        '{"edits":[{"find":"hello","replace":"hello\\n\\n# New\\n"}],"notes":"add"}'
    )
    out = apply_qmd_edits(src, plan)
    assert "# New" in out
    assert out.startswith("# A")


def test_reject_ambiguous_find():
    src = "x\nx\n"
    plan = parse_qmd_edit_plan('{"edits":[{"find":"x","replace":"y"}]}')
    with pytest.raises(QmdEditError, match="2 раз"):
        apply_qmd_edits(src, plan)


def test_rebuild_markers():
    assert wants_full_report_rebuild("переделай отчёт с нуля")
    assert not wants_full_report_rebuild("добавь секцию про сегменты")
    assert not wants_full_report_rebuild("перерендери")
