"""Helpers for structured-output generation with repair retries."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Sequence


ModelCall = Callable[[list[dict], float], Awaitable[str]]
ParseFn = Callable[[str], Any]
ValidateFn = Callable[[Any], tuple[bool, str]]


def build_repair_prompt(error_message: str) -> str:
    detail = (error_message or "Structured output validation failed.").strip()
    return (
        "Your previous response did not satisfy the required output format.\n"
        f"Error: {detail}\n\n"
        "Return a corrected response only.\n"
        "Do not explain the mistake.\n"
        "Do not repeat the task description.\n"
        "Preserve the intended semantics, but fix the output so it matches the required structure exactly."
    )


async def generate_with_repair(
    *,
    base_messages: list[dict],
    model_call: ModelCall,
    parse_fn: ParseFn,
    temperatures: Sequence[float],
    validate_fn: ValidateFn | None = None,
    repair_prompt_builder: Callable[[str], str] | None = None,
) -> tuple[Any, str]:
    """Generate structured output, parse it, and on failure ask the model to repair its own output."""
    attempts = list(temperatures) or [0.0]
    repair_prompt_builder = repair_prompt_builder or build_repair_prompt
    conversation = list(base_messages)
    last_error = "Structured output generation failed"

    for index, temperature in enumerate(attempts):
        raw = await model_call(conversation, float(temperature))
        try:
            parsed = parse_fn(raw)
            if validate_fn is not None:
                valid, message = validate_fn(parsed)
                if not valid:
                    raise ValueError(message or "Structured output validation failed")
            return parsed, raw
        except Exception as exc:
            last_error = str(exc) or last_error
            if index >= len(attempts) - 1:
                raise ValueError(last_error) from exc
            conversation = list(base_messages)
            if (raw or "").strip():
                conversation.append({"role": "assistant", "content": raw})
            conversation.append({"role": "user", "content": repair_prompt_builder(last_error)})

    raise ValueError(last_error)