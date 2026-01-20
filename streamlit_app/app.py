from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Tuple

import streamlit as st

from mirror.autopilot import run_autopilot, discover_endpoint
from mirror.mirror_orchestrator import MirrorOrchestrator, MirrorRunConfig
from mirror.mirror_settings import MirrorSettings


def _brain_files(session_dir: Path) -> tuple[Path, List[Path]]:
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


def _run_mirror(goal: str, session_id: str, mode: str, iterations: int, include_toxic: bool) -> Tuple[str, str]:
    endpoint, fmt = discover_endpoint()
    settings = MirrorSettings(
        mode=mode,
        endpoint=endpoint,
        endpoint_format=fmt,
        max_iterations=iterations,
        use_toxic_small_llm=include_toxic,
    )
    config = MirrorRunConfig(workspace_root=Path(".").resolve(), session_id=session_id)
    orch = MirrorOrchestrator(config, settings)
    result = orch.run(goal)
    return str(result.brain_dir), session_id


def _tail_events(brain_dir: Path, max_lines: int = 300) -> List[dict]:
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


st.set_page_config(page_title="MIRROR Autopilot", layout="wide")
st.title("MIRROR Autopilot Demo")
st.write("입력 없이 OFF→ON 두 세션을 자동 실행하고, 진행 상황과 지표를 보여줍니다.")

if "executor" not in st.session_state:
    st.session_state.executor = ThreadPoolExecutor(max_workers=2)

with st.sidebar:
    st.header("Controls")
    goal = st.text_input("Goal", value="Autopilot security assessment")
    iterations = st.slider("Iterations", 1, 10, 3)
    include_toxic = st.checkbox("Include Toxic Adaptive Attacks", value=True)
    run_auto = st.button("Run Autopilot", type="primary")
    run_live = st.button("Run LIVE (OFF)")

# Autopilot (완료 후 스냅샷)
if run_auto:
    st.session_state["auto_result"] = run_autopilot(
        goal=goal, endpoint=None, iterations=iterations, include_toxic=include_toxic
    )

def _render_session(title: str, session_dir: Path):
    st.subheader(title)
    plans, attacks = _brain_files(session_dir)
    st.caption(str(plans))
    st.code(_read_text(plans), language="markdown")
    if attacks:
        last = attacks[-1]
        st.caption(str(last))
        st.code(_read_text(last), language="markdown")


auto = st.session_state.get("auto_result")
if auto:
    col1, col2 = st.columns(2)
    with col1:
        _render_session(f"OFF Session — {auto['off_session']}", Path(auto["off_dir"]))
    with col2:
        _render_session(f"ON Session — {auto['on_session']}", Path(auto["on_dir"]))

    st.divider()
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("OFF Metrics")
        off_report = _read_json(Path(auto["off_dir"]) / "REPORT.json")
        st.json(off_report.get("metrics", {}))
    with col4:
        st.subheader("ON Metrics")
        on_report = _read_json(Path(auto["on_dir"]) / "REPORT.json")
        st.json(on_report.get("metrics", {}))

    st.divider()
    st.subheader("Comparison")
    st.code(_read_text(Path(auto["comparison"])), language="markdown")

# LIVE 실행(폴링 기반)
if run_live:
    st.session_state["live_session_id"] = f"live_off_{int(time.time())}"
    fut = st.session_state.executor.submit(
        _run_mirror, goal, st.session_state["live_session_id"], "guardrail-off", iterations, include_toxic
    )
    st.session_state["live_future"] = fut

live_id = st.session_state.get("live_session_id")
live_fut = st.session_state.get("live_future")
if live_id and live_fut:
    st.info(f"LIVE 실행 중… 세션: {live_id}")
    brain_dir = Path.home() / ".mirror" / "brain" / live_id
    left, right = st.columns(2)
    with left:
        st.subheader("Timeline (events)")
        events = _tail_events(brain_dir)
        if not events:
            st.write("(waiting for events…)")
        else:
            for ev in events[-100:]:
                et = ev.get("type")
                ts = ev.get("ts")
                st.markdown(f"**{et}** — {ts}")
                st.code(ev, language="json")
    with right:
        st.subheader("Latest Logs")
        plans, attacks = _brain_files(brain_dir)
        st.caption(str(plans))
        st.code(_read_text(plans), language="markdown")
        if attacks:
            st.caption(str(attacks[-1]))
            st.code(_read_text(attacks[-1]), language="markdown")
    # 자동 리프레시
    if not live_fut.done():
        time.sleep(1.0)
        st.experimental_rerun()
