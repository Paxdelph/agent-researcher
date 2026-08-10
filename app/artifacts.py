"""Workspace artifact catalog for preview tabs."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from app.config import get_settings
from app.markdown_render import render_markdown
from app.models import ResearchState, Stage
from app.workspace_paths import artifact_disk_path, company_context_path


class ArtifactDef(BaseModel):
    id: str
    file: str
    label: str
    editable: bool = True


class ArtifactTab(BaseModel):
    id: str
    file: str
    label: str
    editable: bool
    exists: bool
    active: bool


DEFAULT_ARTIFACTS: list[ArtifactDef] = [
    ArtifactDef(id="context", file="context.md", label="Контекст"),
    ArtifactDef(id="plan", file="analysis-plan.md", label="План"),
    ArtifactDef(id="data_review", file="data-review.md", label="Сверка", editable=False),
    ArtifactDef(id="skeleton", file="skeleton.md", label="Скелет"),
    ArtifactDef(id="report", file="report.qmd", label="Quarto"),
    ArtifactDef(id="report_html", file="report.html", label="HTML", editable=False),
]


def configured_artifacts() -> list[ArtifactDef]:
    settings = get_settings()
    configured = settings.research.artifacts or []
    if configured:
        return [
            ArtifactDef(
                id=a.id,
                file=a.file,
                label=a.label,
                editable=a.editable,
            )
            for a in configured
        ]

    arts = [a.model_copy() for a in DEFAULT_ARTIFACTS]
    for a in arts:
        if a.id == "plan":
            a.file = settings.research.plan_file
        elif a.id == "context":
            a.file = "context.md"
        elif a.id == "skeleton":
            a.file = settings.research.skeleton_file
        elif a.id == "report":
            a.file = settings.research.report_file
        elif a.id == "report_html":
            a.file = settings.research.report_html_file
    return arts


def resolve_artifact(artifact_id: str | None) -> ArtifactDef:
    arts = configured_artifacts()
    if artifact_id:
        for a in arts:
            if a.id == artifact_id or a.file == artifact_id:
                return a
    for a in arts:
        if a.id == "plan":
            return a
    return arts[0]


def editable_filenames() -> set[str]:
    return {a.file for a in configured_artifacts() if a.editable}


def build_tabs(workspace: Path, active: ArtifactDef) -> list[ArtifactTab]:
    settings = get_settings()
    tabs: list[ArtifactTab] = []
    for a in configured_artifacts():
        disk = artifact_disk_path(a, settings)
        tabs.append(
            ArtifactTab(
                id=a.id,
                file=a.file,
                label=a.label,
                editable=a.editable,
                exists=disk.exists(),
                active=(a.id == active.id),
            )
        )
    return tabs


def load_preview(state: ResearchState, artifact_id: str | None = None) -> dict:
    settings = get_settings()
    workspace = Path(settings.workspace.path)
    active = resolve_artifact(artifact_id)
    path = artifact_disk_path(active, settings)

    preview = {
        "id": active.id,
        "name": active.file,
        "label": active.label,
        "editable": active.editable,
        "exists": False,
        "html": None,
        "text": None,
        "error": None,
        "kind": "markdown",
        "iframe_src": None,
    }

    if path.exists():
        preview["exists"] = True
        try:
            text = path.read_text(encoding="utf-8")
            preview["text"] = text
            suffix = path.suffix.lower()
            if suffix in {".html", ".htm"}:
                preview["kind"] = "iframe"
                mtime = int(path.stat().st_mtime)
                preview["iframe_src"] = f"/files/{active.file}?t={mtime}"
                preview["html"] = None
            elif suffix in {".qmd", ".r", ".py", ".sql"}:
                preview["kind"] = "code"
                preview["html"] = f"<pre class='raw-file'>{_escape(text)}</pre>"
            elif suffix in {".md", ".markdown", ".txt"}:
                preview["kind"] = "markdown"
                preview["html"] = render_markdown(text)
            else:
                preview["kind"] = "code"
                preview["html"] = f"<pre class='raw-file'>{_escape(text)}</pre>"
        except OSError as exc:
            preview["error"] = str(exc)
            preview["exists"] = False
    else:
        if active.id == "plan" and state.stage in {Stage.BRIEF, Stage.PLANNING}:
            preview["error"] = "План ещё не создан"
        elif active.id == "context":
            ctx = company_context_path(settings)
            preview["error"] = (
                f"Общий контекст компании пока нет "
                f"(`{ctx}` — общий для всех рисерчей аналитика)"
            )
        elif active.id in {"report", "report_html"} and state.stage in {
            Stage.BRIEF,
            Stage.PLANNING,
            Stage.PLAN_READY,
            Stage.PLAN_APPROVED,
            Stage.WAITING_FOR_DATA,
            Stage.DATA_REVIEW,
            Stage.DATA_READY,
            Stage.PLAN_ADJUSTED,
            Stage.SKELETON,
            Stage.SKELETON_READY,
            Stage.SKELETON_APPROVED,
        }:
            preview["error"] = f"Файл {active.file} появится после этапа кодирования"
        else:
            preview["error"] = f"Файл {active.file} пока нет в папке рисерча"

    return {
        "preview": preview,
        "tabs": build_tabs(workspace, active),
        "artifact_id": active.id,
    }


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
