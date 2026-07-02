"""End-to-end integration test simulating the optimal golden path solve."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_golden_solve_path():
    # 1. Reset
    client.post("/api/session/reset")

    # 2. Inspect locations to find physical evidence
    # Storage room for ledger page
    r = client.post("/api/inspect", json={"location_id": "loc_cafe_storage"})
    assert any(c["clue_id"] == "clue_ledger_page" for c in r.json()["new_clues"])

    # Marcus's house for audited ledger
    r = client.post("/api/inspect", json={"location_id": "loc_marcus_house"})
    assert any(c["clue_id"] == "clue_till_discrepancy" for c in r.json()["new_clues"])

    # Cafe for missing till weight
    r = client.post("/api/inspect", json={"location_id": "loc_hobbs_cafe"})
    assert any(c["clue_id"] == "clue_till_weight_missing" for c in r.json()["new_clues"])

    # Kitchen for found till weight (requires missing weight as prereq)
    r = client.post("/api/inspect", json={"location_id": "loc_cafe_kitchen"})
    found_clues = [c["clue_id"] for c in r.json()["new_clues"]]
    assert "clue_till_weight_found" in found_clues
    assert "clue_blue_coat_damp" in found_clues

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
