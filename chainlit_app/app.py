from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

import chainlit as cl
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


@cl.on_chat_start
async def on_chat_start():
    load_dotenv()
    await cl.Message(content="MIRROR Chainlit에 오신 것을 환영합니다!\n목표(Goal)를 입력하고 모드를 선택하세요.").send()


@cl.on_message
async def on_message(msg: cl.Message):
    goal = msg.content.strip()
    if not goal:
        await cl.Message(content="목표를 입력해주세요.").send()
        return

    mode_action = await cl.AskActionMessage(
        content="모드를 선택하세요.",
        actions=[
            cl.Action(name="MIRROR", value="mirror", label="MIRROR"),
            cl.Action(name="ATTACK_ONLY", value="attack", label="Attack Only"),
        ],
    ).send()

    if not mode_action:  # canceled
        return

    mode = mode_action.value

    if mode == "mirror":
        # Collect minimal settings
        ep_msg = await cl.AskUserMessage(content="Endpoint (default: http://127.0.0.1:8000/chat)").send()
        endpoint = ep_msg.content.strip() if ep_msg and ep_msg.content.strip() else "http://127.0.0.1:8000/chat"
        settings = _default_settings()
        settings.endpoint = endpoint

        session_id = None
        ws_root = Path(".").resolve()
        config = MirrorRunConfig(workspace_root=ws_root, session_id=session_id or "chainlit")

        orch = MirrorOrchestrator(config, settings)

        loop = asyncio.get_event_loop()
        await cl.Message(content=f"MIRROR 실행 중...\nendpoint={settings.endpoint}").send()
        result = await loop.run_in_executor(None, lambda: orch.run(goal))

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
    ep_msg = await cl.AskUserMessage(content="OpenAI Chat 호환 endpoint (ex: http://127.0.0.1:8080/v1/chat/completions)").send()
    endpoint = ep_msg.content.strip() if ep_msg and ep_msg.content.strip() else "http://127.0.0.1:8080/v1/chat/completions"
    kinds_msg = await cl.AskUserMessage(content="전략(comma): dan,toxicity,prompt_injection,pii_leak").send()
    kinds = [k.strip() for k in (kinds_msg.content if kinds_msg else "dan,prompt_injection").split(",") if k.strip()]

    atk_settings = AttackSettings(endpoint=endpoint, model="gpt-4o-mini")
    agent = AttackAgent(settings=atk_settings, mutation_level="light", tries=1, concurrency=2)

    res_all = []
    for k in kinds:
        res = await agent.run_round(k, max_prompts=2)
        res_all.extend(res)

    md = AttackAgent.to_markdown(1, res_all)
    await cl.Message(content="공격 결과 요약:").send()
    await cl.Message(content=md).send()

