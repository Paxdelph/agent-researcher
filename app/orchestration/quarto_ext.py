"""Ensure Quarto researcher-html extension is available in a research workspace."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SRC = _REPO_ROOT / "quarto" / "_extensions" / "researcher"
_DOCKER_SRC = Path("/app/quarto/_extensions/researcher")


def researcher_extension_source() -> Path:
    env = os.environ.get("QUARTO_RESEARCHER_EXT", "").strip()
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.extend([_DOCKER_SRC, _DEFAULT_SRC])
    for path in candidates:
        if (path / "_extension.yml").is_file():
            return path
    raise FileNotFoundError(
        "Quarto extension researcher не найден "
        f"(пробовали: {', '.join(str(p) for p in candidates)})"
    )


def ensure_researcher_extension(workspace: Path) -> Path:
    """Copy bundled extension into workspace/_extensions/researcher (idempotent)."""
    src = researcher_extension_source()
    dest = Path(workspace) / "_extensions" / "researcher"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest
