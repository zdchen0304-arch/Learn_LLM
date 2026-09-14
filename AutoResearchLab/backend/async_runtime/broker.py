"""RabbitMQ broker with durable messages, retry limits and a dead-letter exchange."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from .context import RuntimeUnavailableError
from .types import AsyncTaskEnvelope


TaskHandler = Callable[[AsyncTaskEnvelope], Awaitable[None]]


def queue_name(stage: str) -> str:
    return f"maars.research.{stage}"


class InMemoryTaskBroker:
    """Local/test broker with the same acknowledgement and retry semantics."""

    backend_name = "memory"

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[AsyncTaskEnvelope]] = {}
        self.dead_letters: list[tuple[AsyncTaskEnvelope, str]] = []

    def _queue(self, stage: str) -> asyncio.Queue[AsyncTaskEnvelope]:
        return self._queues.setdefault(stage, asyncio.Queue())

    async def publish(self, envelope: AsyncTaskEnvelope) -> None:
        await self._queue(envelope.stage).put(envelope)

    async def consume_once(self, stage: str, handler: TaskHandler) -> bool:
        queue = self._queue(stage)
        if queue.empty():
            return False
        envelope = await queue.get()
        try:
            await handler(envelope)
        except Exception as exc:
            retry = envelope.next_attempt()
            if retry.attempt < retry.max_attempts:
                await self.publish(retry)
            else:
                self.dead_letters.append((retry, str(exc)))
            return True
        return True

    async def health(self) -> dict[str, Any]:
        return {"backend": self.backend_name, "ready": True}

    async def close(self) -> None:
        return None


class RabbitMQTaskBroker:
    """A lazily-connected RabbitMQ implementation suitable for separate workers."""

    backend_name = "rabbitmq"

    def __init__(self, url: str, *, prefetch_count: int = 1) -> None:
        self._url = url
        self._prefetch_count = prefetch_count
        self._connection = None
        self._channel = None
        self._exchange = None
        self._dead_letter_exchange = None
        self._queues: dict[str, Any] = {}

    async def _ensure_topology(self) -> None:
        if self._channel is not None:
            return
        try:
            import aio_pika
        except ImportError as exc:
            raise RuntimeUnavailableError("aio-pika package is not installed; run pip install -r requirements.txt") from exc
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel(publisher_confirms=True)
        await self._channel.set_qos(prefetch_count=self._prefetch_count)
        self._exchange = await self._channel.declare_exchange("maars.research", aio_pika.ExchangeType.DIRECT, durable=True)
        self._dead_letter_exchange = await self._channel.declare_exchange(
            "maars.research.dlx", aio_pika.ExchangeType.DIRECT, durable=True
        )
        await self._channel.declare_queue("maars.research.dead-letter", durable=True)
        dead = await self._channel.get_queue("maars.research.dead-letter")
        await dead.bind(self._dead_letter_exchange, routing_key="dead-letter")

    async def _queue(self, stage: str):
        await self._ensure_topology()
        if stage not in self._queues:
            import aio_pika

            queue = await self._channel.declare_queue(
                queue_name(stage),
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "maars.research.dlx",
                    "x-dead-letter-routing-key": "dead-letter",
                },
            )
            await queue.bind(self._exchange, routing_key=stage)
            self._queues[stage] = queue
        return self._queues[stage]

    async def publish(self, envelope: AsyncTaskEnvelope) -> None:
        await self._queue(envelope.stage)
        import aio_pika

        body = json.dumps(envelope.to_dict(), ensure_ascii=False).encode("utf-8")
        if len(body) > 64 * 1024:
            raise ValueError("Async envelope is too large; store context as an artifact and pass a reference")
        message = aio_pika.Message(
            body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=envelope.task_id,
            correlation_id=envelope.trace_id,
            type=envelope.event_type,
        )
        await self._exchange.publish(message, routing_key=envelope.stage, mandatory=True)

    async def consume_once(self, stage: str, handler: TaskHandler) -> bool:
        queue = await self._queue(stage)
        message = await queue.get(fail=False)
        if message is None:
            return False
        async with message.process(requeue=False):
            envelope = AsyncTaskEnvelope.from_dict(json.loads(message.body.decode("utf-8")))
            try:
                await handler(envelope)
            except Exception as exc:
                retry = envelope.next_attempt()
                if retry.attempt < retry.max_attempts:
                    await self.publish(retry)
                else:
                    import aio_pika

                    dead = aio_pika.Message(
                        message.body,
                        content_type="application/json",
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        headers={"x-maars-error": str(exc)[:512]},
                    )
                    await self._dead_letter_exchange.publish(dead, routing_key="dead-letter")
        return True

    async def health(self) -> dict[str, Any]:
        try:
            await self._ensure_topology()
            return {"backend": self.backend_name, "ready": True}
        except Exception as exc:
            return {"backend": self.backend_name, "ready": False, "error": str(exc)}

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
        self._connection = self._channel = self._exchange = self._dead_letter_exchange = None
        self._queues.clear()
