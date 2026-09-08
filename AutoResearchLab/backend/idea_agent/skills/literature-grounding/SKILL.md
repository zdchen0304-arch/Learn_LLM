---
name: literature-grounding
description: Guidelines for citing literature in refined ideas. Use [Source ID: X] format when referencing papers. Apply when RefineIdea output should be grounded in retrieved papers.
---

# Literature Grounding

Guidelines for grounding refined research ideas in retrieved literature. Use when RefineIdea output should explicitly cite papers from SearchArxiv/FilterPapers.

## Citation Format

Use `[Source ID: X]` where X is the 0-based index of the paper in the papers list (or filtered_papers).

Example: "Prior work on federated learning [Source ID: 2] shows that..."

## When to Cite

- **Gap**: When stating limitations of existing work
- **Innovation**: When contrasting your approach with prior methods
- **Related work**: When building on specific findings

## Rules

1. Every technical claim about prior work should cite a source
2. Scores in self-evaluation (if used) must be FLOAT 1.0–10.0
3. Do not copy example scores; reflect actual idea quality
4. cited_source_ids should list indices of papers actually referenced

## For RefineIdea

When papers_context is available, ensure:
- research_gap references specific papers
- method_approach acknowledges prior approaches where relevant
- Avoid unsupported claims; ground in retrieved literature
