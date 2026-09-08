"""Shell command tool execution helper for Task Agent tools."""

from .docker_runtime import run_command_in_container


async def run_run_command(
    command: str,
    task_id: str,
    *,
    docker_container_name: str = "",
    timeout_seconds: int | None = None,
    default_timeout_seconds: int = 120,
    command_runner=run_command_in_container,
) -> str:
    del task_id
    try:
        cmd = (command or "").strip()
        if not cmd:
            return "Error: command must be a non-empty string"
        if not docker_container_name:
            return "Error: Docker execution container is not connected for this task"
        result = await command_runner(
            container_name=docker_container_name,
            command=cmd,
            workdir="/workdir/src",
            timeout_seconds=timeout_seconds or default_timeout_seconds,
        )
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        if result.get("code") != 0:
            return f"Exit code {result.get('code')}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        body = stdout.strip()
        if stderr.strip():
            body = (body + "\n" if body else "") + stderr.strip()
        return body or "OK"
    except Exception as e:
        return f"Error running command: {e}"
