from __future__ import annotations

from typing import List
import importlib


def load_garak_prompts(probe_paths: List[str], max_count: int = 5) -> List[str]:
    prompts: List[str] = []
    for path in probe_paths:
        try:
            mod_path, cls_name = path.rsplit(".", 1)
            module = importlib.import_module(mod_path)
            cls = getattr(module, cls_name)
            inst = cls()
            if hasattr(inst, "prompts"):
                items = list(inst.prompts)
            elif hasattr(inst, "promptset"):
                items = list(inst.promptset)
            else:
                items = []
            for it in items:
                if len(prompts) >= max_count:
                    break
                prompts.append(str(it))
        except Exception:
            continue
        if len(prompts) >= max_count:
            break
    return prompts

