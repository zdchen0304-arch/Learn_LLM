---
name: paper-evaluation
description: Criteria for evaluating paper relevance (EvaluatePapers) and filtering (FilterPapers). Use before EvaluatePapers/FilterPapers to ensure consistent scoring and selection. Score 1–5, should_retry when score < 3.
---

# Paper Evaluation

Guidelines for EvaluatePapers and FilterPapers. Use before these tools to ensure consistent scoring and selection.

## EvaluatePapers Scoring (1–5)

| Score | Meaning | Action |
|-------|---------|--------|
| 1 | Irrelevant | should_retry: true if not yet retried |
| 2 | Mostly irrelevant | should_retry: true |
| 3 | Partially relevant | Proceed; consider retry if idea is still fuzzy |
| 4 | Relevant | Proceed |
| 5 | Highly relevant | Proceed |

## should_retry Logic

- **score < 3** and **not yet retried**: Call ExtractKeywords again with refined idea, then SearchArxiv again
- **score >= 3**: Proceed to FilterPapers
- **suggestion**: Use the suggestion field to guide keyword refinement (e.g. "Try adding domain terms like 'medical imaging'")

## FilterPapers Principles

- **Count**: Select 5–8 most relevant papers
- **Order**: By relevance to idea (not by arXiv date)
- **Indices**: Use 1-based indices from papers_summary (e.g. [1, 3, 5, 7, 9] for top 5)
- **Diversity**: Prefer papers that cover different aspects of the idea when possible
- **Avoid**: Duplicate or near-duplicate papers (same authors, same method)

## Relevance Criteria

When evaluating, consider:
- **Direct**: Paper directly addresses the idea's core question
- **Method**: Paper introduces methods relevant to the idea
- **Domain**: Paper is in the same domain (e.g. NLP, ML)
- **Recency**: Prefer recent papers when idea is time-sensitive
- **Citation**: Highly cited papers may indicate foundational work

## Output Format

EvaluatePapers returns: `{"score": 1–5, "should_retry": bool, "suggestion": "string"}`

FilterPapers receives indices and returns: `{"count": N, "indices": [1, 2, ...]}`
