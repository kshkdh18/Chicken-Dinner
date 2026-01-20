from __future__ import annotations

from typing import Any

import httpx


def _parse_response_json(data: dict[str, Any]) -> str:
    # OpenAI Chat Completions compatible
    try:
        return (
            data["choices"][0]["message"].get("content")
            or data["choices"][0].get("text")
        )
    except Exception:
        pass
    # OpenAI Responses or generic
    if "output" in data:
        return str(data["output"])
    if "result" in data:
        return str(data["result"])
    return str(data)


async def call_target(
    endpoint: str,
    model: str,
    prompt: str,
    timeout_s: float = 30.0,
) -> tuple[str, dict[str, Any]]:
    """POST a chat-style payload to an OpenAI-compatible endpoint.

    Returns: (response_text, raw_json)
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(endpoint, json=payload)
        r.raise_for_status()
        data = r.json()
        text = _parse_response_json(data)
        return text, data

