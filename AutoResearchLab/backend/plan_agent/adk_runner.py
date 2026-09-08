"""
Plan Agent - Google ADK 驱动实现。
当 planAgentMode=True 时使用，替代自实现 ReAct 循环。
"""

import json
from typing import Any, Callable, Dict, List, Optional

from shared.adk_bridge import (
    create_executor_tools,
    get_model_for_adk,
    prepare_api_env,
)
from shared.adk_runtime import (
    build_tool_args_preview,
    parse_function_response_payload,
    run_adk_agent_loop,
)
from shared.constants import PLAN_AGENT_MAX_TURNS

from .agent_tools import PLAN_AGENT_TOOLS, execute_plan_agent_tool
from .llm.executor import check_atomicity, decompose_task, format_task
from .llm.executor_helpers import _get_prompt_cached


async def run_plan_agent_adk(
    plan: Dict,
    on_thinking: Callable[[str], None],
    abort_event: Optional[Any],
    on_tasks_batch: Optional[Callable[[List[Dict], Dict, List[Dict]], None]],
    api_config: Optional[Dict],
    idea_id: Optional[str] = None,
    plan_id: Optional[str] = None,
) -> Dict:
    """
    使用 Google ADK Runner 运行 Plan Agent。
    返回 {tasks}。
    """
    prepare_api_env(api_config or {})

    tasks = plan.get("tasks") or []
    root_task = next((t for t in tasks if t.get("task_id") == "0"), None)
    if not root_task:
        root_task = next(
            (t for t in tasks if t.get("task_id") and not (t.get("dependencies") or [])),
            tasks[0] if tasks else None,
        )
    if not root_task:
        raise ValueError("No decomposable task found. Generate plan first.")

    all_tasks = list(tasks)
    idea = plan.get("idea") or root_task.get("description") or ""
    plan_state: Dict[str, Any] = {
        "all_tasks": all_tasks,
        "pending_queue": ["0"],
        "idea": idea,
    }

    on_thinking_fn = on_thinking or (lambda *a, **_: None)

    async def executor_fn(name: str, args: dict) -> tuple[bool, str]:
        args_str = json.dumps(args, ensure_ascii=False)
        return await execute_plan_agent_tool(
            name,
            args_str,
            plan_state,
            check_atomicity_fn=check_atomicity,
            decompose_fn=decompose_task,
            format_fn=format_task,
            on_thinking=on_thinking_fn,
            on_tasks_batch=on_tasks_batch,
            abort_event=abort_event,
            use_mock=False,
            api_config=api_config,
            idea_id=idea_id,
            plan_id=plan_id,
        )

    tools = create_executor_tools(PLAN_AGENT_TOOLS, executor_fn)
    system_prompt = _get_prompt_cached("plan-agent-prompt.txt")
    user_message = f"**Idea:** {idea}\n\n**Root task:** task_id \"0\", description \"{root_task.get('description', '')}\"\n\nProcess all tasks until GetNextTask returns null, then call FinishPlan."

    model = get_model_for_adk(api_config or {})

    finish_result: Optional[dict] = None

    def _on_tool_call(name: str, args: dict, turn_count: int):
        return on_thinking_fn(
            "",
            task_id=None,
            operation="Decompose",
            schedule_info={
                "turn": turn_count,
                "max_turns": PLAN_AGENT_MAX_TURNS,
                "tool_name": name,
                "tool_args": build_tool_args_preview(args),
                "tool_args_preview": None,
                "operation": "Decompose",
            },
        )

    def _on_tool_response(name: str, response: Any, _turn_count: int):
        nonlocal finish_result
        if name == "FinishPlan" and response:
            finish_result = parse_function_response_payload(response)

    def _on_text(text: str, turn_count: int):
        return on_thinking_fn(
            text,
            task_id=None,
            operation="Decompose",
            schedule_info={
                "turn": turn_count,
                "max_turns": PLAN_AGENT_MAX_TURNS,
                "operation": "Decompose",
            },
        )

    turn_count = await run_adk_agent_loop(
        app_name="maars_plan",
        agent_name="plan_agent",
        model=model,
        instruction=system_prompt,
        tools=tools,
        user_message=user_message,
        max_turns=PLAN_AGENT_MAX_TURNS,
        abort_event=abort_event,
        abort_message="Plan Agent aborted",
        on_tool_call=_on_tool_call,
        on_tool_response=_on_tool_response,
        on_text=_on_text,
    )

    plan["tasks"] = plan_state["all_tasks"]
    return {
        "tasks": plan_state["all_tasks"],
        "pending_queue": list(plan_state.get("pending_queue") or []),
        "finished": bool(finish_result) and not (plan_state.get("pending_queue") or []),
        "turn_count": int(turn_count or 0),
    }
