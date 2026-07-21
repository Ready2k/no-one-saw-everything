"""Depth-gated relationship backstory (min_ask_count rules)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_relationship_backstory_unlocks_on_second_ask():
    ask = {"agent_id": "agent_elias", "question_type": "relationship"}
    r1 = client.post("/api/interview/ask", json=ask).json()
    r2 = client.post("/api/interview/ask", json=ask).json()
    # First ask gets the base answer and advertises the follow-up.
    assert "Forty years" in r1["deterministic_answer_text"]
    assert any("first meet" in f for f in r1["suggested_followups"])
    # Second ask unlocks the depth-gated backstory.
    assert "I taught him" in r2["deterministic_answer_text"]
    assert r1["deterministic_answer_text"] != r2["deterministic_answer_text"]


def test_free_text_first_met_reaches_backstory():
    # Base relationship answer first...
    client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_isabella", "question_type": "relationship"},
    )
    # ...then the natural free-text follow-up lands the backstory rule.
    r = client.post(
        "/api/interview/free-text",
        json={
            "agent_id": "agent_isabella",
            "question": "Let's go back to how you first met the deceased.",
        },
    ).json()
    assert r["intent"]["intent"] == "relationship"
    assert "bank" in r["answer"]["deterministic_answer_text"]
