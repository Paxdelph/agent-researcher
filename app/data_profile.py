"""Deterministic CSV profiling for research data/ folder."""

from __future__ import annotations

import csv
from pathlib import Path


def profile_data_dir(data_dir: Path, max_sample_rows: int = 5) -> str:
    """Return markdown profile of all CSV files in data_dir."""
    if not data_dir.exists():
        return f"# Обзор данных\n\nПапка `{data_dir.name}/` отсутствует.\n"

    files = sorted(data_dir.glob("*.csv"))
    if not files:
        return f"# Обзор данных\n\nВ `{data_dir.as_posix()}` нет CSV-файлов.\n"

    parts = ["# Обзор данных\n", f"Найдено CSV: **{len(files)}**.\n"]
    for path in files:
        parts.append(_profile_csv(path, max_sample_rows=max_sample_rows))
    return "\n".join(parts).rstrip() + "\n"


def _profile_csv(path: Path, max_sample_rows: int = 5) -> str:
    try:
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames or [])
            nullish = {c: 0 for c in fields}
            sample: list[dict[str, str]] = []
            total = 0
            for row in reader:
                total += 1
                if len(sample) < max_sample_rows:
                    sample.append(row)
                for c in fields:
                    val = (row.get(c) or "").strip()
                    if val == "" or val.lower() in {"nan", "null", "none"}:
                        nullish[c] += 1
    except OSError as exc:
        return f"\n## `{path.name}`\n\nОшибка чтения: {exc}\n"

    size_kb = path.stat().st_size / 1024
    lines = [
        f"\n## `{path.name}`\n",
        f"- Строк (без заголовка): **{total}**",
        f"- Размер: **{size_kb:.1f} KB**",
        f"- Колонки ({len(fields)}): "
        + (", ".join(f"`{c}`" for c in fields) if fields else "(нет)"),
        "",
        "### Пропуски (пустые / null-like)",
    ]
    if fields:
        for c in fields:
            pct = (100.0 * nullish[c] / total) if total else 0.0
            lines.append(f"- `{c}`: {nullish[c]} ({pct:.1f}%)")
    else:
        lines.append("- (нет колонок)")

    lines.append("\n### Пример строк\n")
    if sample and fields:
        lines.append("| " + " | ".join(fields) + " |")
        lines.append("| " + " | ".join("---" for _ in fields) + " |")
        for row in sample:
            cells = []
            for c in fields:
                v = (row.get(c) or "").replace("|", "\\|")
                if len(v) > 40:
                    v = v[:37] + "..."
                cells.append(v)
            lines.append("| " + " | ".join(cells) + " |")
    else:
        lines.append("_пусто_")

    lines.append("")
    return "\n".join(lines)
