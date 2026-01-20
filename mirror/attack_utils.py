from __future__ import annotations

import base64
import codecs
from typing import Dict, Optional

import httpx

from .mirror_settings import MirrorSettings


def _leetspeak(text: str) -> str:
    table = str.maketrans({"a": "@", "e": "3", "i": "1", "o": "0", "s": "5"})
    return text.translate(table)


def _spacing(text: str) -> str:
    return " ".join(list(text))


def mutate_prompt(prompt: str, method: str) -> Optional[str]:
    if method == "base64":
        return base64.b64encode(prompt.encode("utf-8")).decode("utf-8")
    if method == "rot13":
        return codecs.encode(prompt, "rot_13")
    if method == "spacing":
        return _spacing(prompt)
    if method == "leetspeak":
        return _leetspeak(prompt)
    return None


def call_target_sync(
    settings: MirrorSettings,
    message: str,
    endpoint: str | None = None,
    endpoint_format: str | None = None,
    messages: list[dict] | None = None,
) -> Dict[str, object]:
    url = endpoint or settings.endpoint
    fmt = endpoint_format or settings.endpoint_format
    timeout = settings.request_timeout
    try:
        if fmt == "openai-chat":
            payload = {
                "model": settings.target_model or settings.model,
                "messages": messages or [{"role": "user", "content": message}],
            }
            response = httpx.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "ok": True,
                "response": content,
                "raw": data,
                "status_code": response.status_code,
            }

        payload = {"message": message}
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        content = data.get("answer", "")
        return {
            "ok": True,
            "response": content,
            "raw": data,
            "status_code": response.status_code,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def call_target_async(
    settings: MirrorSettings,
    message: str,
    endpoint: str | None = None,
    endpoint_format: str | None = None,
    messages: list[dict] | None = None,
) -> Dict[str, object]:
    url = endpoint or settings.endpoint
    fmt = endpoint_format or settings.endpoint_format
    timeout = settings.request_timeout
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if fmt == "openai-chat":
                payload = {
                    "model": settings.target_model or settings.model,
                    "messages": messages or [{"role": "user", "content": message}],
                }
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {
                    "ok": True,
                    "response": content,
                    "raw": data,
                    "status_code": response.status_code,
                }

            payload = {"message": message}
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("answer", "")
            return {
                "ok": True,
                "response": content,
                "raw": data,
                "status_code": response.status_code,
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
