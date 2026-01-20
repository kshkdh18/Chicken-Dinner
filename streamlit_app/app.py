from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Tuple

import streamlit as st

from mirror.autopilot import discover_endpoint, run_autopilot, write_comparison
from mirror.brain import BrainStore
from mirror.mirror_tools import build_reporter_tools
from mirror.prompts import session_reporter_instructions
from agents import Agent, Runner
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


def _run_mirror(goal: str, session_id: str, mode: str, iterations: int, include_toxic: bool, white_box_path: str | None) -> Tuple[str, str]:
    endpoint, fmt = discover_endpoint()
    settings = MirrorSettings(
        mode=mode,
        endpoint=endpoint,
        endpoint_format=fmt,
        max_iterations=iterations,
        use_toxic_small_llm=include_toxic,
        white_box_path=white_box_path,
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


def _compute_live_metrics(events: List[dict]) -> dict:
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


def _regenerate_report(brain_dir: Path, model: str = "gpt-4o-mini") -> str:
    try:
        brain = BrainStore(brain_dir)
        agent = Agent(
            name="Session Reporter",
            instructions=session_reporter_instructions(str(brain_dir)),
            tools=build_reporter_tools(brain),
            model=model,
        )
        prompt = (
            "Generate a polished Markdown report for this session. "
            "Use tools to read PLANS.md and all ATTACK_n.md files and compute metrics."
        )
        run = Runner.run_sync(agent, input=prompt, max_turns=8)
        md = str(run.final_output)
        (brain_dir / "REPORT.md").write_text(md, encoding="utf-8")
        return "OK"
    except Exception as e:
        return f"ERROR: {e}"


st.set_page_config(page_title="MIRROR Autopilot", layout="wide")
st.title("MIRROR Autopilot (LIVE)")
st.write("OFF→ON 전체 플로우를 스냅샷 또는 실시간으로 보고, REPORT 에이전트 결과까지 확인합니다.")

if "executor" not in st.session_state:
    st.session_state.executor = ThreadPoolExecutor(max_workers=2)

with st.sidebar:
    st.header("Controls")
    goal = st.text_input("Goal", value="Autopilot security assessment", placeholder="예: /Users/you/path/image.jpg 또는 시나리오 설명")
    iterations = st.slider("Iterations", 1, 10, 3)
    with st.expander("Advanced", expanded=False):
        include_toxic = st.checkbox("Include Toxic Adaptive Attacks", value=True)
    run_auto_live = st.button("Run", type="primary")

def _render_session(title: str, session_dir: Path):
    st.subheader(title)
    plans, attacks = _brain_files(session_dir)
    st.caption(str(plans))
    st.code(_read_text(plans), language="markdown")
    if attacks:
        names = [p.name for p in attacks]
        sel = st.selectbox("Select ATTACK file", names, index=len(names) - 1, key=f"sel_{session_dir.name}")
        pick = next((p for p in attacks if p.name == sel), attacks[-1])
        st.caption(str(pick))
        st.code(_read_text(pick), language="markdown")
        with st.expander("All ATTACK files", expanded=False):
            for p in attacks:
                st.caption(p.name)
                st.code(_read_text(p), language="markdown")

def _render_report_section(dir_path: Path, title_prefix: str):
    st.subheader(f"{title_prefix} Metrics")
    rep = _read_json(dir_path / "REPORT.json")
    st.json(rep.get("metrics", {}))
    st.subheader(f"{title_prefix} REPORT.md")
    st.code(_read_text(dir_path / "REPORT.md"), language="markdown")
    if st.button(f"Regenerate Report — {title_prefix}"):
        status = _regenerate_report(dir_path)
        if status != "OK":
            st.warning(status)
        else:
            st.success("Report regenerated.")

## Snapshot section removed for minimal UI

def _run_auto_pair(goal: str, iterations: int, include_toxic: bool, off_id: str, on_id: str) -> dict:
    endpoint, fmt = discover_endpoint()
    # OFF
    settings_off = MirrorSettings(
        mode="guardrail-off", endpoint=endpoint, endpoint_format=fmt,
        max_iterations=iterations, use_toxic_small_llm=include_toxic,
    )
    config_off = MirrorRunConfig(workspace_root=Path(".").resolve(), session_id=off_id)
    orch_off = MirrorOrchestrator(config_off, settings_off)
    res_off = orch_off.run(goal)
    # ON
    settings_on = MirrorSettings(
        mode="guardrail-on", endpoint=endpoint, endpoint_format=fmt,
        max_iterations=iterations, use_toxic_small_llm=include_toxic,
    )
    config_on = MirrorRunConfig(workspace_root=Path(".").resolve(), session_id=on_id)
    orch_on = MirrorOrchestrator(config_on, settings_on)
    res_on = orch_on.run(goal)
    # Comparison
    compare_path = Path(res_off.brain_dir).parent / "AUTOPILOT_COMPARISON.md"
    write_comparison(res_off.brain_dir, res_on.brain_dir, compare_path)
    return {"off_dir": str(res_off.brain_dir), "on_dir": str(res_on.brain_dir), "comparison": str(compare_path)}

# LIVE Autopilot (OFF→ON)
if run_auto_live:
    off_id = f"live_off_{int(time.time())}"
    on_id = f"live_on_{int(time.time())}"
    st.session_state["auto_live_off_id"] = off_id
    st.session_state["auto_live_on_id"] = on_id
    fut = st.session_state.executor.submit(_run_auto_pair, goal, iterations, include_toxic, off_id, on_id)
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
            # 힌트: ON 세션은 OFF 완료 후 시작됩니다.
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

## Removed legacy OFF-only live mode for minimal UI
