"""
LLM client for Plan Agent and Task Agent. Uses Google GenAI SDK (Gemini API only).
"""

import asyncio
import json
from typing import Any, Callable, List, Optional, Union

from google import genai
from google.genai import types
from openai import AsyncOpenAI

from loguru import logger

from shared.constants import DEFAULT_MODEL, LLM_REQUEST_TIMEOUT, LLM_STREAM_CHUNK_TIMEOUT

DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"
DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"


def merge_phase_config(api_config: dict, phase: str) -> dict:
    """从 api_config 提取 LLM 连接参数。phase 参数保留用于未来扩展，当前不做区分。"""
    cfg = dict(api_config or {})
    return {
        "provider": cfg.get("provider") or cfg.get("llmProvider") or "gemini",
        "baseUrl": cfg.get("baseUrl") or cfg.get("base_url"),
        "apiKey": cfg.get("apiKey") or cfg.get("api_key"),
        "model": cfg.get("model"),
    }


def _provider_for(cfg: dict) -> str:
    """Return a supported provider identifier, with a clear failure otherwise."""
    provider = str(cfg.get("provider") or cfg.get("llmProvider") or "gemini").strip().lower()
    if provider in {"gemini", "google"}:
        return "gemini"
    if provider == "deepseek":
        return "deepseek"
    raise RuntimeError(f"Unsupported LLM provider: {provider}. Use gemini or deepseek.")


def _model_for(cfg: dict, provider: str) -> str:
    """Choose a provider-appropriate default model only when none is configured."""
    configured_model = str(cfg.get("model") or "").strip()
    if configured_model:
        return configured_model
    return DEEPSEEK_DEFAULT_MODEL if provider == "deepseek" else DEFAULT_MODEL


async def _deepseek_chat_completion(
    messages: list[dict],
    cfg: dict,
    on_chunk: Optional[Callable[[str], None]],
    abort_event: Optional[Any],
    stream: bool,
    temperature: Optional[float],
    response_format: Optional[dict],
    tools: Optional[List[dict]],
) -> Union[str, dict]:
    """Call DeepSeek's OpenAI-compatible chat-completions endpoint."""
    api_key = str(cfg.get("apiKey") or cfg.get("api_key") or "").strip()
    if not api_key:
        raise RuntimeError("DeepSeek API key is missing. Set MAARS_API_KEY in .env.")

    base_url = str(cfg.get("baseUrl") or cfg.get("base_url") or DEEPSEEK_DEFAULT_BASE_URL).strip()
    request: dict = {"model": _model_for(cfg, "deepseek"), "messages": messages}
    if temperature is not None:
        request["temperature"] = temperature
    if response_format and response_format.get("type") == "json_object":
        request["response_format"] = {"type": "json_object"}
    if tools:
        request["tools"] = tools
        stream = False

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    try:
        if abort_event and abort_event.is_set():
            raise asyncio.CancelledError("Aborted")
        if stream:
            stream_response = await asyncio.wait_for(
                client.chat.completions.create(**request, stream=True),
                timeout=LLM_REQUEST_TIMEOUT,
            )
            full_content: list[str] = []
            async for chunk in stream_response:
                if abort_event and abort_event.is_set():
                    raise asyncio.CancelledError("Aborted")
                text = (chunk.choices[0].delta.content or "") if chunk.choices else ""
                if text:
                    if on_chunk:
                        result = on_chunk(text)
                        if asyncio.iscoroutine(result):
                            await result
                    full_content.append(text)
            return "".join(full_content)

        response = await asyncio.wait_for(
            client.chat.completions.create(**request, stream=False),
            timeout=LLM_REQUEST_TIMEOUT,
        )
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise RuntimeError(f"DeepSeek request timed out after {LLM_REQUEST_TIMEOUT}s")
    except asyncio.TimeoutError:
        raise RuntimeError(f"DeepSeek request timed out after {LLM_REQUEST_TIMEOUT}s")
    except Exception as e:
        raise RuntimeError(f"DeepSeek API error: {e}") from e
    finally:
        await client.close()

    if abort_event and abort_event.is_set():
        raise asyncio.CancelledError("Aborted")
    if not response.choices:
        return ""

    choice = response.choices[0]
    message = choice.message
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        return {
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": call.type or "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in tool_calls
            ],
            "finish_reason": choice.finish_reason or "tool_calls",
        }
    return message.content or ""


def _tools_to_gemini(tools: List[dict]) -> List[Any]:
    """Convert OpenAI-style tools format to google-genai types.Tool."""
    declarations = []
    for t in tools or []:
        fn = t.get("function") if isinstance(t, dict) else getattr(t, "function", None)
        if not fn:
            continue
        fn = fn if isinstance(fn, dict) else {}
        name = fn.get("name") or ""
        desc = fn.get("description") or ""
        params = fn.get("parameters") or {"type": "object", "properties": {}}
        declarations.append(
            types.FunctionDeclaration(
                name=name,
                description=desc,
                parameters_json_schema=params,
            )
        )
    if not declarations:
        return []
    return [types.Tool(function_declarations=declarations)]


def _messages_to_gemini_contents(messages: list[dict]) -> tuple[List[Any], Optional[str]]:
    """
    Convert messages to Google contents. Returns (contents, system_instruction).
    Supports gemini_model_content in assistant messages for native thought_signature.
    """
    contents: List[Any] = []
    system_instruction: Optional[str] = None
    id_to_name: dict = {}

    for m in messages:
        role = (m.get("role") or "").lower()

        if role == "system":
            system_instruction = m.get("content") or ""
            continue

        if role == "user":
            text = m.get("content") or ""
            if text:
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=text)]))
            continue

        if role == "assistant":
            raw = m.get("gemini_model_content")
            if raw is not None:
                contents.append(raw)
                continue
            text = m.get("content") or ""
            tool_calls = m.get("tool_calls") or []
            for tc in tool_calls:
                fn = tc.get("function") or {}
                tid = tc.get("id") or ""
                if tid:
                    id_to_name[tid] = fn.get("name") or ""
            if tool_calls:
                parts = []
                if text:
                    parts.append(types.Part.from_text(text=text))
                for tc in tool_calls:
                    fn = tc.get("function") or {}
                    name = fn.get("name") or ""
                    args = fn.get("arguments") or "{}"
                    try:
                        args_dict = json.loads(args) if isinstance(args, str) else (args or {})
                    except json.JSONDecodeError:
                        args_dict = {}
                    part = types.Part.from_function_call(name=name, args=args_dict)
                    try:
                        if tc.get("thought_signature") is not None:
                            part.thought_signature = tc["thought_signature"]
                    except Exception:
                        pass
                    parts.append(part)
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
            elif text:
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=text)]))
            continue

        if role == "tool":
            tool_call_id = m.get("tool_call_id") or ""
            content = m.get("content") or ""
            name = id_to_name.get(tool_call_id) or "tool"
            contents.append(
                types.Content(
                    role="tool",
                    parts=[types.Part.from_function_response(name=name, response={"result": content})],
                )
            )
            continue

    return contents, system_instruction


async def chat_completion(
    messages: list[dict],
    api_config: dict,
    on_chunk: Optional[Callable[[str], None]] = None,
    abort_event: Optional[Any] = None,
    stream: bool = True,
    temperature: Optional[float] = None,
    response_format: Optional[dict] = None,
    tools: Optional[List[dict]] = None,
) -> Union[str, dict]:
    """
    Call the configured provider's chat-completions API.
    When tools provided: returns dict with content, tool_calls, finish_reason, gemini_model_content.
    """
    cfg = dict(api_config or {})
    provider = _provider_for(cfg)
    if provider == "deepseek":
        return await _deepseek_chat_completion(
            messages, cfg, on_chunk, abort_event, stream, temperature, response_format, tools
        )

    model = _model_for(cfg, provider)
    temp = temperature if temperature is not None else cfg.get("temperature")
    api_key = cfg.get("apiKey") or cfg.get("api_key") or ""

    client = genai.Client(api_key=api_key)
    contents, system_instruction = _messages_to_gemini_contents(messages)

    config_kw: dict = {}
    if system_instruction:
        config_kw["system_instruction"] = system_instruction
    if temp is not None:
        config_kw["temperature"] = temp
    if response_format and response_format.get("type") == "json_object":
        config_kw["response_mime_type"] = "application/json"

    if tools:
        config_kw["tools"] = _tools_to_gemini(tools)
        config_kw.pop("response_mime_type", None)
        stream = False

    config = types.GenerateContentConfig(**config_kw) if config_kw else None

    _ABORT_SENTINEL = object()

    async def _abort_waiter():
        """轮询 abort_event，触发后返回哨兵值。"""
        while True:
            await asyncio.sleep(0.5)
            if abort_event and abort_event.is_set():
                return _ABORT_SENTINEL

    try:
        aclient = client.aio
        try:
            if abort_event and abort_event.is_set():
                raise asyncio.CancelledError("Aborted")

            if stream and not tools:
                full_content = []
                stream_iter = await asyncio.wait_for(
                    aclient.models.generate_content_stream(
                        model=model, contents=contents, config=config,
                    ),
                    timeout=LLM_REQUEST_TIMEOUT,
                )
                async for chunk in stream_iter:
                    if abort_event and abort_event.is_set():
                        raise asyncio.CancelledError("Aborted")
                    text = chunk.text or ""
                    if text and on_chunk:
                        r = on_chunk(text)
                        if asyncio.iscoroutine(r):
                            await r
                    full_content.append(text)
                return "".join(full_content)

            api_coro = aclient.models.generate_content(
                model=model, contents=contents, config=config,
            )
            if abort_event:
                api_task = asyncio.ensure_future(api_coro)
                abort_task = asyncio.ensure_future(_abort_waiter())
                done, pending = await asyncio.wait(
                    [api_task, abort_task],
                    timeout=LLM_REQUEST_TIMEOUT,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
                if not done:
                    raise TimeoutError(f"LLM request timed out after {LLM_REQUEST_TIMEOUT}s")
                if abort_task in done:
                    api_task.cancel()
                    raise asyncio.CancelledError("Aborted")
                resp = api_task.result()
            else:
                resp = await asyncio.wait_for(api_coro, timeout=LLM_REQUEST_TIMEOUT)
        finally:
            try:
                await aclient.aclose()
            except Exception:
                pass
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise RuntimeError(f"LLM request timed out after {LLM_REQUEST_TIMEOUT}s")
    except asyncio.TimeoutError:
        raise RuntimeError(f"LLM request timed out after {LLM_REQUEST_TIMEOUT}s")
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}") from e

    if abort_event and abort_event.is_set():
        raise asyncio.CancelledError("Aborted")

    function_calls = getattr(resp, "function_calls", None) or []
    if function_calls and resp.candidates:
        model_content = resp.candidates[0].content
        tool_calls = []
        for i, fc in enumerate(function_calls):
            name = getattr(fc, "name", None) or ""
            fn_call = getattr(fc, "function_call", None)
            args = getattr(fn_call, "args", None) if fn_call else getattr(fc, "args", None)
            if args is None and fn_call is not None:
                args = fn_call
            if hasattr(args, "args"):
                args = getattr(args, "args", args)
            args_str = json.dumps(args) if isinstance(args, dict) else (str(args) if args else "{}")
            tool_calls.append({
                "id": f"gc_{i}",
                "type": "function",
                "function": {"name": name, "arguments": args_str},
            })

        return {
            "content": resp.text or "",
            "tool_calls": tool_calls,
            "finish_reason": "tool_calls",
            "gemini_model_content": model_content,
        }

    return resp.text or ""
