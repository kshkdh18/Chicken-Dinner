from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

import chainlit as cl
import re
import httpx
from dotenv import load_dotenv

from mirror.mirror_orchestrator import MirrorOrchestrator, MirrorRunConfig
from mirror.mirror_settings import MirrorSettings
from mirror.brain import BrainStore
from mirror.mirror_tools import build_reporter_tools
from mirror.prompts import session_reporter_instructions
from agents import Agent, Runner

from attack_agent.attack_agent import AttackAgent
from attack_agent.config import Settings as AttackSettings


def _default_settings() -> MirrorSettings:
    return MirrorSettings(
        mode="guardrail-off",
        endpoint="http://127.0.0.1:8000/chat",
        endpoint_format="simple-rag",
        max_iterations=2,
        attack_categories=["prompt_injection", "pii_leak"],
        model="gpt-4o-mini",
        target_model="gpt-4o-mini",
    )


def _is_url(s: str) -> bool:
    return bool(re.match(r"^https?://", s))


async def _show_menu():
    await cl.Message(
        content=(
            "모드를 선택하세요.\n- MIRROR: 블랙박스(`/chat`) 평가 루프\n"
            "- Attack Only: OpenAI Chat 호환(`/v1/chat/completions`) 공격\n"
            "- Report: 세션 리포트 생성"
        ),
        actions=[
            cl.Action(name="pick_mode", value="mirror", label="MIRROR", payload={"mode": "mirror"}),
            cl.Action(name="pick_mode", value="attack", label="Attack Only", payload={"mode": "attack"}),
            cl.Action(name="pick_mode", value="report", label="Report", payload={"mode": "report"}),
        ],
    ).send()


@cl.on_chat_start
async def on_chat_start():
    load_dotenv()
    await cl.Message(content="MIRROR Chainlit에 오신 것을 환영합니다!\n먼저 목표(Goal)를 입력하세요.").send()


@cl.on_message
async def on_message(msg: cl.Message):
    goal = msg.content.strip()
    if not goal:
        await cl.Message(content="목표를 입력해주세요.").send()
        return

    cl.user_session.set("goal", goal)
    await _show_menu()
    return


@cl.action_callback("pick_mode")
async def on_pick_mode(action: cl.Action):
    goal = cl.user_session.get("goal") or "Security assessment"
    mode = (action.payload or {}).get("mode") or action.value or ""
    mode = str(mode).lower()

    if mode == "mirror":
        # Collect minimal settings
        ep_msg = await cl.AskUserMessage(content="Endpoint (기본: http://127.0.0.1:8000/chat)").send()
        endpoint = ep_msg.content.strip() if ep_msg and ep_msg.content.strip() else "http://127.0.0.1:8000/chat"
        if not _is_url(endpoint):
            await cl.Message(content=f"유효한 URL이 아닙니다: {endpoint}").send()
            return
        # 가벼운 헬스체크
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                _ = await client.post(endpoint, json={"message": "health"})
        except Exception:
            await cl.Message(content=f"엔드포인트 연결 실패: {endpoint}").send()
            return
        settings = _default_settings()
        settings.endpoint = endpoint

        session_id = None
        ws_root = Path(".").resolve()
        config = MirrorRunConfig(workspace_root=ws_root, session_id=session_id or "chainlit")

        orch = MirrorOrchestrator(config, settings)

        loop = asyncio.get_event_loop()
        await cl.Message(content=f"MIRROR 실행 중...\nendpoint={settings.endpoint}").send()

        # Live tail of session brain while orchestrator runs
        brain_dir = (Path.home() / ".mirror" / "brain" / (config.session_id or "chainlit")).resolve()

        async def tail_brain(dir_path: Path):
            seen: dict[str, int] = {}
            while True:
                files = []
                if (dir_path / "PLANS.md").exists():
                    files.append(dir_path / "PLANS.md")
                files.extend(sorted(dir_path.glob("ATTACK_*.md")))
                for f in files:
                    try:
                        text = f.read_text(encoding="utf-8")
                        key = str(f)
                        prev = seen.get(key, 0)
                        if len(text) > prev:
                            new = text[prev:]
                            snippet = new[-2000:]
                            await cl.Message(content=f"{f.name} 업데이트\n```\n{snippet}\n```", author="Log").send()
                            seen[key] = len(text)
                    except Exception:
                        pass
                await asyncio.sleep(1.0)

        tail_task = asyncio.create_task(tail_brain(brain_dir))
        try:
            result = await loop.run_in_executor(None, lambda: orch.run(goal))
        except Exception as e:
            await cl.Message(content=f"오류 발생: {e}").send()
            return
        finally:
            tail_task.cancel()

        brain_dir = result.brain_dir
        await cl.Message(content=f"세션 완료: {brain_dir}\nPLANS: {brain_dir / 'PLANS.md'}").send()

        # Generate session report
        brain = BrainStore(brain_dir)
        reporter = Agent(
            name="Session Reporter",
            instructions=session_reporter_instructions(str(brain_dir)),
            tools=build_reporter_tools(brain),
            model=settings.model,
        )
        run = Runner.run_sync(reporter, input="Generate report", max_turns=8)
        md = str(run.final_output)
        (brain_dir / "REPORT.md").write_text(md, encoding="utf-8")
        await cl.Message(content="세션 리포트 생성 완료 (REPORT.md)").send()
        await cl.Message(content=md).send()
        return

    # Attack only (OpenAI Chat compatible endpoint)
    ep_msg = await cl.AskUserMessage(content="OpenAI Chat 호환 endpoint (예: http://127.0.0.1:8080/v1/chat/completions)").send()
    endpoint = ep_msg.content.strip() if ep_msg and ep_msg.content.strip() else "http://127.0.0.1:8080/v1/chat/completions"
    if not _is_url(endpoint):
        await cl.Message(content=f"유효한 URL이 아닙니다: {endpoint}").send()
        return
    kinds_msg = await cl.AskUserMessage(content="전략(comma): dan,toxicity,prompt_injection,pii_leak (기본: dan,prompt_injection)").send()
    kinds = [k.strip() for k in (kinds_msg.content if kinds_msg else "dan,prompt_injection").split(",") if k.strip()]

    atk_settings = AttackSettings(endpoint=endpoint, model="gpt-4o-mini")
    agent = AttackAgent(settings=atk_settings, mutation_level="light", tries=1, concurrency=2)

    res_all = []
    try:
        for k in kinds:
            res = await agent.run_round(k, max_prompts=2)
            res_all.extend(res)
    except Exception as e:
        await cl.Message(content=f"공격 실행 중 오류: {e}").send()
        return

    md = AttackAgent.to_markdown(1, res_all)
    await cl.Message(content="공격 결과 요약:").send()
    await cl.Message(content=md).send()
    await _show_menu()
    return

    # Report mode
    # (action handler 상단 분기에서 처리)
