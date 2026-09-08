"""
Idea Agent - Google ADK 驱动 (ideaAgentMode=True)。
替代自实现 ReAct 循环，使用 backend/idea_agent/adk_runner.py。
"""

from typing import Any, Callable, Optional

from . import adk_runner


async def run_idea_agent(
    idea: str,
    api_config: dict,
    limit: int = 10,
    on_thinking: Optional[Callable[..., Any]] = None,
    abort_event: Optional[Any] = None,
) -> dict:
    """
    Idea Agent 入口。使用 Google ADK 驱动。
    返回 {keywords, papers, refined_idea}，与 collect_literature 一致。
    """
    return await adk_runner.run_idea_agent_adk(
        idea=idea,
        api_config=api_config,
        limit=limit,
        on_thinking=on_thinking,
        abort_event=abort_event,
    )
