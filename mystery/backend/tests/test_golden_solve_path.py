"""End-to-end integration test simulating the optimal golden path solve."""

from fastapi.testclient import TestClient

from app.main import app
from helpers import inspect_and_discover

client = TestClient(app)


def test_golden_solve_path():
    # 1. Reset
    client.post("/api/session/reset")

    # 2. Inspect locations and work the hotspots to find physical evidence
    # Storage room for ledger page
    found = inspect_and_discover(client, "loc_cafe_storage")
    assert "clue_ledger_page" in found

    # Marcus's house for audited ledger
    found = inspect_and_discover(client, "loc_marcus_house")
    assert "clue_till_discrepancy" in found

    # Cafe for missing till weight
    found = inspect_and_discover(client, "loc_hobbs_cafe")
    assert "clue_till_weight_missing" in found

    # Kitchen for found till weight (requires missing weight as prereq)
    found = inspect_and_discover(client, "loc_cafe_kitchen")
    assert "clue_till_weight_found" in found
    assert "clue_blue_coat_damp" in found

    # 3. Interview Ben to place Clara near the rear alley
    r = client.post("/api/interview/ask", json={
        "agent_id": "agent_ben",
        "question_type": "timeline",
        "time_reference": "07:45"
    })
    assert any(c["clue_id"] == "clue_ben_sighting" for c in r.json()["revealed_clues"])

    # 4. Check readiness hints on the board
    r = client.get("/api/board")
    hints = r.json()["readiness_hints"]
    # We should have found motive and opportunity (maybe method too)
    assert any("motive" in h.lower() for h in hints) or any("opportunity" in h.lower() for h in hints)

    # 5. Submit accusation against Clara
    r = client.post("/api/accuse", json={
        "accused_agent_id": "agent_clara",
        "motive_answer": "She was stealing money from the till, and Marcus threatened to expose her to the committee with the ledger.",
        "method_answer": "She struck him with the brass till weight.",
        "opportunity_answer": "She lied about being at the fountain and went through the rear alley door.",
        "supporting_clue_ids": ["clue_ledger_page", "clue_till_weight_found"]
    })
    assert r.status_code == 200
    result = r.json()
    
    assert result["killer_correct"] is True
    assert result["motive_correct"] is True
    assert result["method_correct"] is True
    assert result["opportunity_correct"] is True
    assert result["score"] >= 90  # Should be a very high score
