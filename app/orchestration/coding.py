"""Coding pipeline: Coder → Quarto render → Designer (max one fix round)."""

from __future__ import annotations

from pathlib import Path

from app.agents.runner import read_workspace_text, run_agent, write_workspace_text
from app.config import get_settings
from app.models import ChatMessage, ImagePart, ResearchState, Stage, Status
from app.orchestration.context import artifact_excerpt, coding_context_block
from app.orchestration.parse import extract_qmd, parse_json_object
from app.orchestration.planning import brief_block
from app.orchestration.qmd_validate import QmdValidationError, validate_coder_result, validate_qmd_text
from app.orchestration.render import (
    RenderError,
    html_excerpt,
    images_as_base64,
    render_quarto,
    report_data_warnings,
    screenshot_html,
)


def _parse_design(text: str) -> dict:
    data = parse_json_object(text)
    verdict = str(data.get("verdict", "revise")).strip().lower()
    if verdict not in {"approve", "revise"}:
        verdict = "revise"
    issues = data.get("issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]
    issues = [str(x).strip() for x in issues if str(x).strip()]
    notes = str(data.get("notes") or "").strip()
    return {"verdict": verdict, "issues": issues, "notes": notes}


async def _run_designer(
    state: ResearchState,
    workspace: Path,
    *,
    pass_index: int,
    html_path: Path,
) -> dict:
    settings = get_settings()
    shot_dir = workspace / ".design-shots"
    shots = screenshot_html(html_path, shot_dir)
    images = [
        ImagePart(media_type=mt, data_base64=b64)
        for mt, b64 in images_as_base64(shots)
    ]

    skeleton = read_workspace_text(workspace, settings.research.skeleton_file)
    data_review = read_workspace_text(workspace, settings.research.data_review_file)
    user_bits = [
        f"Это просмотр #{pass_index} (максимум 2: первичный и после одного фикса Coder).",
        "Сделай design review по skill design_review. Верни только JSON.",
        f"## Skeleton (ориентир секций)\n{artifact_excerpt(skeleton) or '(нет)'}\n",
        f"## Data review (колонки/ограничения)\n{artifact_excerpt(data_review, max_chars=6000) or '(нет)'}\n",
    ]
    if images:
        user_bits.append(
            f"Приложено скриншотов: {len(images)}. Опирайся на них как на главный сигнал."
        )
    else:
        user_bits.append(
            "Скриншоты недоступны — оцени по HTML-фрагменту (ограниченно).\n"
            f"## HTML excerpt\n```html\n{html_excerpt(html_path)}\n```"
        )

    result = await run_agent(
        state=state,
        agent_name="designer",
        stage=Stage.CODING,
        user_message="\n\n".join(user_bits),
        summary=f"Designer: ревью отчёта (pass {pass_index})",
        json_mode=True,
        images=images,
        skill_override=["design_review"],
    )
    return _parse_design(result.text)


def _render_and_store(state: ResearchState, workspace: Path) -> Path:
    settings = get_settings()
    html_path = render_quarto(
        workspace,
        settings.research.report_file,
        settings.research.report_html_file,
    )
    state.artifacts.report_html = str(html_path)
    return html_path


async def _render_with_data_check(
    state: ResearchState,
    workspace: Path,
    *,
    allow_data_fix: bool,
) -> Path:
    """Render HTML; if report looks empty, one Coder pass to wire CSV schema."""
    settings = get_settings()
    html_path = _render_and_store(state, workspace)
    warnings = report_data_warnings(html_path)
    if not warnings or not allow_data_fix:
        if warnings:
            raise RenderError(
                "Отчёт собрался без данных (проверь колонки CSV vs setup-чанк):\n"
                + "\n".join(f"- {w}" for w in warnings)
            )
        return html_path

    current = read_workspace_text(workspace, settings.research.report_file)
    ctx = coding_context_block(workspace)
    issues = "\n".join(f"- {w}" for w in warnings)
    try:
        await _coder_write(
            state,
            workspace,
            summary="Coder: подключение данных в report.qmd",
            user_message=(
                "Quarto отрендерился, но отчёт пустой — данные не подключены.\n"
                "Исправь setup/чтение CSV: используй **реальные** имена колонок и "
                "`event_name` из Data review / Fresh profile. Не выдумывай `event_time`, "
                "`checkout_start` и т.п.\n"
                "Верни полный обновлённый `report.qmd`.\n\n"
                f"## Проблемы в HTML\n{issues}\n\n"
                f"{ctx}\n\n"
                f"## Current report.qmd\n```qmd\n{current}\n```\n"
            ),
        )
    except QmdValidationError as exc:
        raise RenderError(str(exc)) from exc
    html_path = _render_and_store(state, workspace)
    warnings = report_data_warnings(html_path)
    if warnings:
        raise RenderError(
            "После правки данные всё ещё не подключены:\n"
            + "\n".join(f"- {w}" for w in warnings)
        )
    return html_path


async def _coder_write(
    state: ResearchState,
    workspace: Path,
    *,
    user_message: str,
    summary: str,
) -> str:
    settings = get_settings()
    agent = settings.agents["coder"]
    result = await run_agent(
        state=state,
        agent_name="coder",
        stage=Stage.CODING,
        user_message=user_message,
        summary=summary,
        skill_override=[
            "quarto_coding",
            "viz_craft",
            "product_analytics",
        ],
    )
    qmd = extract_qmd(result.text)
    validate_coder_result(result, qmd, agent)
    path = write_workspace_text(workspace, settings.research.report_file, qmd)
    state.artifacts.report = str(path)
    return qmd


def _designer_blank_report(review: dict) -> bool:
    notes = (review.get("notes") or "").lower()
    issues = " ".join(review.get("issues") or []).lower()
    blob = f"{notes} {issues}"
    signals = (
        "бел",
        "white",
        "пуст",
        "blank",
        "не содержат видимого",
        "чистые белые",
    )
    return any(s in blob for s in signals)


def _fail_coding(state: ResearchState, message: str) -> ResearchState:
    state.status = Status.FAILED
    state.error = message
    state.status_text = "Coder не собрал report.qmd"
    state.active_role = None
    state.chat.append(
        ChatMessage(
            role="assistant",
            content=(
                "Не удалось собрать `report.qmd` — файл не перезаписан пустым черновиком.\n"
                f"```\n{message}\n```\n"
                "Попробуйте «переделай отчёт с нуля» после перезапуска с обновлённым config."
            ),
        )
    )
    return state


def _fail_render(state: ResearchState, exc: RenderError, *, after_fix: bool = False) -> ResearchState:
    state.status = Status.FAILED
    state.error = str(exc)
    state.status_text = "Ошибка рендера после фикса" if after_fix else "Ошибка рендера Quarto"
    state.active_role = None
    label = "После фикса Coder рендер упал" if after_fix else "Не удалось срендерить `report.qmd`"
    state.chat.append(
        ChatMessage(
            role="assistant",
            content=f"{label}:\n```\n{exc}\n```",
        )
    )
    return state


def _finish_render_only(
    state: ResearchState,
    *,
    message: str,
    status_text: str = "Отчёт обновлён — превью HTML",
) -> ResearchState:
    state.stage = Stage.CODING_READY
    state.status = Status.WAITING_FOR_USER
    state.active_role = None
    state.status_text = status_text
    state.chat.append(ChatMessage(role="assistant", content=message))
    return state


async def render_only(state: ResearchState, workspace: Path, *, note: str | None = None) -> ResearchState:
    """Quarto → HTML without Designer / Coder."""
    try:
        _render_and_store(state, workspace)
    except RenderError as exc:
        return _fail_render(state, exc)
    return _finish_render_only(
        state,
        message=note
        or "Срендерил `report.qmd` → `report.html` (без моделей, без Design review).",
        status_text="Срендерено без моделей",
    )


async def _design_cycle(
    state: ResearchState,
    workspace: Path,
    *,
    allow_fix: bool = True,
) -> ResearchState:
    """Render → Designer; optional one Coder fix → re-render → Designer."""
    settings = get_settings()
    ctx = coding_context_block(workspace)

    try:
        html_path = await _render_with_data_check(
            state, workspace, allow_data_fix=True
        )
    except RenderError as exc:
        return _fail_render(state, exc)

    review = await _run_designer(state, workspace, pass_index=1, html_path=html_path)
    state.design_verdict = review["verdict"]
    state.design_notes = review["notes"]

    if review["verdict"] == "revise" and allow_fix and review["issues"]:
        issues_block = "\n".join(f"- {x}" for x in review["issues"])
        current = read_workspace_text(workspace, settings.research.report_file)
        try:
            await _coder_write(
                state,
                workspace,
                summary="Coder: фикс по design review",
                user_message=(
                    "Исправь визуальные замечания Designer. Один раунд фикса. "
                    "Верни полный обновлённый `report.qmd`.\n"
                    "Сохрани подключение данных к реальным колонкам из data-review.\n\n"
                    f"## Designer issues\n{issues_block}\n\n"
                    f"## Designer notes\n{review['notes'] or '(нет)'}\n\n"
                    f"{ctx}\n\n"
                    f"## Current report.qmd\n```qmd\n{current}\n```\n"
                ),
            )
        except QmdValidationError as exc:
            return _fail_coding(state, str(exc))
        try:
            html_path = await _render_with_data_check(
                state, workspace, allow_data_fix=False
            )
        except RenderError as exc:
            return _fail_render(state, exc, after_fix=True)

        review = await _run_designer(
            state, workspace, pass_index=2, html_path=html_path
        )
        qmd_now = read_workspace_text(workspace, settings.research.report_file)
        qmd_issues = validate_qmd_text(qmd_now)
        if review["verdict"] == "revise":
            if qmd_issues or _designer_blank_report(review):
                detail = "; ".join(qmd_issues) if qmd_issues else review["notes"] or "пустой отчёт"
                return _fail_coding(state, f"Design review не пройден: {detail}")
            review = {
                "verdict": "approve",
                "issues": review["issues"],
                "notes": (
                    (review["notes"] + " ").strip()
                    + "Оставшиеся замечания зафиксированы, но второй fix-раунд не запускаем."
                ).strip(),
            }
        state.design_verdict = review["verdict"]
        state.design_notes = review["notes"]

    state.stage = Stage.CODING_READY
    state.status = Status.WAITING_FOR_USER
    state.active_role = None
    state.status_text = "Отчёт готов — превью HTML, правки в чате или «едем дальше»"
    note = state.design_notes or "Design review пройден."
    state.chat.append(
        ChatMessage(
            role="assistant",
            content=(
                f"Отчёт собран (`report.qmd` → `report.html`). "
                f"Designer: **{state.design_verdict}**. {note}"
            ),
        )
    )
    return state


async def rerender_and_review(state: ResearchState, workspace: Path) -> ResearchState:
    """Re-render existing report.qmd and run design cycle (one fix round)."""
    settings = get_settings()
    existing = read_workspace_text(workspace, settings.research.report_file)
    if not existing.strip():
        return await run_coding(state, workspace)
    state.stage = Stage.CODING
    state.status = Status.RUNNING
    state.error = None
    state.artifacts.report = str(workspace / settings.research.report_file)
    state.chat.append(
        ChatMessage(
            role="system",
            content="Перерендер + Design review…",
        )
    )
    return await _design_cycle(state, workspace, allow_fix=True)


async def run_coding(state: ResearchState, workspace: Path) -> ResearchState:
    state.stage = Stage.CODING
    state.status = Status.RUNNING
    state.error = None

    brief = brief_block(state, workspace)
    ctx = coding_context_block(workspace)

    try:
        await _coder_write(
            state,
            workspace,
            summary="Coder: черновик report.qmd",
            user_message=(
                "Собери полный `report.qmd` по skill quarto_coding и скелету.\n"
                "Format: `researcher-html: default`. Без CSS/`<style>`.\n"
                "Plotly без modeBar. Semantic-блоки (.finding/.kpi/.warning/.recommendation).\n"
                "Только реальные поля данных из Data review / Fresh profile.\n\n"
                f"## Brief\n{brief}\n\n"
                f"{ctx}\n"
            ),
        )
    except QmdValidationError as exc:
        return _fail_coding(state, str(exc))
    return await _design_cycle(state, workspace, allow_fix=True)


async def apply_coding_edit(
    state: ResearchState,
    workspace: Path,
    user_message: str,
    reply_hint: str | None = None,
) -> ResearchState:
    """Point edits to existing report.qmd via find/replace JSON — never full rewrite."""
    from app.orchestration.qmd_edits import (
        QmdEditError,
        apply_qmd_edits,
        parse_qmd_edit_plan,
    )

    settings = get_settings()
    existing = read_workspace_text(workspace, settings.research.report_file)
    if not existing:
        raise RuntimeError("report.qmd ещё нет — сначала соберите отчёт")

    state.stage = Stage.CODING
    state.status = Status.RUNNING
    state.error = None

    ctx = coding_context_block(workspace, include_profile=False)
    result = await run_agent(
        state=state,
        agent_name="coder",
        stage=Stage.CODING,
        user_message=(
            "Точечная правка уже собранного `report.qmd`.\n"
            "НЕ переписывай файл целиком. НЕ трогай секции вне запроса.\n"
            "Сохраняй реальные имена колонок из data-review.\n"
            "Верни ТОЛЬКО JSON:\n"
            '{"edits":[{"find":"точный уникальный фрагмент из файла",'
            '"replace":"тот же фрагмент с правкой"}],'
            '"notes":"кратко что изменил"}\n'
            "Правила:\n"
            "- `find` должен встречаться в файле ровно один раз\n"
            "- для новой секции: find = якорь (например конец предыдущей секции), "
            "replace = якорь + новая секция\n"
            "- минимум правок, без косметики «заодно»\n"
            "- без markdown-преамбулы вокруг JSON\n\n"
            f"## User request\n{user_message}\n"
            + (f"\n## Reply hint\n{reply_hint}\n" if reply_hint else "")
            + f"\n{ctx}\n"
            + f"\n## Current report.qmd\n```qmd\n{existing}\n```\n"
        ),
        summary="Coder: точечная правка report.qmd",
        json_mode=True,
        skill_override=["quarto_coding", "viz_craft", "product_analytics"],
    )

    try:
        plan = parse_qmd_edit_plan(result.text)
        patched = apply_qmd_edits(existing, plan)
    except (QmdEditError, ValueError, TypeError) as exc:
        state.status = Status.FAILED
        state.error = str(exc)
        state.status_text = "Точечная правка не применилась"
        state.active_role = None
        state.chat.append(
            ChatMessage(
                role="assistant",
                content=(
                    f"Не смог точечно поправить `report.qmd`: {exc}\n"
                    "Файл не трогал. Уточни место правки или скажи «переделай отчёт с нуля»."
                ),
            )
        )
        return state

    path = write_workspace_text(workspace, settings.research.report_file, patched)
    state.artifacts.report = str(path)

    try:
        await _render_with_data_check(state, workspace, allow_data_fix=False)
    except RenderError as exc:
        return _fail_render(state, exc)

    n = len(plan.edits)
    note = plan.notes or "ок"
    return _finish_render_only(
        state,
        message=(
            f"Точечная правка применена ({n} replace), HTML пересобран "
            f"(без Design review). {note}"
        ),
        status_text="Точечная правка report.qmd",
    )


def approve_coding(state: ResearchState) -> ResearchState:
    state.stage = Stage.CODING_APPROVED
    state.status = Status.WAITING_FOR_USER
    state.status_text = "Отчёт утверждён"
    state.active_role = None
    state.chat.append(
        ChatMessage(
            role="assistant",
            content=(
                "Отчёт утверждён (`report.html`). "
                "Можно скачать/забрать из папки рисерча или попросить точечные правки."
            ),
        )
    )
    return state
