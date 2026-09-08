---
name: keyword-extraction
description: Guidelines for extracting arXiv search keywords from fuzzy research ideas. Use before ExtractKeywords or when EvaluatePapers suggests retry. Ensures keywords are technical, domain-specific, and suitable for literature retrieval.
---

# Keyword Extraction for arXiv

Guidelines for turning fuzzy research ideas into effective arXiv search keywords.

## Principles

1. **Technical over generic**: Prefer domain nouns (e.g. "transformer", "reinforcement learning") over vague terms ("research", "study").
2. **3–5 keywords**: Enough to narrow scope; avoid single overly broad or many overlapping terms.
3. **No stop words**: Exclude "the", "a", "and", "for", "with" — arXiv handles these.
4. **Combine concepts**: If idea spans multiple areas, include 1–2 terms per area (e.g. "federated learning" + "privacy" + "healthcare").
5. **Use arXiv categories when inferable**: cs.AI, cs.LG, stat.ML for ML; cs.CL for NLP; etc.

## Common Patterns

| Idea type | Keyword strategy |
|-----------|------------------|
| Method + domain | Method term + application domain (e.g. "attention mechanism", "image segmentation") |
| Comparison | Both compared items + comparison dimension (e.g. "BERT", "GPT", "benchmark") |
| Gap analysis | Broad area + "survey" or "review" + time constraint ("2020", "recent") |
| Implementation | Framework/tool + task (e.g. "PyTorch", "fine-tuning") |

## Retry Triggers

If EvaluatePapers returns score < 3, consider:
- Narrowing keywords (add domain or constraint)
- Replacing generic terms with technical synonyms
- Splitting one broad idea into 2–3 focused keyword sets and searching separately

## Examples

- "用深度学习做医学图像分析" → ["deep learning", "medical image", "diagnosis", "CNN"]
- "大模型在代码生成上的应用" → ["large language model", "code generation", "programming"]
- "联邦学习隐私保护" → ["federated learning", "privacy", "differential privacy"]
