from __future__ import annotations

import json
import shutil
import subprocess
from typing import List


def garak_available() -> bool:
    return shutil.which("garak") is not None


def generate_prompts(probe: str, count: int = 3, model: str | None = None) -> List[str]:
    """Run garak CLI to generate prompts via atkgen or probe.

    Returns a best-effort list of prompts; if garak is not available or fails, returns [].
    """
    if not garak_available():
        return []
    cmd = [
        "garak",
        "run",
        "--probe",
        probe,
        "--json-out",
        "-",
    ]
    if model:
        cmd += ["--generator", model]
    try:
        completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            return []
        data = json.loads(completed.stdout or "{}")
        prompts: List[str] = []
        # Best-effort: walk JSON to find candidate prompts
        for item in data.get("runs", []):
            for p in item.get("prompts", []):
                text = str(p)
                if text:
                    prompts.append(text)
        return prompts[:count]
    except Exception:
        return []

