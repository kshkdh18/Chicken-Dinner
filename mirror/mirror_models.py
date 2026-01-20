from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field


class AttackPlan(BaseModel):
    category: str = Field(..., description="Attack category like prompt_injection.")
    goal: str = Field(..., description="Specific goal for this attack iteration.")
    notes: str | None = Field(default=None, description="Extra notes for the attacker.")


class MirrorPlan(BaseModel):
    objective: str = Field(..., description="Overall objective for the MIRROR run.")
    iterations: List[AttackPlan] = Field(default_factory=list)


class AttackResult(BaseModel):
    category: str
    prompt: str
    mutated_prompt: str | None = None
    response: str
    attack_notes: str
    success_signal: str | None = None
    toxicity_score: float | None = None


class JudgeResult(BaseModel):
    verdict: Literal["pass", "fail", "borderline"]
    severity: Literal["low", "medium", "high"]
    rationale: str
    signals: List[str] = Field(default_factory=list)
    tier: Literal["tier1", "tier2", "tier3"] | None = None


class DefenseResult(BaseModel):
    actions: List[str] = Field(default_factory=list)
    input_patterns: List[str] = Field(default_factory=list)
    output_patterns: List[str] = Field(default_factory=list)
    system_prompt_update: str | None = None


class ReportResult(BaseModel):
    summary: str
    metrics: Dict[str, float] = Field(default_factory=dict)
    findings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    owasp_mapping: Dict[str, List[str]] = Field(default_factory=dict)
    nist_mapping: Dict[str, List[str]] = Field(default_factory=dict)
