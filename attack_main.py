from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer

from attack_agent.config import load_settings, Settings
from attack_agent.attack_agent import AttackAgent
from attack_agent.garak_loader import load_garak_prompts


app = typer.Typer(help="Run minimal Attack Agent rounds against an OpenAI-compatible endpoint.")


@app.command()
def run(
    settings_path: Optional[str] = typer.Option(None, help="Path to settings.json"),
    endpoint: Optional[str] = typer.Option(None, help="Override target endpoint"),
    model: str = typer.Option("gpt-4o-mini", help="Model name to send to target"),
    strategies: str = typer.Option("dan,toxicity,prompt_injection", help="Comma-separated kinds"),
    mutation_level: str = typer.Option("light", help="light|medium|heavy"),
    max_prompts: int = typer.Option(3, help="Max prompts per strategy"),
    concurrency: int = typer.Option(4, help="Concurrent calls per round"),
    tries: int = typer.Option(1, help="Multi-turn attempts per prompt"),
    garak_probes: Optional[str] = typer.Option(None, help="Comma-separated garak probe paths (overrides prompts)"),
    round_id: int = typer.Option(1, help="Round index for report naming"),
    out_md: str = typer.Option("docs/ATTACK_1.md", help="Where to write markdown report"),
    out_json: Optional[str] = typer.Option(None, help="Optional JSON summary output path"),
):
    settings: Settings = load_settings(settings_path)
    if endpoint:
        settings.endpoint = endpoint
    settings.model = model or settings.model

    agent = AttackAgent(
        settings=settings,
        mutation_level=mutation_level,
        tries=tries,
        concurrency=concurrency,
    )
    kinds = [k.strip() for k in strategies.split(",") if k.strip()]

    async def _run():
        all_results = []
        for k in kinds:
            prompts_override = None
            if garak_probes:
                probe_paths = [p.strip() for p in garak_probes.split(",") if p.strip()]
                prompts_override = load_garak_prompts(probe_paths, max_count=max_prompts)
            res = await agent.run_round(k, max_prompts=max_prompts, prompts_override=prompts_override)
            all_results.extend(res)
        md = AttackAgent.to_markdown(round_id, all_results)
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(out_md).write_text(md, encoding="utf-8")
        typer.echo(f"Wrote report: {out_md}")
        if out_json:
            data = AttackAgent.to_json(round_id, all_results)
            Path(out_json).parent.mkdir(parents=True, exist_ok=True)
            Path(out_json).write_text(__import__("json").dumps(data, indent=2), encoding="utf-8")
            typer.echo(f"Wrote JSON: {out_json}")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
