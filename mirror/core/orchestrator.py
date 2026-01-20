from __future__ import annotations

from dataclasses import dataclass, field

from agents import Agent, Runner

from mirror.core.config import OrchestratorConfig
from mirror.core.models import Plan, PlanStep, WorkerResult
from mirror.core.prompts import planner_instructions, worker_instructions
from mirror.core.tools import build_tools


@dataclass
class StepOutcome:
    step: PlanStep
    result: WorkerResult


@dataclass
class OrchestratorResult:
    goal: str
    plan: Plan
    outcomes: list[StepOutcome] = field(default_factory=list)
    replans: int = 0


class Orchestrator:
    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config
        self._tools = build_tools(config)
        self._planner = Agent(
            name="Planner",
            instructions=planner_instructions(
                plans_path=str(config.plans_path())
            ),
            output_type=Plan,
            model=config.model,
        )
        self._worker = Agent(
            name="Worker",
            instructions=worker_instructions(
                workspace_root=str(config.workspace_root),
                approval_mode=config.approval_mode.value,
                brain_session_dir=str(config.brain_session_dir()),
            ),
            tools=self._tools,
            output_type=WorkerResult,
            model=config.model,
        )

    def run(self, goal: str) -> OrchestratorResult:
        plan = self._make_plan(goal=goal, history=[])
        outcomes: list[StepOutcome] = []
        replans = 0
        self._persist_plan(goal=goal, plan=plan, outcomes=outcomes, replans=replans)

        step_index = 0
        while step_index < len(plan.steps) and len(outcomes) < self.config.max_steps:
            step = plan.steps[step_index]
            history = self._history_summary(outcomes)
            worker_input = self._worker_prompt(goal, step, plan, history)
            worker_run = Runner.run_sync(
                self._worker, input=worker_input, max_turns=self.config.max_turns
            )
            result: WorkerResult = worker_run.final_output
            outcomes.append(StepOutcome(step=step, result=result))
            self._persist_plan(goal=goal, plan=plan, outcomes=outcomes, replans=replans)

            if result.status == "done":
                step_index += 1
                continue

            if replans < self.config.max_replans:
                replans += 1
                plan = self._make_plan(goal=goal, history=self._history_summary(outcomes))
                self._persist_plan(goal=goal, plan=plan, outcomes=outcomes, replans=replans)
                step_index = 0
                continue

            break

        return OrchestratorResult(goal=goal, plan=plan, outcomes=outcomes, replans=replans)

    def _make_plan(self, goal: str, history: str) -> Plan:
        planner_input = self._planner_prompt(goal, history)
        plan_run = Runner.run_sync(self._planner, input=planner_input, max_turns=2)
        return plan_run.final_output

    @staticmethod
    def _planner_prompt(goal: str, history: str) -> str:
        base = f"Goal: {goal}"
        if history:
            return f"{base}\n\nRecent outcomes:\n{history}"
        return base

    @staticmethod
    def _worker_prompt(goal: str, step: PlanStep, plan: Plan, history: str) -> str:
        prompt = [
            f"Goal: {goal}",
            f"Current step: [{step.id}] {step.description}",
        ]
        if step.tool_hint:
            prompt.append(f"Tool hint: {step.tool_hint}")
        if history:
            prompt.append(f"Recent outcomes:\n{history}")
        prompt.append(
            "Plan steps:\n"
            + "\n".join(f"- [{item.id}] {item.description}" for item in plan.steps)
        )
        return "\n\n".join(prompt)

    @staticmethod
    def _history_summary(outcomes: list[StepOutcome]) -> str:
        if not outcomes:
            return ""
        lines = []
        for outcome in outcomes[-5:]:
            lines.append(
                f"[{outcome.step.id}] {outcome.result.status}: {outcome.result.summary}"
            )
        return "\n".join(lines)

    def _persist_plan(
        self, goal: str, plan: Plan, outcomes: list[StepOutcome], replans: int
    ) -> None:
        plan_path = self.config.plans_path()
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# PLANS",
            f"Session: {self.config.session_id}",
            f"Workspace: {self.config.workspace_root}",
            f"Goal: {goal}",
            f"Replans: {replans}",
            "",
            "## Plan",
        ]
        for step in plan.steps:
            hint = f" (tool_hint: {step.tool_hint})" if step.tool_hint else ""
            lines.append(f"- [{step.id}] {step.description}{hint}")

        if outcomes:
            lines.append("")
            lines.append("## Progress")
            for outcome in outcomes:
                lines.append(
                    f"- [{outcome.step.id}] {outcome.result.status}: {outcome.result.summary}"
                )

        plan_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
