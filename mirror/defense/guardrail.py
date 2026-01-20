from __future__ import annotations

import re
import time

from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel

from mirror.defense.guardrail_rules import GuardrailRules, load_rules


class ChatMessage(BaseModel):
    role: str
    content: str
    model_config = {"extra": "allow"}


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = None
    model_config = {"extra": "allow"}


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]


def _matches_any(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return pattern
        except re.error:
            continue
    return None


def _redact(text: str, patterns: list[str]) -> str:
    redacted = text
    for pattern in patterns:
        try:
            redacted = re.sub(pattern, "[REDACTED]", redacted, flags=re.IGNORECASE)
        except re.error:
            continue
    return redacted


def create_app(rules_path, model: str) -> FastAPI:
    app = FastAPI(title="MIRROR Guardrail Proxy")
    client = OpenAI()

    @app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
    def chat_completions(payload: ChatCompletionRequest) -> ChatCompletionResponse:
        rules: GuardrailRules = load_rules(rules_path)
        user_text = "\n".join(
            msg.content for msg in payload.messages if msg.role == "user"
        )
        blocked_pattern = _matches_any(user_text, rules.input_denylists)
        if blocked_pattern:
            blocked_message = (
                "Request blocked by guardrail. Pattern: " + blocked_pattern
            )
            return ChatCompletionResponse(
                id=f"guardrail-{int(time.time())}",
                created=int(time.time()),
                model=payload.model or model,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content=blocked_message),
                    )
                ],
            )

        response = client.chat.completions.create(
            model=payload.model or model,
            messages=[msg.model_dump() for msg in payload.messages],
            temperature=payload.temperature,
        )
        content = response.choices[0].message.content or ""
        content = _redact(content, rules.output_redact_patterns)

        return ChatCompletionResponse(
            id=response.id,
            created=int(time.time()),
            model=response.model or model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=content),
                    finish_reason=response.choices[0].finish_reason or "stop",
                )
            ],
        )

    return app
