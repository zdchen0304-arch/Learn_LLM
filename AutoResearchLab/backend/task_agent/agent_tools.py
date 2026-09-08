"""Agent tools facade for Task Agent executor."""

import json
import os
from pathlib import Path
from typing import Any, Optional, Tuple

from . import web_tools
from .agent_tool_defs import TOOLS
from .agent_tool_finish import run_finish
from .agent_tool_io import (
    run_list_files as _run_list_files_impl,
    run_read_artifact,
    run_read_file as _run_read_file_impl,
    run_write_file as _run_write_file_impl,
)
from .agent_tool_command import run_run_command as _run_run_command_impl
from .agent_tool_skills import (
    run_list_skills as _run_list_skills,
    run_load_skill as _run_load_skill,
    run_read_skill_file as _run_read_skill_file,
    run_run_skill_script as _run_run_skill_script,
)
from .docker_runtime import run_command_in_container

_RUN_SCRIPT_ALLOWED_EXT = (".py", ".sh", ".js")
_RUN_SCRIPT_TIMEOUT = int(os.environ.get("MAARS_RUN_SCRIPT_TIMEOUT", "120"))

_TASK_SKILLS_DIR = os.environ.get("MAARS_TASK_SKILLS_DIR")
SKILLS_ROOT = (
    Path(_TASK_SKILLS_DIR).resolve()
    if _TASK_SKILLS_DIR
    else Path(__file__).resolve().parent / "skills"
)


def run_list_skills() -> str:
    return _run_list_skills(SKILLS_ROOT)


def run_load_skill(name: str) -> str:
    return _run_load_skill(SKILLS_ROOT, name)


def run_read_skill_file(skill: str, path: str) -> str:
    return _run_read_skill_file(SKILLS_ROOT, skill, path)


async def run_read_file(
    idea_id: str,
    plan_id: str,
    path: str,
    task_id: str = "",
    execution_run_id: str = "",
    docker_container_name: str = "",
) -> str:
    return await _run_read_file_impl(
        idea_id,
        plan_id,
        path,
        task_id,
        execution_run_id,
        docker_container_name,
        command_runner=run_command_in_container,
    )


async def run_write_file(
    idea_id: str,
    plan_id: str,
    path: str,
    content: str,
    task_id: str = "",
    execution_run_id: str = "",
    docker_container_name: str = "",
) -> str:
    return await _run_write_file_impl(
        idea_id,
        plan_id,
        path,
        content,
        task_id,
        execution_run_id,
        docker_container_name,
        command_runner=run_command_in_container,
    )


async def run_list_files(
    idea_id: str,
    plan_id: str,
    path: str,
    task_id: str = "",
    execution_run_id: str = "",
    docker_container_name: str = "",
    max_entries: int = 200,
    max_depth: int = 3,
) -> str:
    return await _run_list_files_impl(
        idea_id,
        plan_id,
        path,
        task_id,
        execution_run_id,
        docker_container_name,
        max_entries,
        max_depth,
        command_runner=run_command_in_container,
    )


async def run_run_command(
    command: str,
    task_id: str,
    *,
    docker_container_name: str = "",
    timeout_seconds: int | None = None,
) -> str:
    return await _run_run_command_impl(
        command,
        task_id,
        docker_container_name=docker_container_name,
        timeout_seconds=timeout_seconds,
        default_timeout_seconds=_RUN_SCRIPT_TIMEOUT,
        command_runner=run_command_in_container,
    )


async def run_run_skill_script(
    skill: str,
    script: str,
    args: list[str],
    idea_id: str,
    plan_id: str,
    task_id: str,
    execution_run_id: str = "",
    docker_container_name: str = "",
) -> str:
    return await _run_run_skill_script(
        skill,
        script,
        args,
        idea_id,
        plan_id,
        task_id,
        skills_root=SKILLS_ROOT,
        run_script_allowed_ext=_RUN_SCRIPT_ALLOWED_EXT,
        run_script_timeout=_RUN_SCRIPT_TIMEOUT,
        execution_run_id=execution_run_id,
        docker_container_name=docker_container_name,
    )


async def execute_tool(
    name: str,
    arguments: str,
    idea_id: str,
    plan_id: str,
    task_id: str,
    *,
    execution_run_id: str = "",
    docker_container_name: str = "",
    output_format: str = "",
) -> Tuple[Optional[Any], str]:
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
    except json.JSONDecodeError as e:
        return None, f"Error: invalid tool arguments: {e}"

    if name == "ReadArtifact":
        tid = args.get("task_id", "")
        return None, await run_read_artifact(idea_id, plan_id, tid)

    if name == "ReadFile":
        path = args.get("path", "")
        return None, await run_read_file(
            idea_id,
            plan_id,
            path,
            task_id,
            execution_run_id,
            docker_container_name,
        )

    if name == "ListFiles":
        return None, await run_list_files(
            idea_id,
            plan_id,
            args.get("path", "sandbox/"),
            task_id,
            execution_run_id,
            docker_container_name,
            args.get("max_entries", 200),
            args.get("max_depth", 3),
        )

    if name == "WriteFile":
        path = args.get("path", "")
        content = args.get("content", "")
        return None, await run_write_file(
            idea_id,
            plan_id,
            path,
            content,
            task_id,
            execution_run_id,
            docker_container_name,
        )

    if name == "RunCommand":
        return None, await run_run_command(
            args.get("command", ""),
            task_id,
            docker_container_name=docker_container_name,
            timeout_seconds=args.get("timeout_seconds"),
        )

    if name == "ListSkills":
        return None, run_list_skills()

    if name == "LoadSkill":
        return None, run_load_skill(args.get("name", ""))

    if name == "ReadSkillFile":
        return None, run_read_skill_file(args.get("skill", ""), args.get("path", ""))

    if name == "RunSkillScript":
        script_args = args.get("args") or []
        if isinstance(script_args, str):
            try:
                script_args = json.loads(script_args) if script_args else []
            except json.JSONDecodeError:
                script_args = [script_args]
        return None, await run_run_skill_script(
            args.get("skill", ""),
            args.get("script", ""),
            script_args,
            idea_id,
            plan_id,
            task_id,
            execution_run_id=execution_run_id,
            docker_container_name=docker_container_name,
        )

    if name == "Finish":
        ok, val = run_finish(args.get("output", ""), output_format=output_format)
        if ok:
            return val, ""
        return None, val

    if name == "WebSearch":
        return None, await web_tools.run_web_search(
            args.get("query", ""), args.get("max_results", 5)
        )

    if name == "WebFetch":
        return None, await web_tools.run_web_fetch(args.get("url", ""))

    return None, f"Error: unknown tool '{name}'"
