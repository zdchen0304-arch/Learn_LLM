# Research Control Tower demo

This page is a concise interview walkthrough for the MAARS multi-agent
research architecture.

## One-minute explanation

MAARS is not presented as four chatbots passing text along. It has a
**Supervisor–Worker control plane** over a staged execution data plane:

1. The **Research Director** owns sequencing and policy. It does not perform
   research work itself.
2. Each stage has a **Lead** that delegates to specialised workers through a
   task contract: owner, goal, dependencies, expected outputs, and status.
3. **Quality gates** protect every handoff. A downstream stage is blocked until
   the upstream artifacts prove its contract is satisfied.
4. The task DAG answers scheduling questions; the evidence lineage answers
   provenance questions. They are deliberately different views.
5. Paper generation is followed by a dedicated **Paper Quality Review Skill**.
   A blocking review creates a `needs_revision` gate instead of a false sense
   of completion.

## Demonstration sequence

1. Create a Research in Mock mode and open its detail page.
2. Point out the Control Tower's role hierarchy: Director → stage Lead →
   workers. This demonstrates the master–worker relationship.
3. Run Refine and show the first gate turn `passed` only once a refined idea
   and keywords are persisted.
4. Run Plan and use the existing Workbench to explain the execution DAG. Then
   return to Task Contracts to show that a DAG node and a delivery commitment
   are different concepts.
5. Run Execute and show validated outputs entering Evidence Lineage.
6. Run Paper. Explain that the review is a separate quality activity: review
   findings are persisted and may turn the final gate into `needs_revision`.

## APIs and durable state

| Capability | API / storage |
| --- | --- |
| Control-plane snapshot | `GET /api/research/{researchId}/control-tower` |
| Refresh a saved paper review | `POST /api/paper/review` |
| Review report | SQLite `paper_reviews` table |
| Real-time review update | `paper-review-complete` SSE event |

## Acceptance checklist

- The Control Tower displays organization, quality gates, contracts, and
  evidence lineage independently.
- The existing Workbench continues to display the execution DAG independently.
- A saved paper review is returned with the Research detail payload.
- A review containing a blocker yields `needs_revision` for the Paper gate.
- The review Skill does not invent evidence or citations; claims without
  supplied support are reported as `unverifiable`.
