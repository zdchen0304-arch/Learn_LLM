---
name: topic-refinement
description: Guidelines for refining broad or fuzzy ideas into concrete research topics. Use when user input is vague to guide ExtractKeywords and RefineIdea. Includes RESEARCH_TOPIC_SCHEMA and refinement tactics.
---

# Topic Refinement

Guidelines for turning broad or fuzzy research ideas into concrete, executable topics. Use when the user's idea is vague (e.g. "调研某技术", "research AI") to guide ExtractKeywords and RefineIdea.

## Broad vs Specific

When to refine further:

- **Broad**: Idea is a domain ("AI", "机器学习") or activity ("research") without scope
- **Specific**: Idea names a method, comparison, or deliverable ("Compare BERT vs GPT for code completion", "Survey federated learning 2020–2024")

If broad, apply refinement tactics before ExtractKeywords.

## RESEARCH_TOPIC_SCHEMA

A well-refined topic typically has:

| Field | Description |
|-------|-------------|
| **title** | Short, concrete title (e.g. "Federated Learning for Medical Imaging") |
| **keywords** | 3–5 technical terms for arXiv search |
| **tldr** | 1–2 sentence summary |
| **abstract** | 2–4 sentences: problem, approach, contribution |
| **refinement_reason** | Why this scope was chosen (if narrowed from broader idea) |

## Refinement Tactics

When the idea is too broad:

1. **Narrow by domain**: "AI in healthcare" → "AI for medical image diagnosis"
2. **Narrow by output**: "Research X" → "Produce comparison report on X vs Y"
3. **Add constraints**: "Survey frameworks" → "Survey Python web frameworks (2020+)"
4. **Split by dimension**: "Evaluate tools" → "Evaluate by performance" + "Evaluate by ecosystem"

## For ExtractKeywords

After refinement, keywords should be:
- Technical and domain-specific
- 3–5 terms
- Aligned with the narrowed scope

## For RefineIdea

When the idea was refined, ensure the output:
- Reflects the narrowed scope
- Has clear questions or goals that match the refined topic
- Includes refinement_reason if the scope was narrowed from a broader idea
