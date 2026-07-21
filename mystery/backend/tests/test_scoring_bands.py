"""Tests for accusation scoring with partial or incorrect solves."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_wrong_killer():
    client.post("/api/session/reset")
    r = client.post("/api/accuse", json={
        "accused_agent_id": "agent_owen",
        "motive_answer": "He owed Marcus money.",
        "method_answer": "Struck him.",
        "opportunity_answer": "He was around.",
        "supporting_clue_ids": []
    })
    assert r.status_code == 200
    result = r.json()
    assert result["killer_correct"] is False
    assert result["score"] < 50


def test_correct_killer_missing_motive_and_method():
    client.post("/api/session/reset")
    r = client.post("/api/accuse", json={
        "accused_agent_id": "agent_clara",
        "motive_answer": "She hated him.",
        "method_answer": "Poison maybe?",
        "opportunity_answer": "She was at the cafe.",
        "supporting_clue_ids": []
    })
    assert r.status_code == 200
    result = r.json()
    assert result["killer_correct"] is True
    assert result["motive_correct"] is False
    assert result["method_correct"] is False
    # Getting the killer right but no reasoning should be a middling/low score
    assert 20 <= result["score"] <= 60
