"""Resolve research vs company-shared file paths."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.config import get_settings
from app.models import AppSettings


class _ArtifactLike(Protocol):
    id: str
    file: str


def company_context_path(settings: AppSettings | None = None) -> Path:
    """Shared company context — one file for all researches of an analyst."""
    settings = settings or get_settings()
    raw = getattr(settings.workspace, "context_path", None) or "/company/context.md"
    return Path(raw)


def research_file(settings: AppSettings, filename: str) -> Path:
    return Path(settings.workspace.path) / filename


def artifact_disk_path(
    artifact: _ArtifactLike,
    settings: AppSettings | None = None,
) -> Path:
    settings = settings or get_settings()
    if artifact.id == "context":
        return company_context_path(settings)
    return research_file(settings, artifact.file)


def path_for_artifact_id(artifact_id: str, settings: AppSettings | None = None) -> Path | None:
    settings = settings or get_settings()
    for item in settings.research.artifacts:
        if item.id == artifact_id:
            return artifact_disk_path(item, settings)
    return None
