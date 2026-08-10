"""Agent runner: assemble role + skills and call LLM."""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings, resolve_prompt_path, resolve_skill_path
from app.models import (
    CallLogEntry,
    ChatMessage,
    ImagePart,
    LLMRequest,
    LLMResult,
    ResearchState,
    Stage,
    utcnow,
)
from app.providers import get_provider
from app.state import get_store

LANGUAGE_BLOCK = """# Language policy

All research artifacts and chat replies to the user must be in Russian.
JSON control fields (action names, keys) stay in English as specified by skills.
Do not invent data fields that are not available or stated in the brief.
"""

AGENT_LABELS = {
    "lead": "Lead",
    "analyst": "Analyst",
    "storyteller": "Storyteller",
    "bi_analyst": "BI Analyst",
    "coder": "Coder",
    "designer": "Designer",
}


def agent_label(agent_name: str) -> str:
    return AGENT_LABELS.get(agent_name, agent_name.replace("_", " ").title())


def progress_chat_line(agent_name: str, summary: str | None = None) -> str:
    label = agent_label(agent_name)
    task = (summary or "").strip()
    if task:
        for prefix in (f"{agent_name}:", f"{label}:", f"{agent_name} —", f"{label} —"):
            if task.lower().startswith(prefix.lower()):
                task = task[len(prefix) :].strip()
                break
    if task:
        return f"{label} работает: {task}…"
    return f"{label} работает…"


def load_role_prompt(agent_name: str) -> str:
    settings = get_settings()
    agent = settings.agents[agent_name]
    return resolve_prompt_path(agent.prompt).read_text(encoding="utf-8")


def load_skills(skill_names: list[str]) -> str:
    parts: list[str] = []
    for name in skill_names:
        path = resolve_skill_path(name)
        parts.append(f"## Skill: {name}\n\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts)


def assemble_system(agent_name: str, skill_override: list[str] | None = None) -> str:
    settings = get_settings()
    agent = settings.agents[agent_name]
    role = load_role_prompt(agent_name)
    skills = load_skills(skill_override if skill_override is not None else agent.skills)
    blocks = [role.strip(), LANGUAGE_BLOCK.strip()]
    if skills:
        blocks.append("# Skills\n\n" + skills)
    return "\n\n---\n\n".join(blocks)


async def run_agent(
    *,
    state: ResearchState,
    agent_name: str,
    stage: Stage,
    user_message: str,
    summary: str | None = None,
    json_mode: bool = False,
    skill_override: list[str] | None = None,
    announce: bool = True,
    images: list[ImagePart] | None = None,
) -> LLMResult:
    settings = get_settings()
    agent = settings.agents[agent_name]
    if not agent.enabled:
        raise RuntimeError(f"Agent '{agent_name}' is disabled in config")

    system = assemble_system(agent_name, skill_override=skill_override)
    estimated = (len(system) + len(user_message)) // 4
    max_total = settings.limits.max_total_tokens
    if max_total > 0 and state.usage.total_tokens + estimated > max_total:
        raise RuntimeError("Token budget exceeded")
    max_single = settings.limits.max_single_call_input_tokens
    if max_single > 0 and estimated > max_single:
        raise RuntimeError(
            f"Single call input estimate {estimated} exceeds "
            f"max_single_call_input_tokens={max_single}"
        )

    request = LLMRequest(
        role=agent_name,
        stage=stage,
        system=system,
        user=user_message,
        model=agent.model,
        max_output_tokens=agent.max_output_tokens,
        json_mode=json_mode,
        images=list(images or []),
    )
    provider = get_provider(agent.provider)
    store = get_store()

    state.active_role = f"{agent_name} / {agent.provider}"
    state.status_text = summary or f"{agent_label(agent_name)} работает…"
    if announce:
        state.chat.append(
            ChatMessage(role="system", content=progress_chat_line(agent_name, summary))
        )

    started = utcnow()
    entry = CallLogEntry(
        run_id=state.run_id,
        created_at=started,
        stage=stage,
        role=agent_name,
        provider=agent.provider,
        model=agent.model,
        status="running",
        summary=summary,
    )
    store.append_log(entry.model_dump())
    store.save(state)

    try:
        result = await provider.complete(request)
    except Exception as exc:  # noqa: BLE001
        failed = CallLogEntry(
            id=entry.id,
            run_id=state.run_id,
            created_at=started,
            stage=stage,
            role=agent_name,
            provider=agent.provider,
            model=agent.model,
            status="failed",
            error=str(exc),
            summary=summary,
        )
        store.update_log(entry.id, failed.model_dump())
        raise

    state.usage.add(result.provider, result.input_tokens, result.output_tokens)
    done = CallLogEntry(
        id=entry.id,
        run_id=state.run_id,
        created_at=started,
        stage=stage,
        role=agent_name,
        provider=result.provider,
        model=result.model,
        status="completed",
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        summary=summary,
        prompt_preview=user_message[:500] if settings.app.store_full_prompts else None,
        response_preview=result.text[:500] if settings.app.store_full_prompts else None,
    )
    store.update_log(entry.id, done.model_dump())
    store.save(state)
    return result


def write_workspace_text(workspace: Path, relative: str, content: str) -> Path:
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    return path


def read_workspace_text(workspace: Path, relative: str) -> str:
    path = workspace / relative
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
