"""Parse model JSON payloads."""

from __future__ import annotations

import json
import re
from typing import Any

from app.models import ChatAction, ChatDecision


def parse_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 2:
            block = parts[1]
            raw = block.split("\n", 1)[1] if "\n" in block else block
            if raw.lstrip().startswith("json"):
                raw = raw.lstrip()[4:].lstrip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    raise ValueError("Model did not return a JSON object")


def parse_chat_decision(text: str) -> ChatDecision:
    data = parse_json_object(text)
    action_raw = str(data.get("action", "clarify")).strip().lower()
    try:
        action = ChatAction(action_raw)
    except ValueError:
        action = ChatAction.CLARIFY
    reply = str(data.get("reply") or "").strip() or "Уточните, пожалуйста."
    artifact = data.get("artifact")
    if artifact is not None:
        artifact = str(artifact)
        if not artifact.strip():
            artifact = None
    return ChatDecision(action=action, reply=reply, artifact=artifact)


def strip_markdown_fence(text: str) -> str:
    raw = text.strip()
    if not raw.startswith("```"):
        return raw
    parts = raw.split("```")
    if len(parts) < 2:
        return raw
    block = parts[1]
    if "\n" in block:
        first, rest = block.split("\n", 1)
        if first.strip().lower() in {"markdown", "md", "json"}:
            return rest.strip()
        return block.strip()
    return block.strip()


def extract_qmd(text: str) -> str:
    """Strip a single outer fence without breaking inner ```{r} chunks."""
    raw = text.strip()
    if not raw.startswith("```"):
        return raw
    first_nl = raw.find("\n")
    if first_nl == -1:
        return raw
    body = raw[first_nl + 1 :]
    stripped = body.rstrip()
    if stripped.endswith("```"):
        body = stripped[:-3].rstrip()
    return body
