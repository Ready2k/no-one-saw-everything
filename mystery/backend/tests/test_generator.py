"""Tests for procedural case generation API."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_generate_case_no_activate():
    # Generate without activating
    r = client.post("/api/cases/generate", json={
        "case_type": "debt",
        "difficulty": "standard",
        "seed": 42,
        "activate": False
    })
    assert r.status_code == 200
    data = r.json()
    assert data["case_id"] == "gen_debt_42"
    assert data["validation"]["valid"] is True
    assert data["active_session_id"] is None
    
    # Board should not have the new case
    board = client.get("/api/board").json()
    assert board["readiness_hints"] is not None # just check it doesn't crash

def test_generate_case_with_activate():
    r = client.post("/api/cases/generate", json={
        "case_type": "betrayal",
        "difficulty": "standard",
        "seed": 99,
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    assert data["case_id"] == "gen_betrayal_99"
    assert data["active_session_id"] == "gen_betrayal_99"
    
    # The active case is now gen_betrayal_99
    case_info = client.get("/api/case").json()
    assert case_info["case_id"] == "gen_betrayal_99"
