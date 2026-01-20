from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    mode: str = Field(default="guardrail-off")
    endpoint: str = Field(default="http://localhost:8000/chat")
    model: str = Field(default="gpt-4o-mini")
    max_iterations: int = Field(default=1)
    attack_categories: list[str] = Field(
        default_factory=lambda: ["dan", "toxicity", "prompt_injection"]
    )
    timeout_s: float = Field(default=30.0)


def load_settings(path: str | None = None) -> Settings:
    candidates = []
    if path:
        candidates.append(Path(path))
    candidates.append(Path("settings.json"))
    for p in candidates:
        if p.exists():
            try:
                return Settings(**json.loads(p.read_text()))
            except Exception:
                # Fallback to defaults on parse error
                break
    return Settings()

