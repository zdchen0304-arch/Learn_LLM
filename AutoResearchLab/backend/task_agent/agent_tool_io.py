"""I/O and filesystem tool execution helpers for Task Agent tools."""

import shlex
from pathlib import Path

import orjson

from db import (
    DB_DIR,
    _validate_idea_id,
    _validate_plan_id,
    get_execution_task_src_dir,
    get_sandbox_dir,
    get_task_artifact,
)

from .docker_runtime import run_command_in_container


def get_plan_dir_path(idea_id: str, plan_id: str) -> Path:
    """Return absolute path to db/{idea_id}/{plan_id}/ with validated IDs."""
    _validate_idea_id(idea_id)
    _validate_plan_id(plan_id)
    return (DB_DIR / idea_id / plan_id).resolve()


def get_task_root_dir(
    idea_id: str,
    plan_id: str,
    task_id: str,
    execution_run_id: str = "",
) -> Path:
    if execution_run_id:
        return get_execution_task_src_dir(execution_run_id, task_id).resolve()
    return get_sandbox_dir(idea_id, plan_id, task_id)


def normalize_sandbox_subpath(path: str) -> tuple[str, str]:
    normalized = (path or "").replace("\\", "/").strip()
    if not normalized.startswith("sandbox/"):
        return normalized, ""
    subpath = normalized[7:].lstrip("/")
    return normalized, subpath


async def run_read_artifact(idea_id: str, plan_id: str, task_id: str) -> str:
    """Execute ReadArtifact. Returns content string or error message."""
    try:
        if not task_id or not isinstance(task_id, str):
            return "Error: task_id must be a non-empty string"
        if ".." in task_id or "/" in task_id or "\\" in task_id:
            return "Error: task_id must not contain path separators"
        value = await get_task_artifact(idea_id, plan_id, task_id)
        if value is None:
            return f"Error: Task '{task_id}' has no output yet (not completed or does not exist)."
        try:
            return orjson.dumps(value, option=orjson.OPT_INDENT_2).decode("utf-8")
        except (TypeError, ValueError):
            return str(value)
    except Exception as e:
        return f"Error reading artifact: {e}"


async def run_read_file(
    idea_id: str,
    plan_id: str,
    path: str,
    task_id: str = "",
    execution_run_id: str = "",
    docker_container_name: str = "",
    command_runner=run_command_in_container,
) -> str:
    """Execute ReadFile. In execution mode only sandbox paths are allowed."""
    try:
        if not path or not isinstance(path, str):
            return "Error: path must be a non-empty string"
        path, subpath = normalize_sandbox_subpath(path)
        if ".." in path:
            return "Error: path traversal not allowed"
        if execution_run_id and not path.startswith("sandbox/"):
            return "Error: execution-mode ReadFile only supports sandbox paths"
        if path.startswith("sandbox/") and execution_run_id and docker_container_name:
            if not task_id:
                return "Error: sandbox path requires task context"
            if not subpath:
                return "Error: sandbox path must include filename"
            import base64

            target_path = f"/workdir/src/{subpath}"
            cmd = f"cat {shlex.quote(target_path)} | base64"
            result = await command_runner(
                container_name=docker_container_name,
                command=cmd,
                workdir="/workdir/src",
            )
            if result.get("code") != 0:
                return f"Error reading file from docker: {result.get('stderr')}"
            out_b64 = result.get("stdout", "").strip()
            try:
                return base64.b64decode(out_b64).decode("utf-8", errors="replace")
            except Exception as e:
                return f"Error decoding file from docker: {str(e)}"

        plan_dir = get_plan_dir_path(idea_id, plan_id)
        if path.startswith("sandbox/"):
            if not task_id:
                return "Error: sandbox path requires task context"
            sandbox_dir = get_task_root_dir(idea_id, plan_id, task_id, execution_run_id)
            if not subpath:
                return "Error: sandbox path must include filename"
            full = (sandbox_dir / subpath).resolve()
            try:
                full.relative_to(sandbox_dir.resolve())
            except ValueError:
                return "Error: path traversal not allowed"
        else:
            full = (plan_dir / path).resolve()
            try:
                full.relative_to(plan_dir)
            except ValueError:
                return "Error: path traversal not allowed"
        if not full.exists():
            return f"Error: File not found: {path}"
        if not full.is_file():
            return f"Error: Not a file: {path}"

        return full.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


async def run_write_file(
    idea_id: str,
    plan_id: str,
    path: str,
    content: str,
    task_id: str = "",
    execution_run_id: str = "",
    docker_container_name: str = "",
    command_runner=run_command_in_container,
) -> str:
    """Execute WriteFile. Path must be under sandbox."""
    try:
        if not task_id:
            return "Error: WriteFile requires task context"
        if not path or not isinstance(path, str):
            return "Error: path must be a non-empty string"
        path, subpath = normalize_sandbox_subpath(path)
        if ".." in path or not path.startswith("sandbox/"):
            return "Error: path must be under sandbox (e.g. sandbox/notes.txt)"
        if not subpath:
            return "Error: path must include filename"

        if execution_run_id and docker_container_name:
            import base64
            from pathlib import Path as PyPath

            target_path = f"/workdir/src/{subpath}"
            parent_dir = str(PyPath(target_path).parent).replace('\\\\', '/')
            content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            cmd = (
                f"mkdir -p {shlex.quote(parent_dir)} && "
                f"echo {content_b64} | base64 -d > {shlex.quote(target_path)}"
            )
            result = await command_runner(
                container_name=docker_container_name,
                command=cmd,
                workdir="/workdir/src",
            )
            if result.get("code") != 0:
                return f"Error writing file in docker: {result.get('stderr')}"
            return "OK"

        sandbox_dir = get_task_root_dir(idea_id, plan_id, task_id, execution_run_id)
        full = (sandbox_dir / subpath).resolve()
        try:
            full.relative_to(sandbox_dir.resolve())
        except ValueError:
            return "Error: path traversal not allowed"

        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content or "", encoding="utf-8")
        return "OK"
    except Exception as e:
        return f"Error writing file: {e}"


async def run_list_files(
    idea_id: str,
    plan_id: str,
    path: str,
    task_id: str = "",
    execution_run_id: str = "",
    docker_container_name: str = "",
    max_entries: int = 200,
    max_depth: int = 3,
    command_runner=run_command_in_container,
) -> str:
    """Execute ListFiles. In execution mode only sandbox paths are allowed."""
    try:
        normalized_path = (path or "sandbox/").strip() or "sandbox/"
        normalized_path, subpath = normalize_sandbox_subpath(normalized_path)
        if ".." in normalized_path:
            return "Error: path traversal not allowed"

        max_entries = max(1, min(int(max_entries or 200), 500))
        max_depth = max(0, min(int(max_depth or 3), 8))

        if execution_run_id and not normalized_path.startswith("sandbox/"):
            return "Error: execution-mode ListFiles only supports sandbox paths"

        if execution_run_id and docker_container_name:
            if not task_id:
                return "Error: sandbox path requires task context"
            target_path = "/workdir/src"
            if subpath:
                target_path = f"/workdir/src/{subpath}"
            cmd = (
                f"if [ -d {shlex.quote(target_path)} ]; then "
                f"cd {shlex.quote(target_path)} && "
                f"find . -mindepth 1 -maxdepth {max_depth} | "
                "sed 's#^\\./##' | "
                f"head -n {max_entries}; "
                "else echo '__MAARS_NOT_FOUND_OR_DIR__'; fi"
            )
            result = await command_runner(
                container_name=docker_container_name,
                command=cmd,
                workdir="/workdir/src",
                timeout_seconds=30,
            )
            if result.get("code") != 0:
                return f"Error listing files from docker: {result.get('stderr')}"
            stdout = (result.get("stdout") or "").strip()
            if stdout == "__MAARS_NOT_FOUND_OR_DIR__":
                return f"Error: Path not found or not a directory: {normalized_path}"
            items = [line.strip() for line in stdout.splitlines() if line.strip()]
            body = {
                "path": normalized_path,
                "count": len(items),
                "items": items,
                "truncated": len(items) >= max_entries,
            }
            return orjson.dumps(body, option=orjson.OPT_INDENT_2).decode("utf-8")

        plan_dir = get_plan_dir_path(idea_id, plan_id)
        if normalized_path.startswith("sandbox/"):
            if not task_id:
                return "Error: sandbox path requires task context"
            sandbox_dir = get_task_root_dir(idea_id, plan_id, task_id, execution_run_id)
            target_dir = sandbox_dir if not subpath else (sandbox_dir / subpath).resolve()
            try:
                target_dir.relative_to(sandbox_dir.resolve())
            except ValueError:
                return "Error: path traversal not allowed"
        else:
            target_dir = (plan_dir / normalized_path).resolve()
            try:
                target_dir.relative_to(plan_dir)
            except ValueError:
                return "Error: path traversal not allowed"

        if not target_dir.exists():
            return f"Error: Path not found: {normalized_path}"
        if not target_dir.is_dir():
            return f"Error: Not a directory: {normalized_path}"

        entries: list[str] = []
        base_parts = len(target_dir.parts)
        for item in sorted(target_dir.rglob("*"), key=lambda p: p.as_posix()):
            rel_parts = len(item.parts) - base_parts
            if rel_parts <= 0 or rel_parts > max_depth:
                continue
            rel = item.relative_to(target_dir).as_posix()
            entries.append(rel + ("/" if item.is_dir() else ""))
            if len(entries) >= max_entries:
                break

        body = {
            "path": normalized_path,
            "count": len(entries),
            "items": entries,
            "truncated": len(entries) >= max_entries,
        }
        return orjson.dumps(body, option=orjson.OPT_INDENT_2).decode("utf-8")
    except Exception as e:
        return f"Error listing files: {e}"


