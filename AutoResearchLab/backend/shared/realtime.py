"""Realtime/WebSocket event helper utilities."""

from typing import Any, Optional

from loguru import logger


def build_thinking_emitter(
    sio: Any,
    *,
    event_name: str,
    source: str,
    default_operation: str,
    room: Optional[str] = None,
    warning_label: Optional[str] = None,
):
    """
    Build a unified thinking emitter callback:
    signature: (chunk, task_id=None, operation=None, schedule_info=None)
    """
    warn = warning_label or event_name

    async def on_thinking(
        chunk: str,
        task_id=None,
        operation=None,
        schedule_info=None,
    ):
        if not chunk and schedule_info is None:
            return
        if not sio:
            return
        payload = {
            "chunk": chunk or "",
            "source": source,
            "taskId": task_id,
            "operation": operation or default_operation,
        }
        if schedule_info is not None:
            payload["scheduleInfo"] = schedule_info
        try:
            await sio.emit(event_name, payload, to=room)
        except Exception as e:
            logger.warning("%s emit failed: %s", warn, e)

    return on_thinking
