"""
Plan Agent - Google ADK 驱动 (planAgentMode=True)。
替代自实现 ReAct 循环，使用 backend/plan_agent/adk_runner.py。
"""

from typing import Any, Callable, Dict, List, Optional

from . import adk_runner


async def run_plan_agent(
    plan: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    on_tasks_batch: Optional[Callable[[List[Dict], Dict, List[Dict]], None]],
    api_config: Optional[Dict],
    idea_id: Optional[str] = None,
    plan_id: Optional[str] = None,
) -> Dict:
    """
    Plan Agent 入口。使用 Google ADK 驱动。
    返回 {tasks}。
    """
    return await adk_runner.run_plan_agent_adk(
        plan=plan,
        on_thinking=on_thinking,
        abort_event=abort_event,
        on_tasks_batch=on_tasks_batch,
        api_config=api_config,
        idea_id=idea_id,
        plan_id=plan_id,
    )
