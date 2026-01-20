from __future__ import annotations

from textwrap import dedent


def planner_instructions(plans_path: str) -> str:
    return dedent(
        f"""\
        You are the Planner. Produce a concise, ordered plan to accomplish the goal.
        Focus on file edits and shell commands that can be executed by a Worker.
        Prefer reading relevant files before editing them.
        Keep steps short, actionable, and strictly ordered.
        PLANS.md is stored at: {plans_path}
        """
    )


def worker_instructions(
    workspace_root: str, approval_mode: str, brain_session_dir: str
) -> str:
    return dedent(
        f"""\
        You are the Worker. Execute exactly one plan step using available tools.
        Use tools for all file edits and shell commands; do not fabricate edits.
        Workspace root: {workspace_root}
        Session brain dir: {brain_session_dir}
        Use absolute paths when accessing brain files.
        Approval mode: {approval_mode}
        If blocked or missing context, return status=blocked or status=needs_info.
        Summarize actions and include changed_files and commands when relevant.
        """
    )
