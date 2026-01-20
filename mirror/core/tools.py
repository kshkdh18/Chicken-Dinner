from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any

from agents import function_tool

from mirror.core.config import ApprovalMode, OrchestratorConfig
from mirror.storage.workspace import CommandPolicy, Workspace


def _result(ok: bool, **payload: Any) -> dict[str, Any]:
    return {"ok": ok, **payload}


def _strip_patch_prefix(path: str) -> str:
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def _normalize_patch(patch: str) -> tuple[str, list[str]]:
    lines = patch.splitlines()
    normalized: list[str] = []
    paths: list[str] = []

    for line in lines:
        if line.startswith(("--- ", "+++ ")):
            prefix = line[:4]
            rest = line[4:].strip()
            if not rest:
                normalized.append(line)
                continue
            token = rest.split()[0]
            if token == "/dev/null":
                normalized.append(f"{prefix}{token}")
                continue
            cleaned = _strip_patch_prefix(token)
            if cleaned.startswith("/"):
                raise ValueError("Absolute paths are not allowed in patches.")
            paths.append(cleaned)
            normalized.append(f"{prefix}{cleaned}")
            continue

        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                left = _strip_patch_prefix(parts[2])
                right = _strip_patch_prefix(parts[3])
                normalized.append(f"diff --git {left} {right}")
            else:
                normalized.append(line)
            continue

        normalized.append(line)

    joined = "\n".join(normalized)
    if patch.endswith("\n"):
        joined += "\n"
    return joined, list(dict.fromkeys(paths))


@dataclass
class ToolBox:
    workspace: Workspace
    approval_mode: ApprovalMode
    command_timeout: int
    max_write_bytes: int
    command_policy: CommandPolicy

    def _ensure_write_allowed(self) -> None:
        if self.approval_mode in {ApprovalMode.CONFIRM_WRITES, ApprovalMode.CONFIRM_ALL}:
            raise PermissionError("Write approval required by approval_mode.")

    def _ensure_shell_allowed(self) -> None:
        if self.approval_mode in {ApprovalMode.CONFIRM_SHELL, ApprovalMode.CONFIRM_ALL}:
            raise PermissionError("Shell approval required by approval_mode.")

    def read_file(self, path: str, offset: int = 0, limit: int = 2000) -> dict[str, Any]:
        file_path = self.workspace.resolve_path(path)
        if not file_path.exists():
            return _result(False, error=f"File not found: {path}")
        if file_path.is_dir():
            return _result(False, error=f"Path is a directory: {path}")

        size = file_path.stat().st_size
        if size > self.workspace.max_file_size:
            return _result(False, error=f"File too large: {path} ({size} bytes)")

        if offset < 0 or limit <= 0:
            return _result(False, error="Offset must be >= 0 and limit must be > 0.")

        with file_path.open("rb") as handle:
            handle.seek(offset)
            data = handle.read(limit)

        content = data.decode("utf-8", errors="replace")
        next_offset = offset + len(data)
        truncated = next_offset < size

        return _result(
            True,
            path=path,
            offset=offset,
            limit=limit,
            truncated=truncated,
            next_offset=next_offset if truncated else None,
            content=content,
        )

    def list_dir(self, path: str = ".", max_entries: int = 200) -> dict[str, Any]:
        dir_path = self.workspace.resolve_path(path)
        if not dir_path.exists():
            return _result(False, error=f"Path not found: {path}")
        if not dir_path.is_dir():
            return _result(False, error=f"Path is not a directory: {path}")
        if max_entries <= 0:
            return _result(False, error="max_entries must be > 0.")

        entries = []
        truncated = False
        for entry in sorted(dir_path.iterdir(), key=lambda item: item.name):
            if len(entries) >= max_entries:
                truncated = True
                break
            entries.append(
                {
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                }
            )

        return _result(True, path=path, entries=entries, truncated=truncated)

    def write_file(self, path: str, content: str, create_dirs: bool = True) -> dict[str, Any]:
        self._ensure_write_allowed()

        file_path = self.workspace.resolve_path(path)
        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        payload = content.encode("utf-8")
        if len(payload) > self.max_write_bytes:
            return _result(False, error="Content exceeds max_write_bytes limit.")

        tmp_dir = file_path.parent
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=tmp_dir) as handle:
            handle.write(payload)
            temp_name = handle.name

        os.replace(temp_name, file_path)
        return _result(True, path=path, bytes_written=len(payload))

    def edit_file(
        self,
        path: str,
        old_string: str,
        new_string: str,
        expected_count: int = 1,
        allow_fuzzy: bool = False,
    ) -> dict[str, Any]:
        self._ensure_write_allowed()

        if allow_fuzzy:
            return _result(False, error="Fuzzy matching is not supported.")

        file_path = self.workspace.resolve_path(path)
        if not file_path.exists():
            return _result(False, error=f"File not found: {path}")
        if file_path.is_dir():
            return _result(False, error=f"Path is a directory: {path}")
        if file_path.stat().st_size > self.workspace.max_file_size:
            return _result(False, error="File exceeds max_read_bytes limit.")

        text = file_path.read_text(encoding="utf-8")
        count = text.count(old_string)
        if count == 0:
            return _result(False, error="old_string not found.")
        if count != expected_count:
            return _result(
                False,
                error=f"old_string match count {count} does not equal expected_count {expected_count}.",
            )

        updated = text.replace(old_string, new_string, expected_count)
        if updated == text:
            return _result(False, error="No changes applied.")

        payload = updated.encode("utf-8")
        if len(payload) > self.max_write_bytes:
            return _result(False, error="Updated content exceeds max_write_bytes limit.")

        file_path.write_text(updated, encoding="utf-8")
        return _result(True, path=path, replacements=expected_count)

    def apply_patch(self, patch: str) -> dict[str, Any]:
        self._ensure_write_allowed()

        if not patch.strip():
            return _result(False, error="Patch is empty.")

        try:
            normalized, paths = _normalize_patch(patch)
        except ValueError as exc:
            return _result(False, error=str(exc))

        if not paths:
            return _result(False, error="No file paths found in patch.")

        for path in paths:
            try:
                self.workspace.resolve_path(path)
            except ValueError as exc:
                return _result(False, error=str(exc))

        patch_cmd = shutil.which("patch")
        if not patch_cmd:
            return _result(False, error="patch command not available on this system.")

        try:
            completed = subprocess.run(
                [patch_cmd, "-p0", "--batch", "--forward"],
                cwd=self.workspace.root,
                input=normalized,
                text=True,
                capture_output=True,
                timeout=self.command_timeout,
            )
        except subprocess.TimeoutExpired:
            return _result(False, error="Patch command timed out.")

        if completed.returncode != 0:
            return _result(
                False,
                error="Patch failed to apply.",
                stdout=completed.stdout,
                stderr=completed.stderr,
            )

        return _result(
            True,
            paths=paths,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def search_text(
        self, pattern: str, path: str = ".", max_matches: int = 200
    ) -> dict[str, Any]:
        search_path = self.workspace.resolve_path(path)
        if not search_path.exists():
            return _result(False, error=f"Path not found: {path}")
        if max_matches <= 0:
            return _result(False, error="max_matches must be > 0.")

        rg = shutil.which("rg")
        if rg:
            cmd = [
                rg,
                "--line-number",
                "--with-filename",
                "--max-count",
                str(max_matches),
                pattern,
                str(search_path),
            ]
        else:
            cmd = [
                "grep",
                "-R",
                "-n",
                "-m",
                str(max_matches),
                pattern,
                str(search_path),
            ]

        try:
            completed = subprocess.run(
                cmd,
                cwd=self.workspace.root,
                text=True,
                capture_output=True,
                timeout=self.command_timeout,
            )
        except subprocess.TimeoutExpired:
            return _result(False, error="Search command timed out.")

        if completed.returncode not in (0, 1):
            return _result(False, error=completed.stderr.strip() or "Search failed.")

        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        return _result(True, pattern=pattern, path=path, matches=lines)

    def run_shell(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        self._ensure_shell_allowed()

        deny_match = self.command_policy.check(command)
        if deny_match:
            return _result(False, error=f"Command blocked by policy: {deny_match}")

        working_dir = self.workspace.resolve_cwd(cwd)
        run_timeout = timeout or self.command_timeout

        exec_env = os.environ.copy()

        try:
            completed = subprocess.run(
                command,
                cwd=working_dir,
                shell=True,
                text=True,
                capture_output=True,
                timeout=run_timeout,
                env=exec_env,
            )
        except subprocess.TimeoutExpired:
            return _result(False, error=f"Command timed out after {run_timeout} seconds.")

        return _result(
            True,
            command=command,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def build_toolbox(config: OrchestratorConfig) -> ToolBox:
    brain_dir = config.brain_session_dir().resolve()
    workspace = Workspace(
        root=config.workspace_root,
        max_file_size=config.max_read_bytes,
        extra_roots=(brain_dir,),
        allow_outside=config.allow_outside_workspace,
    )
    return ToolBox(
        workspace=workspace,
        approval_mode=config.approval_mode,
        command_timeout=config.command_timeout,
        max_write_bytes=config.max_write_bytes,
        command_policy=CommandPolicy(),
    )


def build_tools(config: OrchestratorConfig) -> list[Any]:
    toolbox = build_toolbox(config)

    @function_tool
    def read_file(path: str, offset: int = 0, limit: int = 2000) -> dict[str, Any]:
        """Read a file slice with offset/limit, returning truncation info."""
        return toolbox.read_file(path=path, offset=offset, limit=limit)

    @function_tool
    def list_dir(path: str = ".", max_entries: int = 200) -> dict[str, Any]:
        """List directory contents with a maximum number of entries."""
        return toolbox.list_dir(path=path, max_entries=max_entries)

    @function_tool
    def write_file(path: str, content: str, create_dirs: bool = True) -> dict[str, Any]:
        """Write a file atomically, creating directories when requested."""
        return toolbox.write_file(path=path, content=content, create_dirs=create_dirs)

    @function_tool
    def edit_file(
        path: str,
        old_string: str,
        new_string: str,
        expected_count: int = 1,
        allow_fuzzy: bool = False,
    ) -> dict[str, Any]:
        """Replace an exact string occurrence with verification."""
        return toolbox.edit_file(
            path=path,
            old_string=old_string,
            new_string=new_string,
            expected_count=expected_count,
            allow_fuzzy=allow_fuzzy,
        )

    @function_tool
    def apply_patch(patch: str) -> dict[str, Any]:
        """Apply a unified diff patch with workspace path safeguards."""
        return toolbox.apply_patch(patch=patch)

    @function_tool
    def search_text(
        pattern: str, path: str = ".", max_matches: int = 200
    ) -> dict[str, Any]:
        """Search files for a pattern using rg if available, otherwise grep."""
        return toolbox.search_text(pattern=pattern, path=path, max_matches=max_matches)

    @function_tool
    def run_shell(
        command: str,
        cwd: str | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Execute a shell command inside the workspace with a timeout. To set environment variables, use shell syntax (e.g., 'ENV_VAR=value command')."""
        return toolbox.run_shell(command=command, cwd=cwd, timeout=timeout)

    return [read_file, list_dir, write_file, edit_file, apply_patch, search_text, run_shell]
