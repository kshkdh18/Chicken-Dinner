from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workspace:
    root: Path
    max_file_size: int
    extra_roots: tuple[Path, ...] = ()
    allow_outside: bool = False

    def resolve_path(self, path: str) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = (self.root / candidate).resolve()
        else:
            candidate = candidate.resolve()

        if self.allow_outside:
            return candidate

        allowed_roots = (self.root, *self.extra_roots)
        if not any(candidate.is_relative_to(root) for root in allowed_roots):
            raise ValueError(f"Path escapes workspace: {path}")
        return candidate

    def resolve_cwd(self, cwd: str | None) -> Path:
        if cwd is None:
            return self.root
        candidate = Path(cwd).expanduser()
        if not candidate.is_absolute():
            candidate = (self.root / candidate).resolve()
        else:
            candidate = candidate.resolve()

        if self.allow_outside:
            return candidate

        allowed_roots = (self.root, *self.extra_roots)
        if not any(candidate.is_relative_to(root) for root in allowed_roots):
            raise ValueError(f"Working directory escapes workspace: {cwd}")
        return candidate


class CommandPolicy:
    def __init__(self) -> None:
        self._deny_patterns = [
            re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
            re.compile(r"\bmkfs\b", re.IGNORECASE),
            re.compile(r"\bdd\s+if=", re.IGNORECASE),
            re.compile(r"\bshutdown\b", re.IGNORECASE),
            re.compile(r"\breboot\b", re.IGNORECASE),
            re.compile(r"\bcurl\b.+\|\s*sh\b", re.IGNORECASE),
            re.compile(r"\bwget\b.+\|\s*sh\b", re.IGNORECASE),
            re.compile(r"\bsudo\b", re.IGNORECASE),
        ]

    def check(self, command: str) -> str | None:
        for pattern in self._deny_patterns:
            if pattern.search(command):
                return pattern.pattern
        return None
