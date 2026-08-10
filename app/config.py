"""Configuration loading."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

from app.models import AppSettings

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"
PACKAGE_PROMPTS = Path(__file__).resolve().parent / "prompts"
PACKAGE_SKILLS = Path(__file__).resolve().parent / "skills"


def load_settings(config_path: str | Path | None = None) -> AppSettings:
    path = Path(config_path) if config_path else Path(
        os.environ.get("AGENT_RESEARCHER_CONFIG", DEFAULT_CONFIG_PATH)
    )
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        example = ROOT / "config.example.yaml"
        if example.exists():
            path = example
        else:
            raise FileNotFoundError(f"Config not found: {path}")

    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    workspace = raw.setdefault("workspace", {})
    if os.environ.get("WORKSPACE_PATH"):
        workspace["path"] = os.environ["WORKSPACE_PATH"]
    if os.environ.get("CONTEXT_PATH"):
        workspace["context_path"] = os.environ["CONTEXT_PATH"]
    app = raw.setdefault("app", {})
    if os.environ.get("STATE_DIR"):
        app["state_dir"] = os.environ["STATE_DIR"]

    return AppSettings.model_validate(raw)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return load_settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()


def resolve_prompt_path(relative: str) -> Path:
    name = Path(relative).name
    candidate = PACKAGE_PROMPTS / name
    if candidate.exists():
        return candidate
    path = Path(relative)
    if path.is_absolute():
        return path
    return ROOT / path


def resolve_skill_path(skill_name: str) -> Path:
    path = PACKAGE_SKILLS / f"{skill_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill not found: {skill_name}")
    return path
