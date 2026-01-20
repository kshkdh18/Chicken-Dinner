from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.tracing import TracingProcessor, add_trace_processor


def _truncate(value: Any, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


@dataclass
class ConsoleProgress(TracingProcessor):
    max_chars: int = 200

    def on_trace_start(self, trace) -> None:
        name = getattr(trace, "name", "")
        print(f"[trace] start {trace.trace_id} {name}".strip(), flush=True)

    def on_trace_end(self, trace) -> None:
        name = getattr(trace, "name", "")
        print(f"[trace] end {trace.trace_id} {name}".strip(), flush=True)

    def on_span_start(self, span) -> None:
        data = getattr(span, "span_data", None)
        data_type = getattr(data, "type", "span")
        if data_type == "agent":
            name = getattr(data, "name", "agent")
            print(f"[agent] start {name}", flush=True)
        elif data_type == "function":
            name = getattr(data, "name", "tool")
            print(f"[tool] start {name}", flush=True)
        elif data_type == "generation":
            model = getattr(data, "model", None)
            suffix = f" ({model})" if model else ""
            print(f"[llm] start{suffix}", flush=True)
        else:
            print(f"[span] start {data_type}", flush=True)

    def on_span_end(self, span) -> None:
        data = getattr(span, "span_data", None)
        data_type = getattr(data, "type", "span")
        if data_type == "agent":
            name = getattr(data, "name", "agent")
            print(f"[agent] end {name}", flush=True)
        elif data_type == "function":
            name = getattr(data, "name", "tool")
            output = getattr(data, "output", None)
            if output is not None:
                output_text = _truncate(output, self.max_chars)
                print(f"[tool] end {name} -> {output_text}", flush=True)
            else:
                print(f"[tool] end {name}", flush=True)
        elif data_type == "generation":
            print("[llm] end", flush=True)
        else:
            print(f"[span] end {data_type}", flush=True)

    def shutdown(self) -> None:
        return None

    def force_flush(self) -> None:
        return None


def enable_print_progress(max_chars: int = 200) -> None:
    add_trace_processor(ConsoleProgress(max_chars=max_chars))
