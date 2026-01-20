from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ApprovalMode(str, Enum):
    AUTO = "auto"
    CONFIRM_WRITES = "confirm_writes"
    CONFIRM_SHELL = "confirm_shell"
    CONFIRM_ALL = "confirm_all"


@dataclass(frozen=True)
class OrchestratorConfig:
    workspace_root: Path
    session_id: str
    brain_root: Path = field(
        default_factory=lambda: Path.home() / ".mirror" / "brain"
    )
    allow_outside_workspace: bool = False
    model: str = "gpt-5-mini"
    max_steps: int = 8
    max_turns: int = 6
    approval_mode: ApprovalMode = ApprovalMode.AUTO
    command_timeout: int = 60
    max_read_bytes: int = 200_000
    max_write_bytes: int = 200_000
    max_replans: int = 1

    def brain_session_dir(self) -> Path:
        return self.brain_root / self.session_id

    def plans_path(self) -> Path:
        return self.brain_session_dir() / "PLANS.md"
