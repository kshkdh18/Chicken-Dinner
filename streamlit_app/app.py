from __future__ import annotations

import time
from pathlib import Path
from typing import List

import streamlit as st

from mirror.autopilot import run_autopilot


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


st.set_page_config(page_title="MIRROR Autopilot", layout="wide")
st.title("MIRROR Autopilot Demo")
st.write("입력 없이 OFF→ON 두 세션을 자동 실행하고, 진행 상황과 지표를 실시간으로 보여줍니다.")

with st.sidebar:
    st.header("Controls")
    goal = st.text_input("Goal", value="Autopilot security assessment")
    iterations = st.slider("Iterations", 1, 10, 3)
    include_toxic = st.checkbox("Include Toxic Adaptive Attacks", value=True)
    run = st.button("Run Autopilot", type="primary")

if run:
    st.session_state["auto_result"] = run_autopilot(
        goal=goal, endpoint=None, iterations=iterations, include_toxic=include_toxic
    )

auto = st.session_state.get("auto_result")
if not auto:
    st.info("좌측 Run Autopilot을 눌러 실행하세요.")
    st.stop()

col1, col2 = st.columns(2)

off_dir = Path(auto["off_dir"]).resolve()
on_dir = Path(auto["on_dir"]).resolve()

with col1:
    st.subheader(f"OFF Session — {auto['off_session']}")
    plans_off, attacks_off = _brain_files(off_dir)
    st.caption(str(plans_off))
    st.code(_read_text(plans_off), language="markdown")
    if attacks_off:
        last_off = attacks_off[-1]
        st.caption(str(last_off))
        st.code(_read_text(last_off), language="markdown")

with col2:
    st.subheader(f"ON Session — {auto['on_session']}")
    plans_on, attacks_on = _brain_files(on_dir)
    st.caption(str(plans_on))
    st.code(_read_text(plans_on), language="markdown")
    if attacks_on:
        last_on = attacks_on[-1]
        st.caption(str(last_on))
        st.code(_read_text(last_on), language="markdown")

st.divider()

col3, col4 = st.columns(2)
with col3:
    st.subheader("OFF Metrics")
    off_report = _read_json(off_dir / "REPORT.json")
    st.json(off_report.get("metrics", {}))
with col4:
    st.subheader("ON Metrics")
    on_report = _read_json(on_dir / "REPORT.json")
    st.json(on_report.get("metrics", {}))

st.divider()
st.subheader("Comparison")
st.code(_read_text(Path(auto["comparison"])), language="markdown")

# Auto refresh every 2 seconds
st.experimental_singleton.clear()
st.experimental_rerun
