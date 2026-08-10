"""Planning pipeline: Lead draft → Analyst critique → Lead synthesis."""

from __future__ import annotations

from pathlib import Path

from app.agents.runner import read_workspace_text, run_agent, write_workspace_text
from app.config import get_settings
from app.models import ChatMessage, ResearchState, Stage, Status
from app.orchestration.parse import parse_chat_decision, strip_markdown_fence
from app.workspace_paths import company_context_path


def brief_block(state: ResearchState, workspace: Path | None = None) -> str:
    settings = get_settings()
    parts = [
        f"Research question:\n{state.research_question}\n",
        f"Business context (brief form):\n{state.business_context or '(none)'}\n",
    ]
    context_path = company_context_path(settings)
    if context_path.exists():
        text = context_path.read_text(encoding="utf-8").strip()
        parts.append(
            f"Product / company context (shared, `{context_path}`):\n{text}\n"
        )
    else:
        parts.append(
            f"Product / company context (shared, `{context_path}`): (file missing)\n"
        )
    return "\n".join(parts)


async def run_planning(state: ResearchState, workspace: Path) -> ResearchState:
    settings = get_settings()
    brief = brief_block(state, workspace)

    state.stage = Stage.PLANNING
    state.status = Status.RUNNING
    state.error = None

    draft = await run_agent(
        state=state,
        agent_name="lead",
        stage=Stage.PLANNING,
        user_message=(
            "Напиши черновик исследовательского дизайна по брифу.\n"
            "Следуй skill planning_pipeline (структура плана).\n"
            "Это ещё не финальный analysis-plan.md — черновик для критики Analyst.\n\n"
            + brief
        ),
        summary="Lead: черновик дизайна",
        skill_override=[
            "planning_pipeline",
            "research_design",
            "product_analytics",
        ],
    )
    state.lead_draft = draft.text.strip()

    critique = await run_agent(
        state=state,
        agent_name="analyst",
        stage=Stage.PLANNING,
        user_message=(
            "Скритикуй черновик Lead. Укажи слабые гипотезы, overclaim, "
            "пропущенные поля данных и риски. Предложи конкретные улучшения.\n\n"
            f"## Brief\n{brief}\n\n"
            f"## Lead draft\n{state.lead_draft}\n"
        ),
        summary="Analyst: критика черновика",
        skill_override=[
            "planning_pipeline",
            "research_design",
            "statistics",
            "product_analytics",
        ],
    )
    state.analyst_critique = critique.text.strip()

    synthesis = await run_agent(
        state=state,
        agent_name="lead",
        stage=Stage.PLANNING,
        user_message=(
            "Синтезируй финальный analysis-plan.md (Markdown) с учётом критики Analyst.\n"
            "Секции и текст — на русском, по skill planning_pipeline.\n"
            "Верни только содержимое файла, без JSON и без пояснений вне markdown.\n\n"
            f"## Brief\n{brief}\n\n"
            f"## Lead draft\n{state.lead_draft}\n\n"
            f"## Analyst critique\n{state.analyst_critique}\n"
        ),
        summary="Lead: финальный analysis-plan.md",
        skill_override=[
            "planning_pipeline",
            "research_design",
            "product_analytics",
        ],
    )

    plan_text = strip_markdown_fence(synthesis.text.strip())
    plan_path = write_workspace_text(workspace, settings.research.plan_file, plan_text)
    state.artifacts.analysis_plan = str(plan_path)
    state.stage = Stage.PLAN_READY
    state.status = Status.WAITING_FOR_USER
    state.status_text = "План готов — правьте в чате или скажите «едем дальше»"
    state.active_role = None
    state.chat.append(
        ChatMessage(
            role="assistant",
            content=(
                "План исследования готов (`analysis-plan.md`). "
                "Можно точечно поправить в чате или написать «едем дальше»."
            ),
        )
    )
    return state


async def apply_plan_edit(
    state: ResearchState,
    workspace: Path,
    user_message: str,
    reply_hint: str | None = None,
) -> ResearchState:
    """Incremental edit of analysis-plan.md via Lead + artifact_edit skill."""
    settings = get_settings()
    existing = read_workspace_text(workspace, settings.research.plan_file)
    if not existing:
        raise RuntimeError("analysis-plan.md ещё нет — сначала нужно спланировать")

    arts = ""
    review = read_workspace_text(workspace, settings.research.data_review_file).strip()
    if review:
        arts = (
            f"\n## Data review (`{settings.research.data_review_file}`)\n{review}\n"
        )

    result = await run_agent(
        state=state,
        agent_name="lead",
        stage=state.stage,
        user_message=(
            "Внеси инкрементальную правку в analysis-plan.md по запросу пользователя.\n"
            "Верни JSON: {\"action\":\"edit\",\"reply\":\"...\",\"artifact\":\"<полный markdown>\"}.\n\n"
            f"## Current plan\n{existing}\n\n"
            f"## User message\n{user_message}\n"
            + (f"\n## Reply hint\n{reply_hint}\n" if reply_hint else "")
            + f"\n## Brief\n{brief_block(state, workspace)}"
            + arts
        ),
        summary="Lead: правка плана",
        json_mode=True,
        skill_override=[
            "chat_control",
            "artifact_edit",
            "planning_pipeline",
            "research_design",
            "product_analytics",
        ],
    )
    decision = parse_chat_decision(result.text)
    if decision.action.value == "clarify" or not decision.artifact:
        state.chat.append(ChatMessage(role="assistant", content=decision.reply))
        state.status = Status.WAITING_FOR_USER
        state.active_role = None
        state.status_text = "Нужно уточнение по правке"
        return state

    plan_text = strip_markdown_fence(decision.artifact.strip())
    plan_path = write_workspace_text(workspace, settings.research.plan_file, plan_text)
    state.artifacts.analysis_plan = str(plan_path)
    state.stage = Stage.PLAN_READY
    state.status = Status.WAITING_FOR_USER
    state.status_text = "План обновлён"
    state.active_role = None
    state.chat.append(ChatMessage(role="assistant", content=decision.reply))
    return state


def approve_plan(state: ResearchState) -> ResearchState:
    from app.orchestration.data_review import enter_waiting_for_data

    return enter_waiting_for_data(state)
