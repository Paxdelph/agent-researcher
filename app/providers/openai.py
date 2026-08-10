"""OpenAI provider."""

from __future__ import annotations

import os
import re
import time

from openai import AsyncOpenAI

from app.models import LLMRequest, LLMResult

# gpt-5*, o1/o3/o4* — use max_completion_tokens; temperature often unsupported.
_NEW_PARAM_MODELS = re.compile(
    r"^(gpt-5|o[1-9])",
    re.IGNORECASE,
)


def _uses_max_completion_tokens(model: str) -> bool:
    return bool(_NEW_PARAM_MODELS.match(model.strip()))


def _supports_temperature(model: str) -> bool:
    return not _uses_max_completion_tokens(model)


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None, timeout: float = 300.0) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = AsyncOpenAI(api_key=key, timeout=timeout)

    async def complete(self, request: LLMRequest) -> LLMResult:
        started = time.perf_counter()
        user_content: str | list = request.user
        if request.images:
            # OpenAI path used rarely for vision here; keep text + note.
            user_content = (
                request.user
                + f"\n\n[{len(request.images)} image(s) attached — "
                "use an Anthropic vision model for visual review.]"
            )
        kwargs: dict = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": user_content},
            ],
        }
        if _uses_max_completion_tokens(request.model):
            kwargs["max_completion_tokens"] = request.max_output_tokens
        else:
            kwargs["max_tokens"] = request.max_output_tokens
        if _supports_temperature(request.model):
            kwargs["temperature"] = request.temperature
        if request.json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**kwargs)
        latency_ms = int((time.perf_counter() - started) * 1000)
        choice = response.choices[0].message.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        return LLMResult(
            text=choice,
            provider=self.name,
            model=request.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
        )
