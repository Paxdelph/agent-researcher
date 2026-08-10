"""Anthropic provider."""

from __future__ import annotations

import os
import re
import time

from anthropic import AsyncAnthropic

from app.models import LLMRequest, LLMResult

_TEMPERATURE_UNSUPPORTED = re.compile(
    r"claude-(sonnet|opus|haiku|fable)-(\d+)(?:-(\d+))?$",
    re.IGNORECASE,
)


def _supports_temperature(model: str) -> bool:
    if re.search(r"-\d{8}$", model):
        return True
    match = _TEMPERATURE_UNSUPPORTED.match(model.strip())
    if not match:
        return True
    major = int(match.group(2))
    minor = int(match.group(3)) if match.group(3) else 0
    if major >= 5:
        return False
    if major == 4 and minor >= 6:
        return False
    return True


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None = None, timeout: float = 300.0) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = AsyncAnthropic(api_key=key, timeout=timeout)

    async def complete(self, request: LLMRequest) -> LLMResult:
        started = time.perf_counter()
        system = request.system
        if request.json_mode:
            system = (
                system
                + "\n\nRespond with a single valid JSON object only. No markdown fences."
            )

        content: list[dict] = []
        for img in request.images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.media_type,
                        "data": img.data_base64,
                    },
                }
            )
        content.append({"type": "text", "text": request.user})

        kwargs: dict = {
            "model": request.model,
            "max_tokens": request.max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": content}],
        }
        if _supports_temperature(request.model):
            kwargs["temperature"] = request.temperature

        response = await self.client.messages.create(**kwargs)
        latency_ms = int((time.perf_counter() - started) * 1000)
        text_parts = [
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ]
        text = "\n".join(text_parts)
        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0
        return LLMResult(
            text=text,
            provider=self.name,
            model=request.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
        )
