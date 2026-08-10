"""Report skeleton: Lead → Analyst → Lead → Storyteller → BI Analyst."""

from __future__ import annotations

from pathlib import Path

from app.agents.runner import read_workspace_text, run_agent, write_workspace_text
from app.config import get_settings
from app.models import ChatMessage, ResearchState, Stage, Status
from app.orchestration.parse import parse_chat_decision, strip_markdown_fence
from app.orchestration.planning import brief_block
from app.workspace_paths import company_context_path


def _artifacts_block(workspace: Path) -> str:
    settings = get_settings()
    parts: list[str] = []
    for label, rel in (
        ("Analysis plan", settings.research.plan_file),
        ("Data review", settings.research.data_review_file),
    ):
        text = read_workspace_text(workspace, rel).strip()
        parts.append(f"## {label} (`{rel}`)\n{text or '(файл отсутствует)'}\n")

    ctx_path = company_context_path(settings)
    if ctx_path.exists():
        ctx_text = ctx_path.read_text(encoding="utf-8").strip()
    else:
        ctx_text = ""
    parts.append(
        f"## Product context (company) (`{ctx_path}`)\n"
        f"{ctx_text or '(файл отсутствует)'}\n"
    )
    return "\n".join(parts)


async def run_skeleton(state: ResearchState, workspace: Path) -> ResearchState:
    settings = get_settings()
    state.stage = Stage.SKELETON
    state.status = Status.RUNNING
    state.error = None

    brief = brief_block(state, workspace)
    arts = _artifacts_block(workspace)

    draft = await run_agent(
        state=state,
        agent_name="lead",
        stage=Stage.SKELETON,
        user_message=(
            "Составь черновик скелета отчёта (`skeleton.md`) по skill report_skeleton.\n"
            "Опирайся только на план и доступные данные; не выдумывай срезы.\n"
            "Верни только markdown скелета.\n\n"
            f"## Brief\n{brief}\n\n"
            f"{arts}\n"
        ),
        summary="Lead: черновик скелета",
        skill_override=[
            "report_skeleton",
            "research_design",
            "product_analytics",
        ],
    )
    state.skeleton_draft = draft.text.strip()

    critique = await run_agent(
        state=state,
        agent_name="analyst",
        stage=Stage.SKELETON,
        user_message=(
            "Скритикуй черновик скелета по skill report_skeleton (раздел критики).\n"
            "Укажи дыры относительно RQ, нереализуемые графики, дубли, слабые переходы.\n\n"
            f"## Brief\n{brief}\n\n"
            f"{arts}\n"
            f"## Skeleton draft\n{state.skeleton_draft}\n"
        ),
        summary="Analyst: критика скелета",
        skill_override=[
            "report_skeleton",
            "research_design",
            "statistics",
            "product_analytics",
        ],
    )
    state.skeleton_critique = critique.text.strip()

    revised = await run_agent(
        state=state,
        agent_name="lead",
        stage=Stage.SKELETON,
        user_message=(
            "Учти критику Analyst и выдай исправленный полный `skeleton.md`.\n"
            "Только markdown, без JSON.\n\n"
            f"## Brief\n{brief}\n\n"
            f"{arts}\n"
            f"## Draft\n{state.skeleton_draft}\n\n"
            f"## Analyst critique\n{state.skeleton_critique}\n"
        ),
        summary="Lead: правка скелета",
        skill_override=[
            "report_skeleton",
            "research_design",
            "product_analytics",
            "artifact_edit",
        ],
    )
    mid_text = strip_markdown_fence(revised.text.strip())

    story = await run_agent(
        state=state,
        agent_name="storyteller",
        stage=Stage.SKELETON,
        user_message=(
            "Пересобери скелет как единую историю по skill storytelling.\n"
            "Сохрани формат report_skeleton. Верни только полный markdown `skeleton.md`.\n\n"
            f"## Central brief\n{brief}\n\n"
            f"## Plan / data context\n{arts}\n"
            f"## Current skeleton\n{mid_text}\n"
        ),
        summary="Storyteller: narrative pass",
        skill_override=[
            "storytelling",
            "report_skeleton",
            "product_analytics",
        ],
    )
    story_text = strip_markdown_fence(story.text.strip())

    viz = await run_agent(
        state=state,
        agent_name="bi_analyst",
        stage=Stage.SKELETON,
        user_message=(
            "Сделай viz-pass по skill viz_craft: уточни типы графиков/таблиц и спеки под тезисы.\n"
            "Не меняй RQ и методологию, не выдумывай поля. Верни полный `skeleton.md`.\n\n"
            f"## Brief\n{brief}\n\n"
            f"{arts}\n"
            f"## Skeleton after storytelling\n{story_text}\n"
        ),
        summary="BI Analyst: viz-pass скелета",
        skill_override=[
            "viz_craft",
            "report_skeleton",
            "product_analytics",
        ],
    )

    final_text = strip_markdown_fence(viz.text.strip())
    path = write_workspace_text(workspace, settings.research.skeleton_file, final_text)
    state.artifacts.skeleton = str(path)
    state.stage = Stage.SKELETON_READY
    state.status = Status.WAITING_FOR_USER
    state.status_text = "Скелет готов — править в чате/UI или «едем дальше»"
    state.active_role = None
    state.chat.append(
        ChatMessage(
            role="assistant",
            content=(
                "Скелет отчёта готов (`skeleton.md`): "
                "Lead → Analyst → Lead → Storyteller → BI Analyst. "
                "Можно точечно поправить или написать «едем дальше»."
            ),
        )
    )
    return state


async def apply_skeleton_edit(
    state: ResearchState,
    workspace: Path,
    user_message: str,
    reply_hint: str | None = None,
) -> ResearchState:
    settings = get_settings()
    existing = read_workspace_text(workspace, settings.research.skeleton_file)
    if not existing:
        raise RuntimeError("skeleton.md ещё нет — сначала соберите скелет")

    result = await run_agent(
        state=state,
        agent_name="lead",
        stage=state.stage,
        user_message=(
            "Внеси инкрементальную правку в skeleton.md по запросу пользователя.\n"
            "Верни JSON: {\"action\":\"edit\",\"reply\":\"...\",\"artifact\":\"<полный markdown>\"}.\n\n"
            f"## Current skeleton\n{existing}\n\n"
            f"## User message\n{user_message}\n"
            + (f"\n## Reply hint\n{reply_hint}\n" if reply_hint else "")
            + f"\n## Brief\n{brief_block(state, workspace)}\n"
        ),
        summary="Lead: правка скелета",
        json_mode=True,
        skill_override=[
            "chat_control",
            "artifact_edit",
            "report_skeleton",
            "storytelling",
        ],
    )
    decision = parse_chat_decision(result.text)
    if decision.action.value == "clarify" or not decision.artifact:
        state.chat.append(ChatMessage(role="assistant", content=decision.reply))
        state.status = Status.WAITING_FOR_USER
        state.active_role = None
        state.status_text = "Нужно уточнение по правке скелета"
        return state

    text = strip_markdown_fence(decision.artifact.strip())
    path = write_workspace_text(workspace, settings.research.skeleton_file, text)
    state.artifacts.skeleton = str(path)
    state.stage = Stage.SKELETON_READY
    state.status = Status.WAITING_FOR_USER
    state.status_text = "Скелет обновлён"
    state.active_role = None
    state.chat.append(ChatMessage(role="assistant", content=decision.reply))
    return state


def approve_skeleton(state: ResearchState) -> ResearchState:
    state.stage = Stage.SKELETON_APPROVED
    state.status = Status.WAITING_FOR_USER
    state.status_text = "Скелет утверждён — «собери отчёт» или «едем дальше»"
    state.active_role = None
    state.chat.append(
        ChatMessage(
            role="assistant",
            content=(
                "Скелет утверждён. Дальше Coder соберёт Quarto/R отчёт и Designer "
                "проверит вёрстку — напишите «собери отчёт» или «едем дальше»."
            ),
        )
    )
    return state
