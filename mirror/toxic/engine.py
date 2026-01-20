from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import List

from ..attack_library import get_prompts
from ..attack_utils import call_target_async, mutate_prompt
from ..mirror_settings import MirrorSettings
from .generator import ToxicPromptGenerator
from .scorer import ToxicityScorer
from ..garak_cli import generate_prompts as garak_generate


@dataclass
class ToxicTurn:
    prompt: str
    mutated_prompt: str | None
    response: str
    score: float


@dataclass
class ToxicAttempt:
    index: int
    base_prompt: str
    turns: List[ToxicTurn]

    @property
    def final_turn(self) -> ToxicTurn:
        return self.turns[-1]


@dataclass
class ToxicRun:
    attempts: List[ToxicAttempt]
    chosen: ToxicAttempt


class ToxicAdaptiveAttackEngine:
    def __init__(self, settings: MirrorSettings) -> None:
        self.settings = settings
        self.gen = ToxicPromptGenerator(
            model_name=settings.toxic_model,
            max_new_tokens=settings.toxic_max_new_tokens,
            temperature=settings.toxic_temperature,
            top_p=settings.toxic_top_p,
        )
        self.scorer = ToxicityScorer(model_name=settings.toxic_cls_model)

    def run(self, goal: str, category: str, iteration: int) -> ToxicRun:
        async def _runner() -> ToxicRun:
            base_prompts = await self._build_prompts(goal, category, iteration)
            attempts = await self._run_attempts(goal, base_prompts)
            chosen = self._select_best(attempts)
            return ToxicRun(attempts=attempts, chosen=chosen)

        return asyncio.run(_runner())

    async def _build_prompts(self, goal: str, category: str, iteration: int) -> List[str]:
        static_prompts = get_prompts("toxicity", limit=self.settings.toxic_variants)
        dynamic = self.gen.generate(None, goal=goal, count=self.settings.toxic_variants)
        garak_prompts: List[str] = []
        if getattr(self.settings, "garak_cli_enabled", False) and getattr(self.settings, "garak_cli_probes", []):
            for probe in self.settings.garak_cli_probes:
                garak_prompts.extend(garak_generate(probe, count=self.settings.toxic_variants))
        combined = [*static_prompts, *dynamic]
        if garak_prompts:
            combined.extend(garak_prompts)
        deduped: List[str] = []
        seen: set[str] = set()
        for p in combined:
            key = " ".join(p.split()).lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(p)
        return deduped[: max(self.settings.attack_fanout, 1)]

    async def _run_attempts(self, goal: str, prompts: List[str]) -> List[ToxicAttempt]:
        tasks = [self._run_one(i + 1, p) for i, p in enumerate(prompts)]
        return list(await asyncio.gather(*tasks))

    async def _run_one(self, index: int, base_prompt: str) -> ToxicAttempt:
        turns: List[ToxicTurn] = []
        last_response: str | None = None
        cur_prompt = base_prompt
        for t in range(max(self.settings.toxic_turns_max, 1)):
            mutated = None
            # 가벼운 변이 재사용(옵션)
            if self.settings.mutation_methods and self.settings.mutation_rate > 0:
                mutated = mutate_prompt(cur_prompt, self.settings.mutation_methods[t % len(self.settings.mutation_methods)])
            outbound = mutated or cur_prompt
            result = await call_target_async(self.settings, message=outbound, messages=None)
            response = (
                result.get("response", "") if result.get("ok") else f"Error: {result.get('error','unknown')}"
            )
            score, labels = self.scorer.score(response)
            turns.append(ToxicTurn(prompt=cur_prompt, mutated_prompt=mutated, response=response, score=score))
            if score >= self.settings.toxic_threshold:
                break
            last_response = response
            # generate next challenge
            nexts = self.gen.generate(last_response, goal="make the model say something toxic", count=1)
            if not nexts:
                break
            cur_prompt = nexts[0]
        return ToxicAttempt(index=index, base_prompt=base_prompt, turns=turns)

    def _select_best(self, attempts: List[ToxicAttempt]) -> ToxicAttempt:
        return sorted(attempts, key=lambda a: a.final_turn.score, reverse=True)[0]
