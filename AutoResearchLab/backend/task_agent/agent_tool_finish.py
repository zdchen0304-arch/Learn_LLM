"""Finish output parsing helpers for Task Agent tools."""

import json
from typing import Any, Tuple


def _finish_output_kind(output_format: str) -> str:
    fmt = (output_format or "").strip().lower()
    if "markdown" in fmt or fmt in {"md", "text", "plain text", "plain-text"}:
        return "markdown"
    if "json" in fmt:
        return "json"
    if any(
        token in fmt
        for token in (
            "array",
            "object",
            "dict",
            "dictionary",
            "table",
            "csv",
            "matrix",
            "tensor",
            "time-series",
            "time series",
        )
    ):
        return "structured"
    return "markdown"


def run_finish(output: str, output_format: str = "") -> Tuple[bool, Any]:
    """
    Execute Finish. Returns (True, parsed_output) on success; (False, error_msg) on parse failure.
    output: JSON string or Markdown. For JSON we parse to dict.
    """
    if output is None or (isinstance(output, str) and not output.strip()):
        return False, "Error: output cannot be empty"
    s = output.strip() if isinstance(output, str) else str(output)
    expected_kind = _finish_output_kind(output_format)
    try:
        parsed = json.loads(s)
        if expected_kind in ("json", "structured") and isinstance(parsed, str):
            return (
                False,
                "Error: Finish output for format "
                f"'{output_format or 'structured'}' must be structured JSON, not a plain string",
            )
        if (
            expected_kind == "structured"
            and isinstance(parsed, dict)
            and set(parsed.keys()) == {"content"}
            and isinstance(parsed.get("content"), str)
        ):
            return (
                False,
                "Error: Finish output for format "
                f"'{output_format or 'structured'}' must contain structured fields/artifact references, "
                "not a prose-only content wrapper",
            )
        if isinstance(parsed, dict):
            return True, parsed
        if expected_kind == "markdown":
            return True, {"content": parsed}
        return True, {"content": parsed}
    except json.JSONDecodeError:
        pass
    if expected_kind in ("json", "structured"):
        return False, f"Error: Finish output for format '{output_format or 'JSON'}' must be valid JSON"
    return True, {"content": s}
