---
name: research-templates
description: Three academic research templates (Heilmeier, scientific discovery, system optimization) with schemas and use cases. Use when RefineIdea to align output structure with research type.
---

# Research Templates

Three academic templates for structuring refined research ideas. Use when RefineIdea to choose the output structure that best fits the research type.

## Template Selection

| Template ID | Use When | Core Fields |
|-------------|----------|-------------|
| **heilmeier_catechism** | Engineering/applied research, system building, DARPA-style proposals | problem_statement, state_of_the_art, key_insight, impact, technical_plan, risks_and_mitigations |
| **scientific_discovery** | Theoretical AI, algorithms, experiments (NeurIPS/ICLR style) | research_question, hypothesis, related_work_gap, proposed_method, experimental_design, expected_results |
| **system_optimization** | Performance tuning, resource efficiency, benchmarking | target_system, bottleneck_analysis, optimization_strategy, implementation_steps, evaluation_metrics |

## Heilmeier Catechism

For engineering and applied research. You may use these fields to organize your output (not required):

- **problem_statement**: What is the problem? Why does it matter?
- **state_of_the_art**: Current solutions and limitations
- **key_insight**: Novel angle or approach
- **impact**: Expected benefit (e.g. efficiency, scalability)
- **technical_plan**: High-level implementation steps
- **risks_and_mitigations**: Main risks and how to address them

## Scientific Discovery

For theory and experiments. You may use these fields (not required):

- **research_question**: Central RQ (RQ1:, RQ2:)
- **hypothesis**: Testable claim
- **related_work_gap**: Limitations of prior work
- **proposed_method**: Method outline
- **experimental_design**: Setup, metrics, baselines
- **expected_results**: Anticipated findings

## System Optimization

For performance and efficiency. You may use these fields (not required):

- **target_system**: System or component to optimize
- **bottleneck_analysis**: Current limitations
- **optimization_strategy**: Approach (e.g. caching, parallelism)
- **implementation_steps**: Concrete steps
- **evaluation_metrics**: How to measure success

Use whichever structure best fits the research type. Quality matters; schema is flexible.
