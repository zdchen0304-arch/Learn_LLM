---
name: paper-quality-review
description: Review a research paper draft against supplied artifacts for evidence, methods, citations, reproducibility, and academic-integrity risks. Use after drafting, not to create a paper from scratch.
---

# Paper Quality Review

## Objective

Return an evidence-aware review report that distinguishes observed defects from
inference. Identify the smallest actionable revisions needed to make a draft
traceable to supplied research artifacts.

## Required inputs

- Paper draft in Markdown, LaTeX, or plain text.
- Research plan and available task outputs.
- Optional reference metadata, target venue, and evaluation criteria.

If evidence is absent, mark a claim `unverifiable`; do not treat it as true or
false and do not invent citations, results, or numerical values.

## Review procedure

1. Inventory sections, major claims, figures/tables, citations, and supplied artifacts.
2. Audit each major claim as `supported`, `partially_supported`, `unsupported`, or `unverifiable`.
3. Check methods, experiment design, baselines, metrics, limitations, and reproducibility details.
4. Check citations only against supplied or verified metadata.
5. Classify findings as `blocker`, `major`, `minor`, or `suggestion`.
6. Return JSON following `references/report-schema.md`.

## Constraints

- Give every finding a section, figure/table, or short excerpt location.
- Do not rewrite the paper unless explicitly requested.
- Do not issue an accept/reject decision unless explicitly requested.
- A blocker is reserved for unsupported central claims, invalid results, or a
  missing condition required to reproduce the main conclusion.
