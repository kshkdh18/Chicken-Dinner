from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


class GuardrailRules(BaseModel):
    input_denylists: List[str] = Field(default_factory=list)
    output_redact_patterns: List[str] = Field(default_factory=list)


def load_rules(path: Path) -> GuardrailRules:
    if not path.exists():
        return GuardrailRules()
    data = json.loads(path.read_text(encoding="utf-8"))
    return GuardrailRules(**data)


def save_rules(path: Path, rules: GuardrailRules) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rules.model_dump_json(indent=2), encoding="utf-8")
