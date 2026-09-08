"""Shared helpers for per-agent run state lifecycle."""

from typing import Any, Awaitable, Callable


def clear_run_state(state: Any) -> None:
    """Clear run task + abort event for idea/plan/paper states."""

    if not state:
        return
    state.run_task = None
    state.abort_event = None


async def stop_run_state(
    session_id: str,
    state: Any,
    *,
    emit_safe: Callable[..., Awaitable[None]],
    error_event: str,
    error_message: str,
    emit_when_idle: bool = False,
) -> bool:
    """Stop one agent run state and optionally emit stop error event."""

    if not state:
        return False
    if state.abort_event:
        state.abort_event.set()

    is_running = bool(state.run_task and not state.run_task.done())
    if is_running:
        state.run_task.cancel()

    if is_running or emit_when_idle:
        await emit_safe(
            session_id,
            error_event,
            {"error": error_message},
            warning_label=f"{error_event} emit (stop)",
        )
    return is_running
