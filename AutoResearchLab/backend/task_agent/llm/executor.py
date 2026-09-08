"""
Task Agent 单轮 LLM 实现 - 任务执行。
与 Plan/Idea 对齐：Mock 模式依赖 test/mock-ai/execute.json，使用 mock_chat_completion 流式输出。
"""

import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import orjson
import json_repair

from shared.constants import MAX_FORMAT_REPAIR_ATTEMPTS, TEMP_RETRY, TEMP_TASK_EXECUTE
from shared.llm_client import chat_completion, merge_phase_config
from shared.mock_utils import get_mock_cached
from shared.structured_output import generate_with_repair
from shared.utils import extract_codeblock
from test.mock_stream import mock_chat_completion

TASK_DIR = Path(__file__).resolve().parent.parent
MOCK_AI_DIR = TASK_DIR.parent / "test" / "mock-ai"
RESPONSE_TYPE = "execute"


def _load_mock_response(response_type: str, task_id: str, use_json_mode: bool) -> Optional[Dict]:
    """从 test/mock-ai/ 加载 mock，与 Plan/Idea 对齐。

    Precedence: task_id → _default_markdown (non-JSON only) → _default.
    """
    data = get_mock_cached(MOCK_AI_DIR, response_type)
    entry = data.get(task_id) or (data.get("_default_markdown") if not use_json_mode else None) or data.get("_default")
    if not entry:
        return None
    content = entry.get("content")
    content_str = content if isinstance(content, str) else orjson.dumps(content).decode("utf-8")
    return {"content": content_str, "reasoning": entry.get("reasoning", "")}


async def _run_mock_execute(task_id: str, output_format: str, on_thinking: Optional[Callable] = None) -> Any:
    """Mock 执行：从 execute.json 加载，使用 mock_chat_completion 流式输出。供 executor 与 agent 共用。"""
    mode = _get_output_mode(output_format)
    mock = _load_mock_response(RESPONSE_TYPE, task_id, mode == "json")
    if not mock:
        raise ValueError(f"No mock data for {RESPONSE_TYPE}/{task_id}")
    stream = on_thinking is not None

    def stream_chunk(chunk: str):
        if on_thinking and chunk:
            return on_thinking(chunk, task_id=task_id, operation="Execute")

    effective_on_thinking = stream_chunk if stream else None
    content = await mock_chat_completion(
        mock["content"],
        mock["reasoning"],
        effective_on_thinking,
        stream=stream,
    )
    return _parse_task_agent_output(content or "", output_format)


def _is_json_format(output_format: str) -> bool:
    if not output_format:
        return False
    fmt = output_format.strip().upper()
    return fmt.startswith("JSON") or "JSON" in fmt


def _is_markdown_format(output_format: str) -> bool:
    fmt = (output_format or "").strip().lower()
    return "markdown" in fmt or fmt in {"md", "text", "plain text", "plain-text"}


def _requires_structured_payload(output_format: str) -> bool:
    fmt = (output_format or "").strip().lower()
    structured_tokens = (
        "array",
        "object",
        "dict",
        "dictionary",
        "table",
        "csv",
        "list",
        "matrix",
        "tensor",
        "time-series",
        "timeseries",
        "time series",
    )
    return any(token in fmt for token in structured_tokens)


def _get_output_mode(output_format: str) -> str:
    if _is_json_format(output_format):
        return "json"
    if _is_markdown_format(output_format):
        return "markdown"
    if _requires_structured_payload(output_format):
        return "structured"
    return "markdown"


def _build_task_agent_messages(
    task_id: str,
    description: str,
    input_spec: Dict[str, Any],
    output_spec: Dict[str, Any],
    resolved_inputs: Dict[str, Any],
    idea_context: str = "",
) -> tuple[list[dict], str]:
    """Build system + user messages for single-turn Task Agent."""
    output_format = output_spec.get("format") or ""
    output_desc = output_spec.get("description") or ""
    input_desc = input_spec.get("description") or ""

    system_prompt = """You are a Task Agent. Your job is to complete a single atomic task and produce output in the exact format specified.

Rules:
1. Use only the provided input artifacts and task description.
2. Output must strictly conform to the specified format.
3. You may reason first (1-3 sentences); this will be shown as your thinking process.
4. For JSON: output reasoning first, then the JSON in a ```json``` code block.
5. For Markdown: output reasoning first, then a blank line, then the document content."""

    if _requires_structured_payload(output_format) and not _is_json_format(output_format):
        system_prompt += "\n6. For array/object/table/time-series outputs, return a structured JSON payload that points to the generated artifact and includes key metadata; do not return a prose-only summary."

    inputs_str = "No input artifacts."
    if resolved_inputs:
        try:
            inputs_str = orjson.dumps(resolved_inputs, option=orjson.OPT_INDENT_2).decode("utf-8")
        except (TypeError, ValueError):
            inputs_str = str(resolved_inputs)

    idea_section = ""
    if idea_context:
        idea_section = f"\n**Research idea (project context):** {idea_context}\n"

    user_prompt = f"""**Task ID:** {task_id}
**Description:** {description}
{idea_section}
**Input description:** {input_desc}
**Input artifacts:**
```json
{inputs_str}
```

**Output description:** {output_desc}
**Output format:** {output_format}

Produce the output now. You may reason first; then output the result."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return messages, output_format


def _parse_task_agent_output(content: str, output_format: str) -> Any:
    """Parse Task Agent output (content) to final result. 支持 reasoning + 结果的格式。"""
    content = (content or "").strip()
    if not content:
        raise ValueError("LLM returned empty response")
    mode = _get_output_mode(output_format)
    if mode in ("json", "structured"):
        cleaned = extract_codeblock(content) or content
        # 若无 ```json``` 块，尝试从文本中提取 {...} 或整体解析
        if not cleaned or not cleaned.strip().startswith("{"):
            obj_match = re.search(r"\{[\s\S]*\}", content)
            if obj_match:
                cleaned = obj_match.group(0)
        try:
            parsed = json_repair.loads(cleaned)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON from LLM response: {e}") from e
        if mode == "structured":
            if isinstance(parsed, str):
                raise ValueError("Structured output must be JSON object/array, not a prose string")
            if isinstance(parsed, dict) and set(parsed.keys()) == {"content"} and isinstance(parsed.get("content"), str):
                raise ValueError("Structured output must not be a prose-only content wrapper")
        return parsed
    # Markdown: 若前面有 reasoning（短于 300 字），取第一个 \n\n 之后的内容作为文档
    if "\n\n" in content and len(content.split("\n\n", 1)[0]) < 300:
        return content.split("\n\n", 1)[1].strip()
    return content




async def execute_task(
    task_id: str,
    description: str,
    input_spec: Dict[str, Any],
    output_spec: Dict[str, Any],
    resolved_inputs: Dict[str, Any],
    api_config: Optional[Dict[str, Any]] = None,
    abort_event: Optional[Any] = None,
    on_thinking: Optional[Callable[[str, Optional[str], Optional[str]], None]] = None,
    idea_id: Optional[str] = None,
    plan_id: Optional[str] = None,
    idea_context: str = "",
) -> Any:
    """
    Execute task via single-turn LLM. Returns parsed output (dict for JSON, str for Markdown).
    When taskUseMock=True in api_config, returns simulated output without LLM call.
    When taskAgentMode=True, caller (runner) should use task_agent.agent.run_task_agent instead.
    """
    raw_cfg = api_config or {}
    if raw_cfg.get("taskUseMock"):
        output_format = (output_spec or {}).get("format") or ""
        return await _run_mock_execute(task_id, output_format, on_thinking)

    cfg = merge_phase_config(raw_cfg, "execute")
    messages, output_format = _build_task_agent_messages(
        task_id, description, input_spec, output_spec, resolved_inputs, idea_context
    )
    output_mode = _get_output_mode(output_format)
    # 不使用 response_format，以便 LLM 先输出 reasoning 再输出结果（Thinking 显示推理）
    response_format = None
    stream = on_thinking is not None

    def _on_chunk(chunk: str):
        if on_thinking and chunk:
            return on_thinking(chunk, task_id=task_id, operation="Execute")

    async def _model_call(message_list: list[dict], temperature: float) -> str:
        raw = await chat_completion(
            message_list,
            cfg,
            on_chunk=_on_chunk if stream else None,
            abort_event=abort_event,
            stream=stream,
            temperature=temperature,
            response_format=response_format,
        )
        return raw if isinstance(raw, str) else (raw.get("content") or "")

    if output_mode in ("json", "structured"):
        temperatures = [TEMP_TASK_EXECUTE] + [TEMP_RETRY] * max(0, MAX_FORMAT_REPAIR_ATTEMPTS - 1)
        parsed, _raw = await generate_with_repair(
            base_messages=messages,
            model_call=_model_call,
            parse_fn=lambda text: _parse_task_agent_output(text, output_format),
            temperatures=temperatures,
        )
        return parsed

    content = await _model_call(messages, TEMP_TASK_EXECUTE)
    return _parse_task_agent_output(content, output_format)
