"""Skill-related tool execution helpers for Task Agent tools."""

import asyncio
from pathlib import Path
from typing import List, Optional, Tuple

from shared.skill_utils import (
    list_skills as _list_skills,
    load_skill as _load_skill,
    read_skill_file as _read_skill_file,
)

from .docker_runtime import run_skill_script_in_container
from .agent_tool_io import get_task_root_dir


def run_list_skills(skills_root: Path) -> str:
    """Execute ListSkills."""
    return _list_skills(skills_root)


def run_load_skill(skills_root: Path, name: str) -> str:
    """Execute LoadSkill."""
    return _load_skill(skills_root, name)


def _get_skill_dir(skills_root: Path, skill_name: str) -> Tuple[Optional[Path], str]:
    """Return (skill_dir, error_msg). error_msg non-empty on failure."""
    if not skill_name or not isinstance(skill_name, str):
        return None, "Error: skill name must be a non-empty string"
    if ".." in skill_name or "/" in skill_name or "\\" in skill_name:
        return None, "Error: invalid skill name"
    skill_dir = (skills_root / skill_name.strip()).resolve()
    try:
        skill_dir.relative_to(skills_root.resolve())
    except ValueError:
        return None, "Error: invalid skill name"
    if not skill_dir.exists() or not skill_dir.is_dir():
        return None, f"Error: Skill '{skill_name}' not found"
    return skill_dir, ""


def run_read_skill_file(skills_root: Path, skill: str, path: str) -> str:
    """Execute ReadSkillFile."""
    return _read_skill_file(skills_root, skill, path)


async def run_run_skill_script(
    skill: str,
    script: str,
    args: List[str],
    idea_id: str,
    plan_id: str,
    task_id: str,
    *,
    skills_root: Path,
    run_script_allowed_ext: tuple[str, ...],
    run_script_timeout: int,
    execution_run_id: str = "",
    docker_container_name: str = "",
) -> str:
    """Execute RunSkillScript for either local or docker execution modes."""
    try:
        skill_dir, err = _get_skill_dir(skills_root, skill)
        if err:
            return err
        script = script.replace("\\", "/").strip()
        if ".." in script or script.startswith("/"):
            return "Error: script path traversal not allowed"
        script_path = (skill_dir / script).resolve()
        try:
            script_path.relative_to(skill_dir)
        except ValueError:
            return "Error: script path traversal not allowed"
        if not script_path.exists() or not script_path.is_file():
            return f"Error: Script not found: {script}"
        ext = script_path.suffix.lower()
        if ext not in run_script_allowed_ext:
            return f"Error: Script extension .{ext} not allowed (use .py, .sh, .js)"

        if execution_run_id and docker_container_name:
            result = await run_skill_script_in_container(
                container_name=docker_container_name,
                task_id=task_id,
                skill=skill,
                script_rel_path=script,
                args=[str(a) for a in (args or [])],
                timeout_seconds=run_script_timeout,
            )
            out = result.get("stdout", "")
            err_out = result.get("stderr", "")
            if result.get("code") != 0:
                return f"Exit code {result.get('code')}\nstdout:\n{out}\nstderr:\n{err_out}"
            return out + (f"\n{err_out}" if err_out else "")

        sandbox_dir = get_task_root_dir(idea_id, plan_id, task_id, execution_run_id)
        sandbox_str = str(sandbox_dir.resolve())
        resolved_args = [
            (
                a.replace("[[sandbox]]", sandbox_str).replace("{{sandbox}}", sandbox_str)
                if isinstance(a, str)
                else str(a)
            )
            for a in (args or [])
        ]

        if ext == ".py":
            cmd = ["python", str(script_path)] + resolved_args
        elif ext == ".sh":
            cmd = ["sh", str(script_path)] + resolved_args
        elif ext == ".js":
            cmd = ["node", str(script_path)] + resolved_args
        else:
            return f"Error: unsupported script type: {ext}"

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(skill_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=run_script_timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return f"Error: Script timed out after {run_script_timeout}s"

        out = stdout.decode("utf-8", errors="replace")
        err_out = stderr.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            return f"Exit code {proc.returncode}\nstdout:\n{out}\nstderr:\n{err_out}"
        return out + (f"\n{err_out}" if err_out else "")
    except Exception as e:
        return f"Error running script: {e}"
