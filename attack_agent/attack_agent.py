from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Callable
from datetime import datetime
import asyncio
import time

from .config import Settings
from . import probes
from .mutations import apply_mutations, build_mutation_pipeline
from .executor import call_target
from .judge import judge_response
from .rewrites import build_rewriters


@dataclass
class AttackResult:
    kind: str
    original_prompt: str
    mutated_prompt: str
    response_text: str
    passed: bool
    reason: str
    raw: Dict[str, Any]
    attempts: int = 1
    latency_ms: int = 0


class AttackAgent:
    def __init__(
        self,
        settings: Settings,
        mutation_level: str = "light",
        tries: int = 1,
        concurrency: int = 4,
        seed: Optional[int] = None,
    ) -> None:
        self.settings = settings
        self.mutations = build_mutation_pipeline(mutation_level)
        self.tries = max(1, tries)
        self.concurrency = max(1, concurrency)
        self.rewriters: List[Callable[[str, str], str]] = build_rewriters()
        self._seed = seed

    async def run_round(
        self,
        kind: str,
        max_prompts: Optional[int] = None,
        prompts_override: Optional[List[str]] = None,
    ) -> List[AttackResult]:
        prompts = list(prompts_override) if prompts_override else probes.get_prompts(kind)
        if max_prompts is not None:
            prompts = prompts[:max_prompts]
        sem = asyncio.Semaphore(self.concurrency)

        async def _attack_one(p: str) -> AttackResult:
            mutated0 = apply_mutations(p, self.mutations) if self.mutations else p
            prompt_current = mutated0
            attempts = 0
            start_ts = time.time()
            last_text: str = ""
            last_raw: Dict[str, Any] = {}
            last_reason: str = ""
            last_passed: bool = False

            while attempts < self.tries:
                attempts += 1
                try:
                    async with sem:
                        last_text, last_raw = await call_target(
                            endpoint=self.settings.endpoint,
                            model=self.settings.model,
                            prompt=prompt_current,
                            timeout_s=self.settings.timeout_s,
                        )
                except Exception as e:
                    last_text, last_raw = f"<error: {e}>", {"error": str(e)}

                j = judge_response(kind=kind, response=last_text or "")
                last_passed = j["passed"]
                last_reason = j["reason"]

                # If defense blocked (passed=True), try rewrite to circumvent; else stop (attack likely succeeded)
                if not last_passed:
                    break

                # rewrite for next attempt using a heuristic rotation
                rewrite = self.rewriters[(attempts - 1) % len(self.rewriters)]
                prompt_current = rewrite(p, prompt_current)

            latency_ms = int((time.time() - start_ts) * 1000)
            return AttackResult(
                kind=kind,
                original_prompt=p,
                mutated_prompt=prompt_current,
                response_text=last_text or "",
                passed=last_passed,
                reason=last_reason,
                raw=last_raw,
                attempts=attempts,
                latency_ms=latency_ms,
            )

        tasks = [_attack_one(p) for p in prompts]
        return await asyncio.gather(*tasks)

    @staticmethod
    def _md_header(title: str) -> str:
        return f"# {title}\n\nGenerated: {datetime.utcnow().isoformat()}Z\n\n"

    @staticmethod
    def to_markdown(round_id: int, results: List[AttackResult]) -> str:
        lines: List[str] = []
        lines.append(AttackAgent._md_header(f"ATTACK_{round_id}"))
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        lines.append(f"Summary: {passed}/{total} passed (defense blocked)\n")
        for i, r in enumerate(results, 1):
            lines.append(f"## Case {i} — kind={r.kind}, passed={'YES' if r.passed else 'NO'}\n")
            lines.append("**Original Prompt**\n")
            lines.append("\n```\n" + r.original_prompt + "\n```\n")
            lines.append("**Mutated Prompt**\n")
            lines.append("\n```\n" + r.mutated_prompt + "\n```\n")
            lines.append("**Model Response (truncated)**\n")
            snippet = (r.response_text or "").strip()
            if len(snippet) > 1200:
                snippet = snippet[:1200] + "..."
            lines.append("\n```")
            lines.append(snippet)
            lines.append("```\n")
            lines.append(f"Attempts: {r.attempts}\n")
            lines.append(f"Latency(ms): {r.latency_ms}\n")
            lines.append(f"Reason: {r.reason}\n")
        return "\n".join(lines)

    @staticmethod
    def to_json(round_id: int, results: List[AttackResult]) -> Dict[str, Any]:
        return {
            "round": round_id,
            "summary": {
                "cases": len(results),
                "defense_passed": sum(1 for r in results if r.passed),
                "defense_failed": sum(1 for r in results if not r.passed),
            },
            "cases": [
                {
                    "kind": r.kind,
                    "original_prompt": r.original_prompt,
                    "mutated_prompt": r.mutated_prompt,
                    "response_snippet": (r.response_text or "")[:1200],
                    "defense_passed": r.passed,
                    "reason": r.reason,
                    "attempts": r.attempts,
                    "latency_ms": r.latency_ms,
                }
                for r in results
            ],
        }
