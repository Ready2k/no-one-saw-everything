"""Challenge engine tests (Phase 5)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_session():
    client.post("/api/session/reset")
    yield


def _clara_fountain_claim():
    """Make Clara assert her false fountain alibi, returning the claim id."""
    r = client.post(
        "/api/interview/ask", json={"agent_id": "agent_clara", "question_type": "alibi"}
    ).json()
    assert r["new_claims"], "Clara should produce an alibi claim"
    return r["new_claims"][0]["claim_id"]


def _discover_ben_sighting():
    client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_ben", "question_type": "timeline", "time_reference": "07:47"},
    )


def test_challenge_needs_discovered_evidence():
    claim_id = _clara_fountain_claim()
    # clue_ben_sighting exists but has not been discovered yet.
    r = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": claim_id,
            "evidence_clue_ids": ["clue_ben_sighting"],
        },
    )
    assert r.status_code == 400
    assert "discovered" in r.json()["detail"].lower()


def test_clara_fountain_alibi_partial_admission():
    claim_id = _clara_fountain_claim()
    _discover_ben_sighting()
    r = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": claim_id,
            "evidence_clue_ids": ["clue_ben_sighting"],
            "player_statement": "Ben saw you near the rear alley at 07:47.",
        },
    ).json()
    assert r["outcome"] == "partial_admission"
    assert r["pressure_delta"] > 0
    assert r["new_claims"], "a reframed claim should be produced"
    # Clara does NOT confess to murder.
    assert "kill" not in r["response_text"].lower()
    assert r["created_note_ids"], "a contradiction note should be auto-created"


def test_challenge_updates_claim_status():
    claim_id = _clara_fountain_claim()
    _discover_ben_sighting()
    client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": claim_id,
            "evidence_clue_ids": ["clue_ben_sighting"],
        },
    )
    claims = client.get("/api/claims", params={"agent_id": "agent_clara"}).json()
    fountain = next(c for c in claims if c["claim_id"] == claim_id)
    assert fountain["player_known_status"] == "reframed"


def test_challenge_creates_contradiction_note():
    claim_id = _clara_fountain_claim()
    _discover_ben_sighting()
    before = len(client.get("/api/notes").json())
    client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": claim_id,
            "evidence_clue_ids": ["clue_ben_sighting"],
        },
    )
    notes = client.get("/api/notes").json()
    assert len(notes) == before + 1
    board = client.get("/api/board").json()
    assert board["contradiction_notes"], "contradiction should appear on the board"


def test_reveal_innocent_secret_via_challenge():
    # Priya first claims she was alone in the stockroom.
    r = client.post(
        "/api/interview/ask", json={"agent_id": "agent_priya", "question_type": "alibi"}
    ).json()
    priya_claim = r["new_claims"][0]["claim_id"]
    # The secret path is gated behind Ben's sighting.
    _discover_ben_sighting()
    res = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_priya",
            "challenged_claim_id": priya_claim,
            "evidence_clue_ids": ["clue_ben_sighting"],
        },
    ).json()
    assert res["outcome"] == "reveal_innocent_secret"
    assert any(c["clue_id"] == "clue_ben_priya_meeting" for c in res["revealed_clues"])
    assert res["revealed_memories"], "the innocent-secret memory should surface"
    # Priya's alibi claim is now resolved (explained, not guilty).
    claims = client.get("/api/claims", params={"agent_id": "agent_priya"}).json()
    assert any(c["claim_id"] == priya_claim and c["player_known_status"] == "resolved" for c in claims)


def test_challenge_response_does_not_leak_hidden_truth():
    claim_id = _clara_fountain_claim()
    _discover_ben_sighting()
    r = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": claim_id,
            "evidence_clue_ids": ["clue_ben_sighting"],
        },
    ).json()
    # No lie flags / truthfulness / role leak in the projected claims.
    for claim in r["new_claims"]:
        assert "truthfulness" not in claim
    blob = str(r).lower()
    assert "killer" not in blob
    assert "murderer" not in blob


def test_duplicate_challenge_is_idempotent():
    claim_id = _clara_fountain_claim()
    _discover_ben_sighting()
    payload = {
        "target_agent_id": "agent_clara",
        "challenged_claim_id": claim_id,
        "evidence_clue_ids": ["clue_ben_sighting"],
    }
    first = client.post("/api/challenge", json=payload).json()
    notes_after_first = len(client.get("/api/notes").json())
    second = client.post("/api/challenge", json=payload).json()
    assert second["duplicate"] is True
    assert second["challenge_id"] == first["challenge_id"]
    # No duplicate note is created on the repeat challenge.
    assert len(client.get("/api/notes").json()) == notes_after_first


def test_challenge_nonexistent_claim_404():
    r = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": "claim_does_not_exist",
            "evidence_clue_ids": ["clue_ledger_page"],
        },
    )
    assert r.status_code == 404


def test_cannot_challenge_victim():
    # Even with a fabricated claim id, victim is rejected before claim lookup.
    r = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_marcus",
            "challenged_claim_id": "claim_whatever",
            "evidence_clue_ids": ["clue_ledger_page"],
        },
    )
    assert r.status_code == 400


def test_unrelated_evidence_handled_gracefully():
    claim_id = _clara_fountain_claim()
    # Owen's public argument clue is unrelated to Clara's fountain alibi.
    client.post("/api/events/ev_0705_owen_argument/pin")  # discover via observation
    r = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": claim_id,
            "evidence_clue_ids": ["clue_owen_argument"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "deny"
    # No scripted state change: claim stays 'claimed'.
    claims = client.get("/api/claims", params={"agent_id": "agent_clara"}).json()
    fountain = next(c for c in claims if c["claim_id"] == claim_id)
    assert fountain["player_known_status"] == "claimed"


def test_challenge_suggestions_appear_only_with_evidence():
    claim_id = _clara_fountain_claim()
    # No evidence discovered yet -> no suggestion for the fountain claim.
    sugg = client.get("/api/challenge/suggestions").json()
    assert not any(s["challenged_claim_id"] == claim_id for s in sugg)
    _discover_ben_sighting()
    sugg = client.get("/api/challenge/suggestions").json()
    assert any(
        s["challenged_claim_id"] == claim_id and s["evidence_clue_id"] == "clue_ben_sighting"
        for s in sugg
    )
