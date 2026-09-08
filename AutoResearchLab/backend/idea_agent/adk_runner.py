"""
Idea Agent - Google ADK 驱动实现。
当 ideaAgentMode=True 时使用，替代自实现 ReAct 循环。
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

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
from shared.constants import IDEA_AGENT_MAX_TURNS

from .agent_tools import execute_idea_agent_tool, get_idea_agent_tools

IDEA_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = IDEA_DIR / "prompts"
_prompt_cache: Dict[str, str] = {}


def _get_prompt_cached(filename: str) -> str:
    """加载 idea agent prompt 文件。"""
    if filename not in _prompt_cache:
        path = PROMPTS_DIR / filename
        _prompt_cache[filename] = path.read_text(encoding="utf-8").strip()
    return _prompt_cache[filename]


async def run_idea_agent_adk(
    idea: str,
    api_config: dict,
    limit: int = 10,
    on_thinking: Optional[Callable[..., Any]] = None,
    abort_event: Optional[Any] = None,
) -> dict:
    """
    使用 Google ADK Runner 运行 Idea Agent。
    返回 {keywords, papers, refined_idea}，与 collect_literature 一致。
    """
    prepare_api_env(api_config)

    idea_state: Dict[str, Any] = {
        "idea": idea,
        "keywords": [],
        "papers": [],
        "filtered_papers": [],
        "analysis": "",
        "refined_idea": "",
        "rag_context": "",
    }

    on_thinking_fn = on_thinking or (lambda *a, **_: None)

    async def executor_fn(name: str, args: dict) -> tuple[bool, str]:
        args_str = json.dumps(args, ensure_ascii=False)
        return await execute_idea_agent_tool(
            name,
            args_str,
            idea_state,
            on_thinking=on_thinking_fn,
            abort_event=abort_event,
            api_config=api_config,
            limit=limit,
        )

    tools = create_executor_tools(get_idea_agent_tools(api_config), executor_fn)
    system_prompt = _get_prompt_cached("idea-agent-prompt.txt")
    user_message = f"**User's fuzzy idea:** {idea}\n\nProcess the idea using the workflow. Call FinishIdea when done."

    model = get_model_for_adk(api_config)
    finish_result: Optional[dict] = None

    def _on_tool_call(name: str, args: dict, turn_count: int):
        return on_thinking_fn(
            "",
            task_id=None,
            operation="Refine",
            schedule_info={
                "turn": turn_count,
                "max_turns": IDEA_AGENT_MAX_TURNS,
                "tool_name": name,
                "tool_args": build_tool_args_preview(args),
                "tool_args_preview": None,
                "operation": "Refine",
            },
        )

    def _on_tool_response(name: str, response: Any, _turn_count: int):
        nonlocal finish_result
        if name == "FinishIdea" and response:
            finish_result = parse_function_response_payload(response)

    def _on_text(text: str, turn_count: int):
        return on_thinking_fn(
            text,
            task_id=None,
            operation="Refine",
            schedule_info={
                "turn": turn_count,
                "max_turns": IDEA_AGENT_MAX_TURNS,
                "operation": "Refine",
            },
        )

    await run_adk_agent_loop(
        app_name="maars_idea",
        agent_name="idea_agent",
        model=model,
        instruction=system_prompt,
        tools=tools,
        user_message=user_message,
        max_turns=IDEA_AGENT_MAX_TURNS,
        abort_event=abort_event,
        abort_message="Idea Agent aborted",
        on_tool_call=_on_tool_call,
        on_tool_response=_on_tool_response,
        on_text=_on_text,
    )

    if finish_result:
        return {
            "keywords": finish_result.get("keywords", []),
            "papers": finish_result.get("papers", []),
            "refined_idea": finish_result.get("refined_idea", ""),
        }

    return {
        "keywords": idea_state.get("keywords", []),
        "papers": idea_state.get("papers", []),
        "refined_idea": idea_state.get("refined_idea", ""),
    }
