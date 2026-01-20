from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

import typer
from dotenv import load_dotenv
from openai import OpenAI

from .core import ApprovalMode, Orchestrator, OrchestratorConfig
from .core.progress import enable_print_progress
from .mirror_system import MirrorOrchestrator, MirrorRunConfig, MirrorSettings

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
    import uvicorn

    from .guardrail import create_app

    app_instance = create_app(rules_path=rules_path, model=model)
    uvicorn.run(app_instance, host=host, port=port)


if __name__ == "__main__":
    app()
