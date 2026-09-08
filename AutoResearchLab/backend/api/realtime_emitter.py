"""Realtime emitter that mirrors Socket.IO events into SSE subscribers."""

from typing import Any, Awaitable, Callable, Optional


class RealtimeEmitter:
    """Proxy emitter that mirrors Socket.IO emits into SSE subscribers."""

    def __init__(
        self,
        raw_sio: Any,
        publish_sse: Callable[[str, str, dict], Awaitable[None]],
    ):
        self._raw = raw_sio
        self._publish_sse = publish_sse

    async def emit(self, event: str, payload: dict, to: Optional[str] = None, **kwargs):
        if to:
            await self._publish_sse(to, event, payload)
        if self._raw and hasattr(self._raw, "emit"):
            return await self._raw.emit(event, payload, to=to, **kwargs)
        return None
