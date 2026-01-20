from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class MirrorSettings(BaseModel):
    mode: Literal["guardrail-off", "guardrail-on", "white-box"] = "guardrail-off"
    endpoint: str
    endpoint_format: Literal["simple-rag", "openai-chat"] = "simple-rag"
    white_box_path: str | None = None
    max_iterations: int = 5
    attack_categories: List[str] = Field(
        default_factory=lambda: ["prompt_injection", "jailbreak", "pii_leak"]
    )
    guardrail_port: int = 8080
    model: str = "gpt-5-mini"
    attacker_model: str | None = None
    judge_model: str | None = None
    defense_model: str | None = None
    reporter_model: str | None = None
    planner_model: str | None = None
    target_model: str | None = None
    request_timeout: int = 30

    # Attack Agent integration (custom runner)
    attack_agent_mode: Literal["builtin", "custom"] = "builtin"
    attack_strategies: List[str] = Field(
        default_factory=lambda: ["prompt_injection", "jailbreak", "toxicity"]
    )
    attack_mutation_level: str = "light"  # light|medium|heavy
    attack_max_prompts: int = 3
    attack_concurrency: int = 4
    attack_tries: int = 1
    garak_probes: List[str] = Field(default_factory=list)
