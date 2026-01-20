from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict


def _now_ms() -> int:
    return int(time.time() * 1000)


def append_event(brain_dir: Path, etype: str, payload: Dict[str, Any]) -> None:
    """Append an event as one JSON line to brain_dir/events.jsonl.

    This is best-effort and never raises.
    """
    try:
        brain_dir.mkdir(parents=True, exist_ok=True)
        rec = {"ts": _now_ms(), "type": etype, **payload}
        line = json.dumps(rec, ensure_ascii=False)
        with (brain_dir / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        return

