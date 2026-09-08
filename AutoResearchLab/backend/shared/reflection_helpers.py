"""Reusable evaluation/skill helper functions for reflection loop."""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import json_repair
from loguru import logger

from shared.constants import TEMP_REFLECT, TEMP_SKILL_GEN
from shared.idea_utils import get_idea_text
from shared.llm_client import chat_completion, merge_phase_config

_AGENT_DIRS = {
    "idea": Path(__file__).resolve().parent.parent / "idea_agent",
    "plan": Path(__file__).resolve().parent.parent / "plan_agent",
    "task": Path(__file__).resolve().parent.parent / "task_agent",
}

_prompt_cache: Dict[str, str] = {}


def _get_prompt(path: Path) -> str:
    key = str(path)
    if key not in _prompt_cache:
        _prompt_cache[key] = path.read_text(encoding="utf-8").strip()
    return _prompt_cache[key]


def _parse_json_from_response(text: str) -> dict:
    """Extract JSON from LLM response (supports fenced code + json_repair)."""
    cleaned = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if m:
        cleaned = m.group(1).strip()
    try:
        result = json_repair.loads(cleaned)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def _build_idea_eval_context(output: dict, context: dict) -> str:
    idea = context.get("idea", "")
    keywords = output.get("keywords", [])
    papers = output.get("papers", [])
    refined = output.get("refined_idea")
    refined_desc = get_idea_text(refined)

    papers_summary = ""
    for p in papers[:10]:
        title = p.get("title", "") if isinstance(p, dict) else str(p)
        papers_summary += f"  - {title}\n"

    return f"""**Original idea:** {idea}

**Extracted keywords:** {', '.join(keywords) if keywords else '(none)'}

**Retrieved papers ({len(papers)} total):**
{papers_summary or '  (none)'}

**Refined idea:** {refined_desc or '(none)'}"""


def _build_plan_eval_context(output: dict, context: dict) -> str:
    idea = context.get("idea", "")
    tasks = output.get("tasks", [])
    lines = []
    for t in tasks:
        tid = t.get("task_id", "")
        desc = (t.get("description") or "")[:100]
        deps = ",".join(t.get("dependencies") or [])
        has_io = "Y" if (t.get("input") and t.get("output")) else "N"
        lines.append(f"  - {tid}: {desc} | deps:[{deps}] io:{has_io}")
    tasks_summary = "\n".join(lines) if lines else "  (no tasks)"
    return f"""**Idea:** {idea}

**Plan tasks ({len(tasks)} total):**
{tasks_summary}"""


def _build_task_eval_context(output: Any, context: dict) -> str:
    task_id = context.get("task_id", "")
    description = context.get("description", "")
    output_spec = context.get("output_spec", {})

    content_str = ""
    if isinstance(output, dict):
        content = output.get("content", output)
        content_str = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    elif isinstance(output, str):
        content_str = output
    else:
        content_str = str(output)

    return f"""**Task ID:** {task_id}
**Description:** {description}
**Expected output format:** {output_spec.get('format', '')}
**Expected output description:** {output_spec.get('description', '')}

**Actual output (truncated to 6000 chars):**
```
{content_str[:6000]}
```"""


_CONTEXT_BUILDERS = {
    "idea": _build_idea_eval_context,
    "plan": _build_plan_eval_context,
    "task": _build_task_eval_context,
}


def _raise_if_aborted(abort_event: Optional[Any]) -> None:
    if abort_event is not None and abort_event.is_set():
        raise asyncio.CancelledError("Aborted during reflection")


async def self_evaluate(
    agent_type: str,
    output: Any,
    context: dict,
    on_thinking: Optional[Callable] = None,
    abort_event: Optional[Any] = None,
    api_config: Optional[dict] = None,
) -> dict:
    """Evaluate agent output quality."""
    _raise_if_aborted(abort_event)

    prompt_path = _AGENT_DIRS[agent_type] / "prompts" / "reflect-prompt.txt"
    system_prompt = _get_prompt(prompt_path)

    builder = _CONTEXT_BUILDERS.get(agent_type)
    if not builder:
        raise ValueError(f"Unknown agent_type: {agent_type}")
    user_message = builder(output, context)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    def stream_chunk(chunk: str):
        if on_thinking and chunk:
            return on_thinking(chunk, task_id=None, operation="Reflect", schedule_info=None)

    cfg = merge_phase_config(api_config or {}, "reflect")
    content = await chat_completion(
        messages,
        cfg,
        on_chunk=stream_chunk if on_thinking else None,
        abort_event=abort_event,
        stream=on_thinking is not None,
        temperature=TEMP_REFLECT,
    )

    result = _parse_json_from_response(content if isinstance(content, str) else "")
    score = result.get("score", 0)
    if isinstance(score, (int, float)):
        score = max(0, min(100, int(score)))
    else:
        score = 0

    return {
        "score": score,
        "analysis": result.get("analysis", ""),
        "dimensions": result.get("dimensions", {}),
        "improvement_areas": result.get("improvement_areas", []),
        "skill_suggestion": result.get("skill_suggestion", {}),
    }


async def generate_skill_from_reflection(
    agent_type: str,
    evaluation: dict,
    context: dict,
    api_config: Optional[dict] = None,
    abort_event: Optional[Any] = None,
) -> Optional[str]:
    """Generate SKILL.md text from evaluation when skill_suggestion requests it."""
    _raise_if_aborted(abort_event)

    suggestion = evaluation.get("skill_suggestion", {})
    if not suggestion or not suggestion.get("should_create"):
        return None

    prompt_path = Path(__file__).resolve().parent / "prompts" / "skill-generation-prompt.txt"
    system_prompt = _get_prompt(prompt_path)

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    user_message = f"""**Agent type:** {agent_type}
**Timestamp:** {timestamp}
**Evaluation score:** {evaluation.get('score', 0)}
**Analysis:** {evaluation.get('analysis', '')}

**Improvement areas:**
{json.dumps(evaluation.get('improvement_areas', []), ensure_ascii=False, indent=2)}

**Skill suggestion:**
- name: {suggestion.get('name', '')}
- description: {suggestion.get('description', '')}
- instructions: {suggestion.get('instructions', '')}

Generate the SKILL.md content."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    cfg = merge_phase_config(api_config or {}, "reflect")
    content = await chat_completion(
        messages,
        cfg,
        on_chunk=None,
        abort_event=abort_event,
        stream=False,
        temperature=TEMP_SKILL_GEN,
    )

    text = content if isinstance(content, str) else ""
    m = re.search(r"```(?:markdown)?\s*([\s\S]*?)```", text)
    if m:
        return m.group(1).strip()
    stripped = text.strip()
    if stripped.startswith("---"):
        return stripped
    return None


def save_learned_skill(agent_type: str, skill_name: str, skill_content: str) -> Path:
    """Save learned skill under corresponding agent skills directory."""
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", skill_name).strip("-")[:60]
    if not safe_name:
        safe_name = f"learned-{int(time.time())}"

    skills_dir = _AGENT_DIRS[agent_type] / "skills"
    skill_dir = skills_dir / safe_name
    if skill_dir.exists():
        safe_name = f"{safe_name}-{int(time.time() * 1000) % 100000}"
        skill_dir = skills_dir / safe_name

    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(skill_content, encoding="utf-8")
    logger.info("Saved learned skill: %s -> %s", skill_name, skill_path)
    return skill_path
