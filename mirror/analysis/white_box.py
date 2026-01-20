from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class WhiteBoxScan:
    root: Path
    prompt_files: list[Path]
    notes: list[str]


def scan_white_box(root: Path, max_files: int = 80, max_bytes: int = 200_000) -> WhiteBoxScan:
    candidates: list[Path] = []
    notes: list[str] = []
    if not root.exists():
        return WhiteBoxScan(root=root, prompt_files=[], notes=["white-box path not found"])

    keyword_names = ("prompt", "policy", "system")
    keyword_content = ("system prompt", "policy", "instruction")

    for path in root.rglob("*"):
        if len(candidates) >= max_files:
            break
        if not path.is_file():
            continue
        if path.stat().st_size > max_bytes:
            continue
        name_lower = path.name.lower()
        if any(key in name_lower for key in keyword_names):
            candidates.append(path)
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if any(key in content.lower() for key in keyword_content):
            candidates.append(path)

    if not candidates:
        notes.append("no prompt-related files detected")
    return WhiteBoxScan(root=root, prompt_files=candidates, notes=notes)


def summarize_scan(scan: WhiteBoxScan, limit: int = 8) -> str:
    lines = [f"root: {scan.root}"]
    if scan.notes:
        lines.append("notes: " + "; ".join(scan.notes))
    if scan.prompt_files:
        lines.append("prompt_files:")
        for path in scan.prompt_files[:limit]:
            lines.append(f"- {path}")
        if len(scan.prompt_files) > limit:
            lines.append(f"- ... ({len(scan.prompt_files) - limit} more)")
    return "\n".join(lines)


def apply_system_prompt_update(root: Path, update: str) -> str | None:
    candidates = [
        path
        for path in root.rglob("*")
        if path.is_file() and "system_prompt" in path.name.lower()
    ]
    if len(candidates) != 1:
        return None
    target = candidates[0]
    target.write_text(update.strip() + "\n", encoding="utf-8")
    return str(target)
