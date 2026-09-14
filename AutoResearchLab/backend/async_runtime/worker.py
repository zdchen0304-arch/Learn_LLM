"""Generic worker entry point for a stage adapter deployed outside the FastAPI process.

Set MAARS_ASYNC_HANDLER to ``module:function``.  The function must be async and
accept ``(AsyncTaskEnvelope, context_dict)``.  Keeping this adapter explicit
prevents a queue consumer from accidentally running with browser session state.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import os

from .runtime import AsyncResearchRuntime


def _load_handler(path: str):
    module_name, separator, attr = path.partition(":")
    if not separator or not module_name or not attr:
        raise ValueError("MAARS_ASYNC_HANDLER must be module:function")
    handler = getattr(importlib.import_module(module_name), attr)
    if not inspect.iscoroutinefunction(handler):
        raise ValueError("MAARS_ASYNC_HANDLER must reference an async function")
    return handler


async def serve(stage: str, handler_path: str, poll_seconds: float = 0.5) -> None:
    runtime = AsyncResearchRuntime.from_env()
    handler = _load_handler(handler_path)
    try:
        while True:
            consumed = await runtime.consume_once(stage, handler)
            if not consumed:
                await asyncio.sleep(poll_seconds)
    finally:
        await runtime.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="MAARS asynchronous research worker")
    parser.add_argument("--stage", required=True, choices=("refine", "plan", "execute", "paper", "review"))
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    args = parser.parse_args()
    handler_path = os.getenv("MAARS_ASYNC_HANDLER", "")
    if not handler_path:
        raise SystemExit("MAARS_ASYNC_HANDLER is required, e.g. worker_adapters:execute")
    asyncio.run(serve(args.stage, handler_path, args.poll_seconds))


if __name__ == "__main__":
    main()
