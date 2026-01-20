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
    attack_fanout: int = 3
    attack_turns: int = 2
    attack_variants: int = 4
    dynamic_attacks: bool = True
    mutation_methods: List[str] = Field(
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

    # Small-LLM toxic adaptive attack (optional)
    use_toxic_small_llm: bool = False
    toxic_model: str = "garak-llm/attackgeneration-toxicity_gpt2"
    toxic_cls_model: str = "unitary/toxic-bert"
    toxic_threshold: float = 0.7
    toxic_variants: int = 3
    toxic_turns_max: int = 4
    toxic_max_new_tokens: int = 48
    toxic_temperature: float = 1.0
    toxic_top_p: float = 0.9
