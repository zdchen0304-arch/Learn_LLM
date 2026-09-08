"""Shared mock data loading utilities for all agents."""

from pathlib import Path
from typing import Dict, Optional

import orjson

_mock_caches: Dict[str, Dict[str, dict]] = {}


def get_mock_cached(mock_ai_dir: Path, response_type: str) -> dict:
    """Load and cache mock AI response JSON from a mock-ai directory."""
    dir_key = str(mock_ai_dir)
    cache = _mock_caches.setdefault(dir_key, {})
    if response_type not in cache:
        path = mock_ai_dir / f"{response_type}.json"
        try:
            cache[response_type] = orjson.loads(path.read_bytes())
        except (FileNotFoundError, orjson.JSONDecodeError):
            cache[response_type] = {}
    return cache[response_type]


def load_mock_entry(
    mock_ai_dir: Path,
    response_type: str,
    key: str,
    *,
    fallback_key: str = "_default",
) -> Optional[Dict]:
    """Load a mock entry with {content, reasoning} from mock cache.

    Looks up by ``key``, falls back to ``fallback_key``.
    """
    data = get_mock_cached(mock_ai_dir, response_type)
    entry = data.get(key) or data.get(fallback_key)
    if not entry:
        return None
    content = entry.get("content")
    content_str = content if isinstance(content, str) else orjson.dumps(content).decode("utf-8")
    return {"content": content_str, "reasoning": entry.get("reasoning", "")}
