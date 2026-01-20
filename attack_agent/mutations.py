from __future__ import annotations

import base64
import random
from typing import Callable, List


def m_base64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def m_leetspeak(s: str) -> str:
    table = str.maketrans({
        "a": "4",
        "e": "3",
        "i": "1",
        "o": "0",
        "s": "5",
        "t": "7",
    })
    return s.translate(table)


def m_spaced(s: str) -> str:
    return " ".join(list(s))


def build_mutation_pipeline(level: str = "light") -> List[Callable[[str], str]]:
    """Return a list of mutation functions to apply in order.

    - light: one random mutation
    - medium: two deterministic
    - heavy: three including base64
    """
    level = level.lower()
    if level == "light":
        return [random.choice([m_leetspeak, m_spaced])]
    if level == "medium":
        return [m_leetspeak, m_spaced]
    if level == "heavy":
        return [m_leetspeak, m_spaced, m_base64]
    return []


def apply_mutations(prompt: str, muts: List[Callable[[str], str]]) -> str:
    out = prompt
    for m in muts:
        out = m(out)
    return out

