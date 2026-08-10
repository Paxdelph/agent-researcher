"""Surgical find/replace edits for an existing report.qmd."""

from __future__ import annotations

from dataclasses import dataclass

from app.orchestration.parse import parse_json_object


@dataclass
class QmdEdit:
    find: str
    replace: str


@dataclass
class QmdEditPlan:
    edits: list[QmdEdit]
    notes: str = ""


class QmdEditError(ValueError):
    pass


def parse_qmd_edit_plan(text: str) -> QmdEditPlan:
    data = parse_json_object(text)
    raw_edits = data.get("edits")
    if not isinstance(raw_edits, list) or not raw_edits:
        raise QmdEditError("Coder не вернул список edits")

    edits: list[QmdEdit] = []
    for i, item in enumerate(raw_edits):
        if not isinstance(item, dict):
            raise QmdEditError(f"edits[{i}] должен быть объектом")
        find = item.get("find")
        replace = item.get("replace")
        if find is None or replace is None:
            raise QmdEditError(f"edits[{i}] нужен find и replace")
        find_s = str(find)
        replace_s = str(replace)
        if not find_s:
            raise QmdEditError(f"edits[{i}].find пустой")
        if find_s == replace_s:
            continue
        edits.append(QmdEdit(find=find_s, replace=replace_s))

    if not edits:
        raise QmdEditError("Все edits пустые (find == replace)")
    notes = str(data.get("notes") or "").strip()
    return QmdEditPlan(edits=edits, notes=notes)


def apply_qmd_edits(source: str, plan: QmdEditPlan) -> str:
    text = source
    for i, edit in enumerate(plan.edits):
        count = text.count(edit.find)
        if count == 0:
            preview = edit.find[:120].replace("\n", "\\n")
            raise QmdEditError(
                f"edits[{i}]: фрагмент find не найден в report.qmd: «{preview}»"
            )
        if count > 1:
            preview = edit.find[:120].replace("\n", "\\n")
            raise QmdEditError(
                f"edits[{i}]: find встречается {count} раз — нужен более уникальный якорь: «{preview}»"
            )
        text = text.replace(edit.find, edit.replace, 1)
    return text


def wants_design_review(message: str) -> bool:
    text = message.strip().lower()
    return any(
        h in text
        for h in (
            "design review",
            "проверь дизайн",
            "дизайн ревью",
            "design-ревью",
            "посмотри дизайн",
            "визуально проверь",
        )
    )


def wants_full_report_rebuild(message: str) -> bool:
    """Explicit full rewrite of report.qmd (+ design cycle)."""
    text = message.strip().lower()
    markers = (
        "с нуля",
        "переделай отчёт",
        "переделай отчет",
        "переделай report",
        "перепиши отчёт",
        "перепиши отчет",
        "перепиши report",
        "весь отчёт заново",
        "весь отчет заново",
        "отчёт заново",
        "отчет заново",
        "full rebuild",
        "rebuild report",
        "from scratch",
        "собери отчёт с нуля",
        "собери отчет с нуля",
        "сделай отчёт с нуля",
        "сделай отчет с нуля",
        "собери отчёт заново",
        "собери отчет заново",
        "пересобери с нуля",
    )
    return any(m in text for m in markers)
