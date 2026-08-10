"""Data review: profile CSVs → Lead compares to plan → Analyst validates → optional plan adjust."""

from __future__ import annotations

from pathlib import Path

from app.agents.runner import read_workspace_text, run_agent, write_workspace_text
from app.config import get_settings
from app.data_profile import profile_data_dir
from app.models import ChatMessage, ResearchState, Stage, Status
from app.orchestration.parse import parse_json_object, strip_markdown_fence
from app.orchestration.planning import brief_block

_VERDICT_RANK = {"ok": 0, "adjusted": 1, "blocked": 2}


def _stricter_verdict(a: str, b: str) -> str:
    return a if _VERDICT_RANK.get(a, 0) >= _VERDICT_RANK.get(b, 0) else b


async def run_data_review(state: ResearchState, workspace: Path) -> ResearchState:
    """Profile data/, write data-review.md, adjust analysis-plan.md if needed."""
    settings = get_settings()
    state.stage = Stage.DATA_REVIEW
    state.status = Status.RUNNING
    state.error = None

    data_dir = workspace / settings.workspace.data_dir
    profile_md = profile_data_dir(data_dir)
    review_path = write_workspace_text(
        workspace, settings.research.data_review_file, profile_md
    )
    state.artifacts.data_review = str(review_path)

    plan = read_workspace_text(workspace, settings.research.plan_file)
    brief = brief_block(state, workspace)

    result = await run_agent(
        state=state,
        agent_name="lead",
        stage=Stage.DATA_REVIEW,
        user_message=(
            "Сверь план исследования с реально доступными данными.\n"
            "Следуй skill data_review.\n"
            "Верни JSON:\n"
            "{\n"
            '  "reply": "краткое сообщение пользователю на русском",\n'
            '  "verdict": "ok" | "adjusted" | "blocked",\n'
            '  "plan_artifact": null или полный обновлённый analysis-plan.md\n'
            "}\n"
            "Если чего-то критичного нет (например platform) — скорректируй план "
            "под доступные поля (verdict=adjusted + plan_artifact). "
            "Не выдумывай колонки, которых нет в профиле.\n\n"
            f"## Brief + product context\n{brief}\n\n"
            f"## Current analysis plan\n{plan or '(нет плана)'}\n\n"
            f"## Data profile\n{profile_md}\n"
        ),
        summary="Lead: сверка плана с данными",
        json_mode=True,
        skill_override=[
            "data_review",
            "planning_pipeline",
            "research_design",
            "product_analytics",
            "artifact_edit",
        ],
    )

    try:
        data = parse_json_object(result.text)
    except ValueError:
        data = {
            "reply": (
                result.text.strip()[:1500]
                or "Не удалось разобрать ответ Lead по сверке данных."
            ),
            "verdict": "blocked",
            "plan_artifact": None,
        }

    reply = str(data.get("reply") or "Проверил данные.").strip()
    verdict = str(data.get("verdict") or "ok").strip().lower()
    if verdict not in _VERDICT_RANK:
        verdict = "blocked"
    plan_artifact = data.get("plan_artifact")

    analyst_result = await run_agent(
        state=state,
        agent_name="analyst",
        stage=Stage.DATA_REVIEW,
        user_message=(
            "Проверь решение Lead по сверке плана с данными. "
            "Lead не должен утверждать несуществующие поля или срезы.\n"
            "Верни JSON:\n"
            '{"agree": true|false, "concerns": "...", '
            '"verdict": null|"ok"|"adjusted"|"blocked"}\n'
            "verdict=null если полностью согласен с Lead.\n\n"
            f"## Lead reply\n{reply}\n\n"
            f"## Lead verdict\n{verdict}\n\n"
            f"## Brief\n{brief}\n\n"
            f"## Current analysis plan\n{plan or '(нет плана)'}\n\n"
            f"## Data profile\n{profile_md}\n"
        ),
        summary="Analyst: валидация сверки данных",
        json_mode=True,
        skill_override=[
            "data_review",
            "research_design",
            "statistics",
            "product_analytics",
        ],
    )

    try:
        analyst_data = parse_json_object(analyst_result.text)
    except ValueError:
        analyst_data = {"agree": True, "concerns": "", "verdict": None}

    analyst_verdict = analyst_data.get("verdict")
    if analyst_verdict is not None:
        analyst_verdict = str(analyst_verdict).strip().lower()
        if analyst_verdict in _VERDICT_RANK:
            verdict = _stricter_verdict(verdict, analyst_verdict)
    concerns = str(analyst_data.get("concerns") or "").strip()
    if concerns and not bool(analyst_data.get("agree", True)):
        reply = f"{reply}\n\nAnalyst: {concerns}".strip()

    if verdict == "adjusted" and plan_artifact:
        plan_text = strip_markdown_fence(str(plan_artifact).strip())
        plan_path = write_workspace_text(
            workspace, settings.research.plan_file, plan_text
        )
        state.artifacts.analysis_plan = str(plan_path)
        state.stage = Stage.PLAN_ADJUSTED
        state.status_text = "План скорректирован под доступные данные"
        reply = reply or "План обновлён под реальные поля в data/."
    elif verdict == "blocked":
        state.stage = Stage.WAITING_FOR_DATA
        state.status_text = "Данных недостаточно — нужно дособрать или уточнить"
    else:
        state.stage = Stage.DATA_READY
        state.status_text = "Данные сверены — можно собирать скелет («едем дальше»)"

    state.status = Status.WAITING_FOR_USER
    state.active_role = None
    state.data_verdict = verdict
    if verdict == "adjusted":
        reply = (
            (reply or "План обновлён под данные.")
            + " Когда будете готовы — «сделай скелет» или «едем дальше»."
        )
    elif verdict == "ok":
        reply = (
            (reply or "Данные согласованы с планом.")
            + " Дальше: «сделай скелет» или «едем дальше»."
        )
    elif verdict == "blocked":
        reply = (
            (reply or "Данных недостаточно для продолжения.")
            + " Дособерите CSV или уточните план."
        )
    state.chat.append(ChatMessage(role="assistant", content=reply))
    return state


def enter_waiting_for_data(state: ResearchState) -> ResearchState:
    state.stage = Stage.WAITING_FOR_DATA
    state.status = Status.WAITING_FOR_USER
    state.status_text = (
        "План утверждён. Положите CSV в data/ и напишите в чат «проверь данные»."
    )
    state.chat.append(
        ChatMessage(
            role="assistant",
            content=(
                "План утверждён. Соберите доступные выгрузки в `data/` "
                "(не обязательно всё из плана) и напишите «проверь данные» — "
                "сверу профиль файлов с планом и при необходимости подправлю план."
            ),
        )
    )
    return state
