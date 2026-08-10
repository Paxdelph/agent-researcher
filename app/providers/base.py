from __future__ import annotations

from typing import Protocol

from app.models import LLMRequest, LLMResult


class LLMProvider(Protocol):
    name: str

    async def complete(self, request: LLMRequest) -> LLMResult:
        ...
