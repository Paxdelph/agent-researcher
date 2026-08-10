"""Shared artifact context blocks for orchestration prompts."""

from __future__ import annotations

from pathlib import Path

from app.agents.runner import read_workspace_text
from app.config import get_settings
from app.data_profile import profile_data_dir
from app.models import ResearchState, Stage
from app.workspace_paths import company_context_path


def artifact_excerpt(text: str, max_chars: int = 16000) -> str:
    """Keep head + tail for long artifacts (Designer / chat router)."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    head = (max_chars * 2) // 3
    tail = max_chars - head - 40
    return (
        text[:head]
        + "\n\n<!-- … середина опущена … -->\n\n"
        + text[-tail:]
    )


def artifacts_block(
    workspace: Path,
    *,
    include_plan: bool = True,
    include_data_review: bool = True,
) -> str:
    """Plan + data-review + shared company context."""
    settings = get_settings()
    parts: list[str] = []
    if include_plan:
        text = read_workspace_text(workspace, settings.research.plan_file).strip()
        parts.append(
            f"## Analysis plan (`{settings.research.plan_file}`)\n"
            f"{text or '(файл отсутствует)'}\n"
        )
    if include_data_review:
        text = read_workspace_text(workspace, settings.research.data_review_file).strip()
        parts.append(
            f"## Data review (`{settings.research.data_review_file}`)\n"
            f"{text or '(файл отсутствует)'}\n"
        )

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


def coding_context_block(workspace: Path, *, include_profile: bool = True) -> str:
    """Context for Coder: skeleton, plan, data-review, company, CSV list, fresh profile."""
    settings = get_settings()
    parts: list[str] = []
    for label, rel in (
        ("Skeleton", settings.research.skeleton_file),
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

    data_dir = workspace / settings.workspace.data_dir
    if data_dir.exists():
        files = sorted(p.name for p in data_dir.glob("*.csv"))
        parts.append(
            "## Data CSV files\n"
            + (", ".join(f"`data/{n}`" for n in files) if files else "(нет csv)")
            + "\n"
        )
    if include_profile and data_dir.exists():
        parts.append(
            "## Fresh data profile (from disk)\n"
            f"{profile_data_dir(data_dir)}\n"
        )
    return "\n".join(parts)


def current_artifact_preview(
    state: ResearchState,
    workspace: Path,
    *,
    max_chars: int = 4000,
) -> str:
    """Snippet of the artifact most likely being edited (chat router)."""
    settings = get_settings()
    stage = state.stage
    if stage in {
        Stage.CODING,
        Stage.CODING_READY,
        Stage.CODING_APPROVED,
    }:
        rel = settings.research.report_file
    elif stage in {Stage.SKELETON, Stage.SKELETON_READY, Stage.SKELETON_APPROVED}:
        rel = settings.research.skeleton_file
    else:
        rel = settings.research.plan_file

    text = read_workspace_text(workspace, rel).strip()
    if not text:
        return f"({rel} отсутствует)"
    return artifact_excerpt(text, max_chars=max_chars)
