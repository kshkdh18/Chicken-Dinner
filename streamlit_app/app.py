from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Ensure repository root importability
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from dotenv import load_dotenv

from mirror.autopilot import discover_endpoint, write_comparison
import httpx
from mirror.mirror_system.orchestrator import MirrorOrchestrator, MirrorRunConfig
from mirror.mirror_system.settings import MirrorSettings


def _brain_files(session_dir: Path) -> tuple[Path, list[Path]]:
    plans = session_dir / "PLANS.md"
    attacks = sorted(session_dir.glob("ATTACK_*.md"))
    return plans, attacks


def _read_text(p: Path, default: str = "") -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return default


def _read_json(p: Path) -> dict:
    import json

    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _tail_events(brain_dir: Path, max_lines: int = 300) -> list[dict]:
    p = brain_dir / "events.jsonl"
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()[-max_lines:]
        out = []
        import json

        for ln in lines:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


def _compute_live_metrics(events: list[dict]) -> dict:
    total = 0
    verdicts = {"pass": 0, "fail": 0, "borderline": 0}
    for ev in events:
        if ev.get("type") == "JudgeResult":
            total += 1
            v = str(ev.get("verdict", "")).lower()
            if v in verdicts:
                verdicts[v] += 1
    if total == 0:
        return {"total_judged": 0}
    return {
        "total_judged": total,
        "attack_success_rate": verdicts["fail"] / total,
        "attack_block_rate": verdicts["pass"] / total,
        "borderline_rate": verdicts["borderline"] / total,
    }


def _try_guardrail_endpoint(timeout: float = 2.0) -> tuple[str | None, str | None]:
    cand = "http://127.0.0.1:8080/v1/chat/completions"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(cand, json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "ping"}]})
            if r.status_code < 500 and "choices" in r.json():
                return cand, "openai-chat"
    except Exception:
        pass
    return None, None


def _run_auto_pair(goal: str, iterations: int, include_toxic: bool, off_id: str, on_id: str, force_proxy_on: bool = False) -> dict:
    endpoint, fmt = discover_endpoint()
    # OFF
    settings_off = MirrorSettings(
        mode="guardrail-off", endpoint=endpoint, endpoint_format=fmt,
        max_iterations=iterations, use_toxic_small_llm=include_toxic,
        judge_model="gpt-4o-mini", defense_model="gpt-4o-mini", reporter_model="gpt-4o-mini",
    )
    config_off = MirrorRunConfig(workspace_root=Path(".").resolve(), session_id=off_id)
    orch_off = MirrorOrchestrator(config_off, settings_off)
    res_off = orch_off.run(goal)
    # ON (prefer guardrail proxy). If force flag is on, skip probe.
    if force_proxy_on:
        on_ep, on_fmt = "http://127.0.0.1:8080/v1/chat/completions", "openai-chat"
    else:
        on_ep, on_fmt = _try_guardrail_endpoint()
    settings_on = MirrorSettings(
        mode="guardrail-on", endpoint=(on_ep or endpoint), endpoint_format=(on_fmt or fmt),
        max_iterations=iterations, use_toxic_small_llm=include_toxic,
        judge_model="gpt-4o-mini", defense_model="gpt-4o-mini", reporter_model="gpt-4o-mini",
    )
    config_on = MirrorRunConfig(workspace_root=Path(".").resolve(), session_id=on_id)
    orch_on = MirrorOrchestrator(config_on, settings_on)
    res_on = orch_on.run(goal)
    # Comparison
    compare_path = Path(res_off.brain_dir).parent / "AUTOPILOT_COMPARISON.md"
    write_comparison(res_off.brain_dir, res_on.brain_dir, compare_path)
    return {"off_dir": str(res_off.brain_dir), "on_dir": str(res_on.brain_dir), "comparison": str(compare_path)}


# UI
st.set_page_config(page_title="MIRROR Autopilot (LIVE)", layout="wide")
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    st.warning("OPENAI_API_KEY 가 설정되지 않았습니다. Judge/Agent가 borderline(parse_error)로 표시될 수 있습니다.")

st.title("MIRROR Autopilot (LIVE)")
st.write("OFF→ON 전체 플로우를 실시간으로 보며 REPORT까지 확인합니다.")

if "executor" not in st.session_state:
    st.session_state.executor = ThreadPoolExecutor(max_workers=2)

with st.sidebar:
    st.header("Controls")
    goal = st.text_input("Goal", value="Autopilot security assessment")
    iterations = st.slider("Iterations", 1, 10, 3)
    with st.expander("Advanced", expanded=False):
        include_toxic = st.checkbox("Include Toxic Adaptive Attacks", value=False)
        force_proxy_on = st.checkbox("Force ON via guardrail proxy (127.0.0.1:8080)", value=True)
    run_btn = st.button("Run", type="primary")

# Start run
if run_btn:
    off_id = f"live_off_{int(time.time())}"
    on_id = f"live_on_{int(time.time())}"
    st.session_state["auto_live_off_id"] = off_id
    st.session_state["auto_live_on_id"] = on_id
    fut = st.session_state.executor.submit(_run_auto_pair, goal, iterations, include_toxic, off_id, on_id, force_proxy_on)
    st.session_state["auto_live_future"] = fut

off_id = st.session_state.get("auto_live_off_id")
on_id = st.session_state.get("auto_live_on_id")
auto_live_fut = st.session_state.get("auto_live_future")
if off_id and on_id and auto_live_fut:
    st.info(f"LIVE Autopilot 실행 중… OFF={off_id}, ON={on_id}")
    off_dir = Path.home() / ".mirror" / "brain" / off_id
    on_dir = Path.home() / ".mirror" / "brain" / on_id
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("OFF Timeline")
        off_events = _tail_events(off_dir)
        if not off_events:
            st.write("(waiting…)")
        else:
            for ev in off_events[-100:]:
                st.markdown(f"**{ev.get('type')}** — {ev.get('ts')}")
                st.code(ev, language="json")
        st.subheader("OFF Latest Logs")
        plans, attacks = _brain_files(off_dir)
        st.caption(str(plans))
        st.code(_read_text(plans), language="markdown")
        if attacks:
            names = [p.name for p in attacks]
            sel_off = st.selectbox("Select OFF ATTACK", names, index=len(names)-1, key="sel_off")
            p_off = next((p for p in attacks if p.name == sel_off), attacks[-1])
            st.caption(str(p_off))
            st.code(_read_text(p_off), language="markdown")
        st.subheader("OFF Live Metrics")
        st.json(_compute_live_metrics(off_events))
        st.subheader("OFF REPORT.md (auto when ready)")
        st.code(_read_text(off_dir / "REPORT.md", default="(report pending…)"), language="markdown")
    with col2:
        st.subheader("ON Timeline")
        on_events = _tail_events(on_dir)
        if not on_events:
            msg = "(waiting…)"
            if _tail_events(off_dir):
                msg += " ON은 OFF 완료 후 시작됩니다."
            st.write(msg)
        else:
            for ev in on_events[-100:]:
                st.markdown(f"**{ev.get('type')}** — {ev.get('ts')}")
                st.code(ev, language="json")
        st.subheader("ON Latest Logs")
        plans, attacks = _brain_files(on_dir)
        st.caption(str(plans))
        st.code(_read_text(plans), language="markdown")
        if attacks:
            names = [p.name for p in attacks]
            sel_on = st.selectbox("Select ON ATTACK", names, index=len(names)-1, key="sel_on")
            p_on = next((p for p in attacks if p.name == sel_on), attacks[-1])
            st.caption(str(p_on))
            st.code(_read_text(p_on), language="markdown")
        st.subheader("ON Live Metrics")
        st.json(_compute_live_metrics(on_events))
        st.subheader("ON REPORT.md (auto when ready)")
        st.code(_read_text(on_dir / "REPORT.md", default="(report pending…)"), language="markdown")
    # Comparison when done
    if auto_live_fut.done():
        res = auto_live_fut.result()
        compare_path = Path(res.get("comparison", ""))
        if compare_path.exists():
            st.divider()
            st.subheader("Comparison")
            st.code(_read_text(compare_path), language="markdown")
    # Auto refresh while running
    if not auto_live_fut.done():
        time.sleep(1.0)
        st.rerun()
