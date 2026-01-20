from __future__ import annotations

from pathlib import Path


class BrainStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def plans_path(self) -> Path:
        return self.root / "PLANS.md"

    def attack_path(self, iteration: int) -> Path:
        return self.root / f"ATTACK_{iteration}.md"

    def report_path(self) -> Path:
        return self.root / "REPORT.md"

    def report_json_path(self) -> Path:
        return self.root / "REPORT.json"

    def guardrail_rules_path(self) -> Path:
        return self.root / "guardrail_rules.json"

    def list_attack_paths(self) -> list[Path]:
        return sorted(self.root.glob("ATTACK_*.md"))

    def write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def append_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(content)

    def read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")
