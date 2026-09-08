"""Shared utilities."""

import re
from typing import Optional

_CODEBLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


def extract_codeblock(text: str) -> Optional[str]:
    """Extract content from a fenced code block (```json...``` or ```...```).

    Returns the inner text stripped, or None if no code block found.
    """
    m = _CODEBLOCK_RE.search(text or "")
    return m.group(1).strip() if m else None


def chunk_string(s: str, size: int):
    """Yield string in chunks for simulated streaming."""
    for i in range(0, len(s), size):
        yield s[i : i + size]
