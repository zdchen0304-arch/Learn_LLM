def test_control_tower_exposes_director_and_quality_gates(client, session_headers):
    created = client.post("/api/research", headers=session_headers, json={"prompt": "Study reliable multi-agent systems"})
    assert created.status_code == 200

    research_id = created.json()["researchId"]
    response = client.get(f"/api/research/{research_id}/control-tower", headers=session_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["director"]["name"] == "Research Director"
    assert [gate["stage"] for gate in payload["qualityGates"]] == ["refine", "plan", "execute", "paper"]
    assert any(contract["contractId"] == "stage:refine" for contract in payload["taskContracts"])
