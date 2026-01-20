from __future__ import annotations

from pathlib import Path
import json
import os
import secrets

import typer
from dotenv import load_dotenv
from openai import OpenAI

from mirror.core.config import ApprovalMode, OrchestratorConfig
from mirror.mirror_system.orchestrator import MirrorOrchestrator, MirrorRunConfig
from mirror.mirror_system.settings import MirrorSettings
from mirror.core.orchestrator import Orchestrator
from mirror.core.progress import enable_print_progress
from mirror.autopilot import run_autopilot
from mirror.storage.brain import BrainStore
from mirror.mirror_system.tools import build_reporter_tools
from agents import Agent, Runner
from mirror.core.prompts import session_reporter_instructions


app = typer.Typer(no_args_is_help=True)


def _require_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise typer.BadParameter("OPENAI_API_KEY is not set.")


@app.command()
def run(
    goal: str = typer.Argument(..., help="Goal for the planner/worker system."),
    workspace: Path = typer.Option(Path("."), help="Workspace root directory."),
    model: str = typer.Option("gpt-5-mini", help="Model name for OpenAI Agents."),
    max_steps: int = typer.Option(8, help="Maximum number of plan steps to run."),
    max_turns: int = typer.Option(6, help="Maximum turns per worker step."),
    approval_mode: ApprovalMode = typer.Option(
        ApprovalMode.AUTO, help="Approval mode for writes/shell commands."
    ),
    allow_outside_workspace: bool = typer.Option(
        False,
        "--allow-outside-workspace",
        help="Allow file/shell access outside the workspace root.",
    ),
    print_progress: bool = typer.Option(
        False,
        "--print-progress",
        help="Print agent/tool/LLM progress via tracing.",
    ),
    session_id: str | None = typer.Option(
        None, help="Session id for ~/.mirror/brain/{session_id}."
    ),
) -> None:
    load_dotenv()
    _require_api_key()
    _client = OpenAI()
    if not workspace.exists():
        raise typer.BadParameter(f"Workspace does not exist: {workspace}")
    if session_id is None:
        session_id = secrets.token_hex(4)
    if print_progress:
        enable_print_progress()

    config = OrchestratorConfig(
        workspace_root=workspace.resolve(),
        session_id=session_id,
        allow_outside_workspace=allow_outside_workspace,
        model=model,
        max_steps=max_steps,
        max_turns=max_turns,
        approval_mode=approval_mode,
    )

    orchestrator = Orchestrator(config)
    result = orchestrator.run(goal)

    typer.echo(f"Goal: {result.goal}")
    typer.echo(f"Session: {session_id}")
    typer.echo(f"PLANS.md: {config.plans_path()}")
    typer.echo(f"Plan objective: {result.plan.objective}")
    for outcome in result.outcomes:
        typer.echo(f"- [{outcome.step.id}] {outcome.result.status}: {outcome.result.summary}")
        if outcome.result.changed_files:
            typer.echo(f"  files: {', '.join(outcome.result.changed_files)}")
        if outcome.result.commands:
            typer.echo(f"  commands: {', '.join(outcome.result.commands)}")

    if result.replans:
        typer.echo(f"Replans: {result.replans}")


@app.command()
def mirror(
    goal: str = typer.Argument(..., help="Goal for the MIRROR system."),
    settings_path: Path = typer.Option(
        Path("settings.json"), help="Path to MIRROR settings.json."
    ),
    workspace: Path = typer.Option(Path("."), help="Workspace root directory."),
    model: str | None = typer.Option(None, help="Override model in settings."),
    session_id: str | None = typer.Option(
        None, help="Session id for ~/.mirror/brain/{session_id}."
    ),
    print_progress: bool = typer.Option(
        False,
        "--print-progress",
        help="Print agent/tool/LLM progress via tracing.",
    ),
) -> None:
    load_dotenv()
    _require_api_key()
    _client = OpenAI()
    if not settings_path.exists():
        raise typer.BadParameter(f"settings.json not found: {settings_path}")
    if not workspace.exists():
        raise typer.BadParameter(f"Workspace does not exist: {workspace}")
    if session_id is None:
        session_id = secrets.token_hex(4)
    if print_progress:
        enable_print_progress()

    raw = settings_path.read_text(encoding="utf-8")
    settings = MirrorSettings(**json.loads(raw))
    if model is not None:
        settings.model = model

    config = MirrorRunConfig(
        workspace_root=workspace.resolve(),
        session_id=session_id,
        model=settings.model,
    )
    orchestrator = MirrorOrchestrator(config, settings)
    result = orchestrator.run(goal)

    typer.echo(f"Goal: {goal}")
    typer.echo(f"Session: {session_id}")
    typer.echo(f"Brain dir: {result.brain_dir}")
    typer.echo(f"PLANS.md: {result.brain_dir / 'PLANS.md'}")
    typer.echo(f"REPORT.md: {result.brain_dir / 'REPORT.md'}")


@app.command()
def guardrail(
    rules_path: Path = typer.Option(
        None, help="Path to guardrail_rules.json (defaults to ~/.mirror/brain/default)."
    ),
    model: str = typer.Option("gpt-5-mini", help="Upstream model name."),
    host: str = typer.Option("0.0.0.0", help="Bind host."),
    port: int = typer.Option(8080, help="Bind port."),
) -> None:
    load_dotenv()
    _require_api_key()
    if rules_path is None:
        rules_path = Path.home() / ".mirror" / "brain" / "default" / "guardrail_rules.json"
    from mirror.defense.guardrail import create_app

    import uvicorn

    app_instance = create_app(rules_path=rules_path, model=model)
    uvicorn.run(app_instance, host=host, port=port)


@app.command()
def autopilot(
    goal: str = typer.Argument(..., help="Goal for automatic MIRROR runs."),
    endpoint: str = typer.Option(None, help="Target endpoint (optional, auto-detect if omitted)."),
    iterations: int = typer.Option(3, help="Max iterations per run."),
    include_toxic: bool = typer.Option(True, help="Include toxicity adaptive attacks."),
    print_progress: bool = typer.Option(False, "--print-progress", help="Print tracing."),
) -> None:
    load_dotenv()
    _require_api_key()
    if print_progress:
        enable_print_progress()
    result = run_autopilot(goal, endpoint=endpoint, iterations=iterations, include_toxic=include_toxic)
    typer.echo("Autopilot completed.")
    for k, v in result.items():
        typer.echo(f"{k}: {v}")


@app.command()
def report(
    session_id: str = typer.Argument(..., help="Session id under ~/.mirror/brain/{session_id}"),
    model: str = typer.Option("gpt-4o-mini", help="Model for the reporter agent."),
    print_progress: bool = typer.Option(False, "--print-progress", help="Print tracing."),
) -> None:
    load_dotenv()
    _require_api_key()
    _client = OpenAI()

    if print_progress:
        enable_print_progress()

    brain_dir = (Path.home() / ".mirror" / "brain" / session_id).resolve()
    if not brain_dir.exists():
        raise typer.BadParameter(f"Brain dir not found: {brain_dir}")

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
    output_md = run.final_output
    target = brain_dir / "REPORT.md"
    target.write_text(str(output_md), encoding="utf-8")
    typer.echo(f"Report written: {target}")


if __name__ == "__main__":
    app()
