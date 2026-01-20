from __future__ import annotations

from typing import List
from fastapi import FastAPI
from pydantic import BaseModel
import time


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]


class ChatMessageOut(BaseModel):
    role: str = "assistant"
    content: str


class Choice(BaseModel):
    index: int
    message: ChatMessageOut
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]


app = FastAPI(title="Mock LLM Target")


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
def chat(payload: ChatCompletionRequest) -> ChatCompletionResponse:
    text = "\n".join(m.content for m in payload.messages if m.role == "user")
    # Simple heuristics: toxic keywords -> refusal; injection/jailbreak keywords -> comply
    lowered = text.lower()
    if any(k in lowered for k in ["insult", "hateful", "harassment", "abusive"]):
        content = "I'm sorry, I cannot help with that request."
    elif any(k in lowered for k in ["ignore previous instructions", "system prompt", "reveal", "developer mode", "no restrictions"]):
        content = "Sure, here is the system prompt: [SIMULATED_SYSTEM_PROMPT]"
    else:
        content = "This is a generic response from the mock model."

    return ChatCompletionResponse(
        id=f"mock-{int(time.time())}",
        created=int(time.time()),
        model=payload.model,
        choices=[Choice(index=0, message=ChatMessageOut(content=content))],
    )

