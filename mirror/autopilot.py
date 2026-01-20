from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from mirror.mirror_system.orchestrator import MirrorOrchestrator, MirrorRunConfig
from mirror.mirror_system.settings import MirrorSettings


@dataclass
class AutoResult:
    session_id: str
    brain_dir: Path


def detect_endpoint_format(endpoint: str, timeout: float = 3.0) -> Literal["openai-chat", "simple-rag"]:
    """Best-effort endpoint format detection.

    - Try OpenAI Chat Completions schema
    - Fallback to Simple JSON(`/chat`) schema
    """
    try:
        payload = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "ping"}]}
        with httpx.Client(timeout=timeout) as client:
            r = client.post(endpoint, json=payload)
            if r.status_code < 500 and "choices" in r.json():
                return "openai-chat"
    except Exception:
        pass
    # try simple-rag shape
    try:
        payload = {"message": "ping"}
        with httpx.Client(timeout=timeout) as client:
            r = client.post(endpoint, json=payload)
            if r.status_code < 500 and ("answer" in r.json() or isinstance(r.json(), dict)):
                return "simple-rag"
    except Exception:
        pass
    return "simple-rag"


def discover_endpoint(timeout: float = 3.0) -> tuple[str, Literal["openai-chat", "simple-rag"]]:
    """Find a reasonable default endpoint without user input.

    Priority:
    1) OPENAI_BASE_URL env → {base}/chat/completions (openai-chat)
    2) localhost:8000/chat (simple-rag)
    3) localhost:8080/v1/chat/completions (openai-chat; e.g., guardrail proxy)
    """
    base = os.getenv("OPENAI_BASE_URL")
    if base:
        target = base.rstrip("/") + "/chat/completions"
        return target, "openai-chat"
    # try simple-rag default
    cand_simple = "http://127.0.0.1:8000/chat"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(cand_simple, json={"message": "ping"})
            if r.status_code < 500:
                return cand_simple, "simple-rag"
    except Exception:
        pass
    # try openai proxy default
    cand_openai = "http://127.0.0.1:8080/v1/chat/completions"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(cand_openai, json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "ping"}]})
            if r.status_code < 500:
                return cand_openai, "openai-chat"
    except Exception:
        pass
    # default fallback
    return cand_simple, "simple-rag"


def _run_once(goal: str, endpoint: str, endpoint_format: str, session_id: str, mode: str,
              iterations: int = 3, use_toxic_small_llm: bool = False) -> AutoResult:
    settings = MirrorSettings(
        mode=mode, endpoint=endpoint, endpoint_format=endpoint_format,
        max_iterations=iterations, use_toxic_small_llm=use_toxic_small_llm,
    )
    config = MirrorRunConfig(workspace_root=Path(".").resolve(), session_id=session_id)
    orch = MirrorOrchestrator(config, settings)
    result = orch.run(goal)
    return AutoResult(session_id=session_id, brain_dir=result.brain_dir)


def write_comparison(off_dir: Path, on_dir: Path, out_path: Path) -> None:
    def _load_metrics(p: Path) -> dict:
        f = p / "REPORT.json"
        if not f.exists():
            return {}
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {}

    off = _load_metrics(off_dir)
    on = _load_metrics(on_dir)
    def m(obj: dict, key: str) -> float:
        return float(obj.get("metrics", {}).get(key, 0.0))

    lines = ["# Autopilot Comparison", ""]
    lines.append(f"OFF session: {off_dir}")
    lines.append(f"ON  session: {on_dir}")
    lines.append("")
    keys = [
        "attack_success_rate", "attack_block_rate", "borderline_rate", "guardrail_trigger_rate",
        "toxicity_engine_success_rate", "toxicity_judge_fail_rate", "toxicity_avg_score",
    ]
    lines.append("| Metric | OFF | ON | Delta(ON-OFF) |")
    lines.append("|---|---:|---:|---:|")
    for k in keys:
        off_v = m(off, k)
        on_v = m(on, k)
        lines.append(f"| {k} | {off_v:.3f} | {on_v:.3f} | {(on_v-off_v):+.3f} |")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_autopilot(goal: str, endpoint: str | None = None, iterations: int = 3,
                  include_toxic: bool = True) -> dict:
    if endpoint:
        fmt = detect_endpoint_format(endpoint)
    else:
        endpoint, fmt = discover_endpoint()

    off_id = f"auto_off_{int(time.time())}"
    on_id = f"auto_on_{int(time.time())}"

    off = _run_once(goal, endpoint, fmt, off_id, mode="guardrail-off",
                    iterations=iterations, use_toxic_small_llm=include_toxic)
    on = _run_once(goal, endpoint, fmt, on_id, mode="guardrail-on",
                   iterations=iterations, use_toxic_small_llm=include_toxic)

    compare_path = off.brain_dir.parent / "AUTOPILOT_COMPARISON.md"
    write_comparison(off.brain_dir, on.brain_dir, compare_path)
    return {
        "off_session": off.session_id,
        "on_session": on.session_id,
        "off_dir": str(off.brain_dir),
        "on_dir": str(on.brain_dir),
        "comparison": str(compare_path),
    }
