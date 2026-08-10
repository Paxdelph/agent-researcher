"""Markdown helpers for preview."""

from __future__ import annotations

import re

import markdown as md

_TABLE_RE = re.compile(r"<table\b.*?</table>", re.IGNORECASE | re.DOTALL)


def render_markdown(text: str) -> str:
    html = md.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"],
        output_format="html5",
    )
    # Let wide tables use the full preview width with their own scroll.
    return _TABLE_RE.sub(lambda m: f'<div class="md-table-wrap">{m.group(0)}</div>', html)
