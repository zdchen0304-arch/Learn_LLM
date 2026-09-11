# Paper quality review report schema

Return one JSON object with this shape:

```json
{
  "summary": "Short evidence-based assessment.",
  "blockingIssueCount": 0,
  "scores": {
    "structure": 0,
    "claimEvidence": 0,
    "methodology": 0,
    "reproducibility": 0
  },
  "claimAudit": [
    {
      "claim": "Short claim",
      "location": "Results, Table 2",
      "status": "supported",
      "evidence": ["task artifact id"],
      "reason": "Why supplied evidence supports or fails to support the claim."
    }
  ],
  "findings": [
    {
      "id": "PQR-001",
      "severity": "major",
      "category": "claim_evidence",
      "location": "Abstract, sentence 3",
      "issue": "Specific observed issue",
      "requiredEvidence": "Evidence needed to resolve it",
      "recommendedAction": "Smallest useful revision"
    }
  ],
  "revisionPlan": [
    {
      "priority": 1,
      "findingIds": ["PQR-001"],
      "action": "Concrete revision action"
    }
  ]
}
```

Scores range from 0 to 4. They are diagnostic signals, not an acceptance decision.
