"""Chat interpretation and control actions."""

from __future__ import annotations

from pathlib import Path

from app.agents.runner import run_agent, write_workspace_text
from app.config import get_settings
from app.models import ChatAction, ChatDecision, ChatMessage, ResearchState, Stage, Status
from app.orchestration.context import current_artifact_preview
from app.orchestration.coding import (
    apply_coding_edit,
    approve_coding,
    render_only,
    rerender_and_review,
    run_coding,
)
from app.orchestration.data_review import run_data_review
from app.orchestration.parse import parse_chat_decision, strip_markdown_fence
from app.orchestration.planning import approve_plan, apply_plan_edit, brief_block, run_planning
from app.orchestration.qmd_edits import wants_design_review, wants_full_report_rebuild
from app.orchestration.skeleton import approve_skeleton, apply_skeleton_edit, run_skeleton


def _history_block(state: ResearchState, limit: int = 10) -> str:
    msgs = state.chat[-limit:]
    if not msgs:
        return "(пусто)"
    lines = []
    for m in msgs:
        who = {"user": "Аналитик", "assistant": "Lead", "system": "Статус"}.get(m.role, m.role)
        lines.append(f"{who}: {m.content}")
    return "\n\n".join(lines)


def _heuristic_decision(state: ResearchState, message: str) -> ChatDecision | None:
    text = message.strip().lower()
    if not text:
        return ChatDecision(action=ChatAction.CLARIFY, reply="Пустое сообщение.")

    advance_exact = {
        "ок", "окей", "ok", "хорошо", "принято", "дальше",
        "едем дальше", "давай дальше", "утверждаю", "утвердить", "approve",
        "ок, дальше", "окей, дальше", "можно дальше",
        "план ок", "план хороший", "всё ок", "все ок",
        "скелет ок", "скелет хороший",
        "отчёт ок", "отчет ок", "отчёт хороший", "отчет хороший",
    }
    advance_phrases = (
        "едем дальше", "давай дальше", "утверждаю план", "утвердить план",
        "можно дальше", "план ок", "утверждаю скелет", "скелет ок",
        "утверждаю отчёт", "утверждаю отчет", "отчёт ок", "отчет ок",
    )
    start_markers = (
        "спланируй", "сделай план", "начать планирование", "start planning",
        "поехали", "давай план", "перепланируй", "заново план",
    )
    data_markers = (
        "проверь данные", "проверь файлы", "данные готовы", "сверь данные",
        "сверь план с данными", "посмотри data", "review data", "data ready", "проверь csv",
    )
    skeleton_markers = (
        "сделай скелет", "собери скелет", "скелет отчёта", "скелет отчета",
        "build skeleton", "report skeleton", "составь скелет", "напиши скелет",
    )
    report_markers = (
        "собери отчёт", "собери отчет", "сделай отчёт", "сделай отчет",
        "напиши код", "сделай код", "quarto", "собери quarto", "build report",
        "напиши qmd", "сделай report", "закодируй", "coder",
    )
    render_markers = (
        "перерендери", "render report",
    )
    design_markers_hit = wants_design_review(message)
    rebuild_hit = wants_full_report_rebuild(message)

    has_plan = bool(state.artifacts.analysis_plan) or state.stage in {
        Stage.PLAN_READY, Stage.PLAN_APPROVED, Stage.WAITING_FOR_DATA,
        Stage.PLAN_ADJUSTED, Stage.DATA_READY, Stage.SKELETON, Stage.SKELETON_READY,
        Stage.SKELETON_APPROVED, Stage.CODING, Stage.CODING_READY, Stage.CODING_APPROVED,
    }
    has_brief = bool(state.research_question.strip())
    has_report = bool(state.artifacts.report) or state.stage in {
        Stage.CODING_READY, Stage.CODING_APPROVED,
    }

    if not has_plan and has_brief and any(m in text for m in start_markers):
        return ChatDecision(
            action=ChatAction.START_PLANNING,
            reply="Запускаю планирование: Lead → Analyst → план.",
        )

    report_stage_ok = state.stage in {
        Stage.SKELETON_APPROVED, Stage.CODING_READY, Stage.CODING_APPROVED, Stage.CODING,
    }
    if report_stage_ok and (design_markers_hit or any(m in text for m in render_markers)):
        return ChatDecision(
            action=ChatAction.BUILD_REPORT,
            reply=(
                "Запускаю Design review."
                if design_markers_hit
                else "Перерендерю HTML без моделей."
            ),
        )
    if report_stage_ok and rebuild_hit:
        return ChatDecision(
            action=ChatAction.BUILD_REPORT,
            reply="Пересобираю отчёт с нуля: Coder → рендер → Designer.",
        )
    if report_stage_ok and not has_report and any(m in text for m in report_markers):
        return ChatDecision(
            action=ChatAction.BUILD_REPORT,
            reply="Собираю отчёт: Coder (Quarto/R) → рендер → Designer.",
        )

    if any(m in text for m in skeleton_markers) and state.stage in {
        Stage.DATA_READY, Stage.PLAN_ADJUSTED, Stage.SKELETON_READY, Stage.SKELETON_APPROVED,
    }:
        return ChatDecision(
            action=ChatAction.BUILD_SKELETON,
            reply="Собираю скелет: Lead → Analyst → Lead → Storyteller → BI Analyst.",
        )

    if state.stage in {
        Stage.WAITING_FOR_DATA, Stage.PLAN_APPROVED, Stage.PLAN_ADJUSTED,
        Stage.DATA_READY, Stage.DATA_REVIEW,
    } and any(m in text for m in data_markers):
        return ChatDecision(
            action=ChatAction.REVIEW_DATA,
            reply="Смотрю CSV в data/ и сверю с планом.",
        )

    if has_plan and state.stage == Stage.PLAN_READY:
        if text in advance_exact or any(p in text for p in advance_phrases):
            return ChatDecision(
                action=ChatAction.ADVANCE,
                reply="Принято — фиксирую утверждение плана.",
            )

    if state.stage in {Stage.WAITING_FOR_DATA, Stage.PLAN_APPROVED}:
        if text in advance_exact or any(p in text for p in advance_phrases):
            return ChatDecision(
                action=ChatAction.REVIEW_DATA,
                reply="Ок — проверяю, что лежит в data/.",
            )

    if state.stage in {Stage.DATA_READY, Stage.PLAN_ADJUSTED}:
        if text in advance_exact or any(p in text for p in advance_phrases):
            return ChatDecision(
                action=ChatAction.BUILD_SKELETON,
                reply="Дальше — скелет отчёта (Lead → Analyst → Storyteller → BI).",
            )

    if state.stage == Stage.SKELETON_READY:
        if text in advance_exact or any(p in text for p in advance_phrases):
            return ChatDecision(
                action=ChatAction.ADVANCE,
                reply="Принято — утверждаю скелет.",
            )

    if state.stage == Stage.SKELETON_APPROVED:
        if text in advance_exact or any(p in text for p in advance_phrases):
            return ChatDecision(
                action=ChatAction.BUILD_REPORT,
                reply="Дальше — код отчёта в Quarto (Coder → Designer).",
            )

    if state.stage == Stage.CODING_READY:
        if text in advance_exact or any(p in text for p in advance_phrases):
            return ChatDecision(
                action=ChatAction.ADVANCE,
                reply="Принято — утверждаю отчёт.",
            )

    return None


async def interpret_message(state: ResearchState, message: str) -> ChatDecision:
    heuristic = _heuristic_decision(state, message)
    if heuristic is not None:
        return heuristic

    plan_note = "есть" if state.artifacts.analysis_plan else "нет"
    skel_note = "есть" if state.artifacts.skeleton else "нет"
    report_note = "есть" if state.artifacts.report else "нет"
    artifact_preview = current_artifact_preview(state, Path(state.workspace))
    result = await run_agent(
        state=state,
        agent_name="lead",
        stage=state.stage,
        user_message=(
            "Определи action по сообщению пользователя. Верни только JSON по skill chat_control.\n"
            "Если action=edit для плана/скелета — верни полный artifact. "
            "Для правок уже собранного report.qmd: action=edit, artifact=null "
            "(Coder сделает ТОЧЕЧНЫЕ find/replace, без переписывания всего файла).\n"
            "Полную пересборку report (Coder+Designer) — только по явной команде "
            "«с нуля» / «переделай отчёт» / «заново» → build_report.\n"
            "«перерендери» → build_report (рендер без моделей). "
            "«проверь дизайн» → build_report (design review).\n"
            "Не трогай отчёт, если пользователь просто спрашивает.\n\n"
            f"## Current stage\n{state.stage.value}\n"
            f"## Plan on disk\n{plan_note}\n"
            f"## Skeleton on disk\n{skel_note}\n"
            f"## Report on disk\n{report_note}\n"
            f"## Brief\n{brief_block(state, Path(state.workspace))}\n"
            f"## Current artifact preview\n{artifact_preview}\n"
            f"## Recent chat\n{_history_block(state)}\n"
            f"## Latest user message\n{message}\n"
        ),
        summary="Lead: разбор сообщения",
        json_mode=True,
        announce=False,
        skill_override=[
            "chat_control",
            "artifact_edit",
            "planning_pipeline",
            "report_skeleton",
            "quarto_coding",
        ],
    )
    return parse_chat_decision(result.text)


def _editing_report(state: ResearchState, message: str) -> bool:
    if state.stage in {
        Stage.CODING, Stage.CODING_READY, Stage.CODING_APPROVED,
    }:
        text = message.lower()
        if any(k in text for k in ("скелет", "skeleton", "план", "plan")):
            return False
        return True
    text = message.lower()
    return any(
        k in text
        for k in ("report.qmd", "qmd", "quarto", "отчёт", "отчет", "код отчёта", "код отчета")
    )


def _editing_skeleton(state: ResearchState, message: str) -> bool:
    if _editing_report(state, message) and state.stage in {
        Stage.CODING, Stage.CODING_READY, Stage.CODING_APPROVED,
    }:
        return False
    if state.stage in {Stage.SKELETON_READY, Stage.SKELETON_APPROVED, Stage.SKELETON}:
        return True
    text = message.lower()
    return "скелет" in text or "skeleton" in text


async def handle_user_message(
    state: ResearchState,
    workspace: Path,
    message: str,
    *,
    already_logged: bool = False,
) -> ResearchState:
    message = message.strip()
    if not already_logged:
        state.chat.append(ChatMessage(role="user", content=message))
    state.error = None

    if state.stage == Stage.BRIEF and not state.research_question.strip():
        if len(message) > 20:
            state.research_question = message
            state.chat.append(
                ChatMessage(
                    role="system",
                    content="Сохранил сообщение как research question и запускаю планирование.",
                )
            )
            state.status = Status.RUNNING
            return await run_planning(state, workspace)

    decision = await interpret_message(state, message)

    if decision.action == ChatAction.START_PLANNING:
        if not state.research_question.strip():
            state.chat.append(
                ChatMessage(
                    role="assistant",
                    content="Сначала укажите research question в брифе слева.",
                )
            )
            state.status = Status.WAITING_FOR_USER
            return state
        state.chat.append(ChatMessage(role="assistant", content=decision.reply))
        state.status = Status.RUNNING
        return await run_planning(state, workspace)

    if decision.action == ChatAction.REVIEW_DATA:
        state.chat.append(ChatMessage(role="assistant", content=decision.reply))
        state.status = Status.RUNNING
        return await run_data_review(state, workspace)

    if decision.action == ChatAction.BUILD_SKELETON:
        state.chat.append(ChatMessage(role="assistant", content=decision.reply))
        state.status = Status.RUNNING
        return await run_skeleton(state, workspace)

    if decision.action == ChatAction.BUILD_REPORT:
        state.chat.append(ChatMessage(role="assistant", content=decision.reply))
        state.status = Status.RUNNING
        has_report = bool(state.artifacts.report) or (
            workspace / get_settings().research.report_file
        ).exists()
        if wants_design_review(message) and has_report:
            return await rerender_and_review(state, workspace)
        rerender_only_markers = ("перерендери", "render report")
        if any(m in message.lower() for m in rerender_only_markers) and has_report:
            return await render_only(state, workspace)
        # Full rebuild only when no report yet, or explicit rebuild wording
        if has_report and not wants_full_report_rebuild(message):
            state.status = Status.WAITING_FOR_USER
            state.active_role = None
            state.chat.append(
                ChatMessage(
                    role="assistant",
                    content=(
                        "Отчёт уже есть. Точечная правка — напишите что добавить/поправить; "
                        "полный цикл — «переделай отчёт с нуля»; только HTML — «перерендери»; "
                        "дизайн — «проверь дизайн»."
                    ),
                )
            )
            return state
        return await run_coding(state, workspace)

    if decision.action == ChatAction.ADVANCE:
        if state.stage == Stage.PLAN_READY:
            return approve_plan(state)
        if state.stage in {Stage.WAITING_FOR_DATA, Stage.PLAN_APPROVED}:
            state.chat.append(ChatMessage(role="assistant", content=decision.reply))
            state.status = Status.RUNNING
            return await run_data_review(state, workspace)
        if state.stage in {Stage.DATA_READY, Stage.PLAN_ADJUSTED}:
            state.chat.append(ChatMessage(role="assistant", content=decision.reply))
            state.status = Status.RUNNING
            return await run_skeleton(state, workspace)
        if state.stage == Stage.SKELETON_READY:
            return approve_skeleton(state)
        if state.stage == Stage.SKELETON_APPROVED:
            state.chat.append(ChatMessage(role="assistant", content=decision.reply))
            state.status = Status.RUNNING
            return await run_coding(state, workspace)
        if state.stage == Stage.CODING_READY:
            return approve_coding(state)
        if state.stage == Stage.CODING_APPROVED:
            state.chat.append(
                ChatMessage(
                    role="assistant",
                    content="Отчёт уже утверждён. Можно точечно править код в чате.",
                )
            )
            return state
        state.chat.append(
            ChatMessage(
                role="assistant",
                content="Сейчас нечего утверждать этим сообщением — уточните, пожалуйста.",
            )
        )
        return state

    if decision.action == ChatAction.EDIT:
        state.status = Status.RUNNING
        if _editing_report(state, message):
            if wants_full_report_rebuild(message):
                state.chat.append(ChatMessage(role="assistant", content=decision.reply))
                return await run_coding(state, workspace)
            return await apply_coding_edit(
                state, workspace, message, reply_hint=decision.reply
            )

        if _editing_skeleton(state, message):
            if decision.artifact:
                settings = get_settings()
                text = strip_markdown_fence(decision.artifact.strip())
                path = write_workspace_text(workspace, settings.research.skeleton_file, text)
                state.artifacts.skeleton = str(path)
                state.stage = Stage.SKELETON_READY
                state.status = Status.WAITING_FOR_USER
                state.status_text = "Скелет обновлён"
                state.active_role = None
                state.chat.append(ChatMessage(role="assistant", content=decision.reply))
                return state
            return await apply_skeleton_edit(
                state, workspace, message, reply_hint=decision.reply
            )

        if not state.artifacts.analysis_plan:
            state.chat.append(
                ChatMessage(
                    role="assistant",
                    content="Плана ещё нет. Напишите, что нужно спланировать, или заполните brief.",
                )
            )
            state.status = Status.WAITING_FOR_USER
            return state
        if decision.artifact:
            settings = get_settings()
            plan_text = strip_markdown_fence(decision.artifact.strip())
            path = write_workspace_text(workspace, settings.research.plan_file, plan_text)
            state.artifacts.analysis_plan = str(path)
            if state.stage in {Stage.WAITING_FOR_DATA, Stage.DATA_READY, Stage.PLAN_ADJUSTED}:
                state.stage = Stage.PLAN_ADJUSTED
            else:
                state.stage = Stage.PLAN_READY
            state.status = Status.WAITING_FOR_USER
            state.status_text = "План обновлён"
            state.active_role = None
            state.chat.append(ChatMessage(role="assistant", content=decision.reply))
            return state
        return await apply_plan_edit(state, workspace, message, reply_hint=decision.reply)

    state.chat.append(ChatMessage(role="assistant", content=decision.reply))
    state.status = Status.WAITING_FOR_USER
    state.active_role = None
    return state
