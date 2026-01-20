from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    id: str = Field(..., description="Short identifier for the step.")
    description: str = Field(..., description="Actionable step description.")
    tool_hint: str | None = Field(
        default=None,
        description="Optional tool suggestion like read_file, edit_file, or run_shell.",
    )


class Plan(BaseModel):
    objective: str = Field(..., description="Overall goal for the plan.")
    steps: list[PlanStep] = Field(..., description="Ordered steps to reach the goal.")


class WorkerResult(BaseModel):
    status: Literal["done", "blocked", "needs_info"] = Field(
        ..., description="Execution result for the step."
    )
    summary: str = Field(..., description="Short summary of actions and outcomes.")
    changed_files: list[str] = Field(
        default_factory=list, description="Workspace-relative paths modified."
    )
    commands: list[str] = Field(
        default_factory=list, description="Shell commands executed."
    )
