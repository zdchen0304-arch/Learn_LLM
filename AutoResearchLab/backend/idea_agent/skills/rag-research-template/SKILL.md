---
name: rag-research-template
description: Advanced RAG-style research schema with literature-grounded fields. Use when RefineIdea for hardware-aware or citation-heavy proposals.
---

# RAG Research Template

Advanced research template for literature-grounded idea refinement. Use when the research requires explicit citation of sources (e.g. gap, innovation) or hardware/feasibility constraints.

## Schema Fields (use as needed)

| Field | Description |
|-------|-------------|
| **title** | Concise research title |
| **gap** | Research gap and limitations (use [Source ID: X] when citing papers) |
| **hypothesis** | Core hypothesis or claim |
| **innovation** | Key innovation points (use [Source ID: X] for citations) |
| **topology** | Model or system topology / flow |
| **components** | Key components (list) |
| **success_metric** | Quantifiable metrics |
| **deliverable** | Expected deliverable output |
| **baselines** | Comparison baselines |
| **cited_source_ids** | Indices of cited papers (0-based) |
| **ai_evaluation** | Optional self-assessment: scores (novelty, feasibility, research_value, writing), feedback |

## When to Use

- Hardware-constrained research (VRAM, compute)
- Proposals requiring explicit literature citations
- DARPA-style or grant-style structured output

Output whatever structure best captures the idea. Quality matters; schema is flexible.
