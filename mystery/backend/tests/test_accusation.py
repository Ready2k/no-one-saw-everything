"""Accusation judge tests (Phase 6)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.case_store import load_case_from_disk as load_case

client = TestClient(app)

CASE = load_case("case_001")


@pytest.fixture(autouse=True)
def fresh_session():
    client.post("/api/session/reset")
    yield


def _discover(clue_ids):
    """Force-discover clues by driving the real discovery paths where cheap,
    else via the observation/inspection endpoints."""
    # Ledger page + rear-door + till weight via inspection/observation.
    client.post("/api/inspect", json={"location_id": "loc_cafe_storage"})  # ledger, notes
    client.post("/api/inspect", json={"location_id": "loc_hobbs_cafe"})  # till missing
    client.post("/api/inspect", json={"location_id": "loc_cafe_kitchen"})  # damp coat, weight found
    client.post("/api/events/ev_0758_rear_door/pin")  # rear door observation
    client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_ben", "question_type": "timeline", "time_reference": "07:47"},
    )  # ben sighting + storage sound
    client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_nadia", "question_type": "timeline", "time_reference": "07:40"},
    )  # nadia overheard


STRONG_MOTIVE = "Marcus was blackmailing Clara after he found she had been stealing cash from the cafe till."
STRONG_METHOD = "Blunt force with the brass till weight."
STRONG_OPPORTUNITY = (
    "Clara was at the cafe rear door during the murder window and lied about being at the fountain."
)


def test_correct_clara_accusation_scores_high():
    _discover(None)
    r = client.post(
        "/api/accuse",
        json={
            "accused_agent_id": "agent_clara",
            "motive_answer": STRONG_MOTIVE,
            "method_answer": STRONG_METHOD,
            "opportunity_answer": STRONG_OPPORTUNITY,
            "supporting_clue_ids": [
                "clue_ledger_page",
                "clue_ben_sighting",
                "clue_till_weight_found",
                "clue_rear_door",
                "clue_nadia_overheard",
            ],
        },
    ).json()
    assert r["killer_correct"] is True
    assert r["motive_correct"] and r["method_correct"] and r["opportunity_correct"]
    assert r["score"] >= 90
    assert r["evidence_score"] >= 0.8


def test_correct_killer_weak_evidence_scores_lower():
    # Correct killer, but no answers and no cited evidence.
    strong = client.post(
        "/api/accuse",
        json={
            "accused_agent_id": "agent_clara",
            "motive_answer": STRONG_MOTIVE,
            "method_answer": STRONG_METHOD,
            "opportunity_answer": STRONG_OPPORTUNITY,
            "supporting_clue_ids": [],
        },
    ).json()

    client.post("/api/session/reset")
    weak = client.post(
        "/api/accuse",
        json={
            "accused_agent_id": "agent_clara",
            "motive_answer": "",
            "method_answer": "",
            "opportunity_answer": "",
            "supporting_clue_ids": [],
        },
    ).json()
    assert weak["killer_correct"] is True
    assert weak["score"] < strong["score"]


def test_wrong_suspect_scores_low():
    _discover(None)
    r = client.post(
        "/api/accuse",
        json={
            "accused_agent_id": "agent_owen",
            "motive_answer": "Owen owed Marcus money and killed him to avoid exposure.",
            "method_answer": "He hit him.",
            "opportunity_answer": "He was angry that morning.",
            "supporting_clue_ids": ["clue_owen_argument"],
        },
    ).json()
    assert r["killer_correct"] is False
    assert r["score"] < 50
    assert any("points elsewhere" in fa for fa in r["false_assumptions"])


def test_undiscovered_clue_cannot_support_accusation():
    # Nothing discovered; cite a real clue that was never found.
    r = client.post(
        "/api/accuse",
        json={
            "accused_agent_id": "agent_clara",
            "motive_answer": STRONG_MOTIVE,
            "method_answer": STRONG_METHOD,
            "opportunity_answer": STRONG_OPPORTUNITY,
            "supporting_clue_ids": ["clue_ledger_page"],
        },
    ).json()
    assert any("never discovered" in fa for fa in r["false_assumptions"])
    assert r["evidence_score"] == 0.0


def test_reveal_sealed_before_accusation():
    r = client.get("/api/reveal")
    assert r.status_code == 403


def test_reveal_available_after_accusation():
    client.post(
        "/api/accuse",
        json={"accused_agent_id": "agent_clara", "motive_answer": STRONG_MOTIVE},
    )
    r = client.get("/api/reveal")
    assert r.status_code == 200
    body = r.json()
    assert body["true_killer_name"] == "Clara Wells"
    assert body["true_timeline"], "reveal includes the true timeline"
    # The hidden murder event surfaces only in the post-accusation reveal.
    assert any("till weight" in e["description"].lower() for e in body["true_timeline"])


def test_reveal_includes_red_herring_explanations():
    r = client.post(
        "/api/accuse",
        json={"accused_agent_id": "agent_clara", "motive_answer": STRONG_MOTIVE},
    ).json()
    herrings = {h["agent_id"] for h in r["red_herring_explanations"]}
    assert "agent_owen" in herrings and "agent_isabella" in herrings
    for h in r["red_herring_explanations"]:
        assert h["looked_suspicious_because"] and h["actually_innocent_because"]


def test_api_does_not_leak_killer_before_accusation():
    # Sweep every pre-accusation player-facing endpoint for the killer's identity.
    endpoints = ["/api/case", "/api/agents", "/api/board", "/api/clues", "/api/status"]
    for ep in endpoints:
        blob = str(client.get(ep).json()).lower()
        assert "killer_id" not in blob
        assert "true_killer" not in blob
    # The status endpoint should report that no accusation has been made.
    assert client.get("/api/status").json()["accused"] is False
