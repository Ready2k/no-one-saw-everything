from fastapi.testclient import TestClient
from app.main import app
from app.session import get_session
from app.case_store import load_case_from_disk
import json
import pytest

client = TestClient(app)

FORBIDDEN_KEYS = [
    "killer_id",
    "true_timeline",
    "hidden_murder",
    "solution_concepts",
    "truthfulness",
    "is_killer",
    "red_herring_role",
    "raw_llm_output",
    "case_plan",
    "repair_prompt"
]

@pytest.fixture(autouse=True)
def setup_golden_case(monkeypatch):
    # These are operator/playtest-only surfaces, gated behind MYSTERY_PLAYTEST_MODE
    # (see test_playtest_gating.py for the gate itself) — enable it for this file.
    monkeypatch.setenv("MYSTERY_PLAYTEST_MODE", "true")
    client.post("/api/cases/activate", json={"case_id": "case_001"})
    yield

def test_playtest_summary_no_leaks():
    response = client.get("/api/session/playtest-summary")
    assert response.status_code == 200
    data = response.json()
    
    assert "telemetry_event_count" in data
    assert "player_action_count" in data
    
    # Ensure no leaks
    data_str = json.dumps(data)
    for key in FORBIDDEN_KEYS:
        assert f'"{key}"' not in data_str

def test_playtest_export_no_leaks_pre_reveal():
    response = client.get("/api/session/playtest-export")
    assert response.status_code == 200
    data = response.json()
    
    assert data["export_visibility"] == "pre_reveal"
    
    # Ensure no leaks
    data_str = json.dumps(data)
    for key in FORBIDDEN_KEYS:
        assert f'"{key}"' not in data_str

def test_playtest_export_post_reveal():
    # Submit accusation
    accuse_payload = {
        "accused_agent_id": "agent_clara",
        "motive_answer": "Test motive",
        "method_answer": "Test method",
        "opportunity_answer": "Test opportunity",
        "supporting_clue_ids": [],
        "supporting_note_ids": []
    }
    client.post("/api/accuse", json=accuse_payload)
    
    # Export again
    response = client.get("/api/session/playtest-export")
    assert response.status_code == 200
    data = response.json()
    
    assert data["export_visibility"] == "post_reveal"
    assert "accusation_result" in data

def test_feedback_submission():
    feedback_payload = {
        "understood_goal": "yes",
        "rewind_made_sense": "mostly",
        "hints_helpfulness": "about_right",
        "difficulty": "about_right",
        "final_reveal_fair": "yes",
        "enjoyment_score": 5,
        "confidence_score": 4,
        "suspected_before_reveal": "Owen",
        "most_confusing_part": "The till weight",
        "best_part": "The accusation",
        "worst_part": None,
        "clues_that_felt_unfair": None,
        "free_text": "Great game!"
    }
    
    response = client.post("/api/session/feedback", json=feedback_payload)
    assert response.status_code == 200
    
    sess = get_session("case_001")
    assert sess.feedback is not None
    assert sess.feedback.enjoyment_score == 5
    assert sess.feedback.most_confusing_part == "The till weight"
