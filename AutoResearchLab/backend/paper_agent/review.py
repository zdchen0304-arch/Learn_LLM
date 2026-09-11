"""Paper Quality Review Skill runtime.

The reviewer is deliberately separate from drafting.  It receives only the
draft and supplied research artifacts, and produces a structured diagnostic
report instead of silently editing the paper.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import json_repair

from shared.constants import TEMP_ANALYSIS
from shared.llm_client import chat_completion, merge_phase_config
from shared.skill_utils import load_skill


PAPER_SKILLS_ROOT = Path(os.getenv("MAARS_PAPER_SKILLS_DIR", Path(__file__).resolve().parent / "skills"))
REVIEW_SKILL_NAME = "paper-quality-review"


def _mock_report(content: str, outputs: dict) -> dict:
    """Deterministic review used by Mock mode and offline tests."""
    has_draft = bool((content or "").strip())
    findings = []
    if not outputs:
        findings.append(
            {
                "id": "PQR-001",
                "severity": "blocker",
                "category": "claim_evidence",
                "location": "Research artifacts",
                "issue": "No task outputs were supplied for evidence review.",
                "requiredEvidence": "Validated task outputs or experiment artifacts.",
                "recommendedAction": "Run and validate planned tasks before finalising claims.",
            }
        )
    return {
        "summary": "Offline review completed against supplied artifacts.",
        "blockingIssueCount": 0 if has_draft and outputs else 1,
        "scores": {"structure": 3 if has_draft else 0, "claimEvidence": 2 if outputs else 0, "methodology": 2, "reproducibility": 1},
        "claimAudit": [],
        "findings": findings,
        "revisionPlan": [],
    }


def _artifact_digest(outputs: dict, limit: int = 1000) -> list[dict]:
    digest = []
    for task_id, output in (outputs or {}).items():
        value = output.get("content") if isinstance(output, dict) else output
        text = str(value or "").strip().replace("\n", " ")
        digest.append({"taskId": str(task_id), "summary": text[:limit]})
    return digest


def _normalize_report(value: Any) -> dict:
    report = value if isinstance(value, dict) else {}
    findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    blocking_count = sum(1 for item in findings if isinstance(item, dict) and item.get("severity") == "blocker")
    return {
        "summary": str(report.get("summary") or "Paper quality review completed."),
        "blockingIssueCount": int(report.get("blockingIssueCount") or blocking_count),
        "scores": report.get("scores") if isinstance(report.get("scores"), dict) else {},
        "claimAudit": report.get("claimAudit") if isinstance(report.get("claimAudit"), list) else [],
        "findings": findings,
        "revisionPlan": report.get("revisionPlan") if isinstance(report.get("revisionPlan"), list) else [],
    }


async def review_paper(
    *,
    content: str,
    plan: dict,
    outputs: dict,
    api_config: dict,
    abort_event: Optional[Any] = None,
) -> dict:
    """Review a draft using the paper-quality-review Skill and return JSON."""
    if not str(content or "").strip():
        raise ValueError("Paper draft is empty; review cannot start.")
    if api_config.get("paperUseMock", True):
        return _mock_report(content, outputs)

    skill = load_skill(PAPER_SKILLS_ROOT, REVIEW_SKILL_NAME)
    if skill.startswith("Error:"):
        raise RuntimeError(f"Paper review Skill unavailable: {skill}")
    context = {
        "plan": plan or {},
        "artifactDigest": _artifact_digest(outputs),
        "paperDraft": content,
    }
    cfg = merge_phase_config(api_config, "paper_review")
    raw = await chat_completion(
        [
            {"role": "system", "content": skill},
            {"role": "user", "content": "Review this paper only against the supplied artifacts. Return the required JSON report.\n\n" + json.dumps(context, ensure_ascii=False)},
        ],
        cfg,
        stream=False,
        temperature=TEMP_ANALYSIS,
        response_format={"type": "json_object"},
        abort_event=abort_event,
    )
    text = raw if isinstance(raw, str) else raw.get("content") or "{}"
    try:
        parsed = json_repair.loads(text)
    except Exception as exc:
        raise RuntimeError(f"Paper review returned invalid JSON: {exc}") from exc
    return _normalize_report(parsed)
