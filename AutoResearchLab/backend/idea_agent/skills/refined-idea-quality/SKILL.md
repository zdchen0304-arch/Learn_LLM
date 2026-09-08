---
name: refined-idea-quality
description: Quality criteria for refined_idea output. Use before RefineIdea or when ValidateRefinedIdea returns low score. Focus on concrete, decomposable, and specific output.
---

# Refined Idea Quality Criteria

Guidelines for producing a high-quality refined idea (Markdown) that is decomposable into 3–10 tasks. Quality matters.

## Quality Rules

1. **Concrete over vague**: "Compare BERT and GPT on code completion benchmarks" not "Research NLP models".
2. **Combine literature insights with novel angles**: Avoid mere summarization; add synthesis, comparison, or gap.
3. **Must be decomposable**: If you cannot list 3+ distinct sub-tasks, refine further.
4. **Gap must be specific**: Name limitations (e.g. "prior work focuses on X, neglects Y") rather than generic "more research needed".

## Validation Hints (ValidateRefinedIdea)

- Score >= 4: Proceed to FinishIdea.
- Score < 4: Call RefineIdea again with improvements — tighten scope, clarify questions, or sharpen gap.

## Red Flags

- Output contains "research" without scope
- Questions are yes/no or too broad
- Gap is generic ("limited studies", "need more work")
- Method or approach is a single vague step
