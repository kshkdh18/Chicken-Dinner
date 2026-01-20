from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MirrorSettings(BaseModel):
    mode: Literal["guardrail-off", "guardrail-on", "white-box"] = "guardrail-off"
    endpoint: str
    endpoint_format: Literal["simple-rag", "openai-chat"] = "simple-rag"
    white_box_path: str | None = None
    max_iterations: int = 5
    attack_categories: list[str] = Field(
        default_factory=lambda: ["prompt_injection", "jailbreak", "pii_leak"]
    )
    attack_fanout: int = 3
    attack_turns: int = 2
    attack_variants: int = 4
    dynamic_attacks: bool = True
    mutation_methods: list[str] = Field(
        default_factory=lambda: ["base64", "rot13", "spacing", "leetspeak"]
    )
    mutation_rate: float = 0.4
    guardrail_port: int = 8080
    model: str = "gpt-5-mini"
    attacker_model: str | None = None
    judge_model: str | None = None
    defense_model: str | None = None
    reporter_model: str | None = None
    planner_model: str | None = None
    target_model: str | None = None
    request_timeout: int = 30
