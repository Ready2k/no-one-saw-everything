"""API behaviour tests: visibility, gated discovery, grounded interviews."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_session():
    client.post("/api/session/reset")
    yield


def test_case_overview():
    r = client.get("/api/case").json()
    assert r["title"] == "The Storage Room Murder"
    assert r["victim"]["full_name"] == "Marcus Bell"
    assert r["discovery_time"] == "08:12"


def test_events_hide_murder_and_deanonymise_partials():
    events = client.get("/api/events").json()
    ids = {e["event_id"] for e in events}
    assert "ev_0756_murder" not in ids
    assert "ev_0753_clara_rear_door" not in ids
    assert "ev_0802_weight_hidden" not in ids
    blue_coat = next(e for e in events if e["event_id"] == "ev_0747_blue_coat")
    assert blue_coat["agent_ids"] == []  # identity obscured
    assert "Clara" not in blue_coat["description"]


def test_follow_agent_does_not_leak_partial_events():
    events = client.get("/api/events", params={"agent_id": "agent_clara"}).json()
    ids = {e["event_id"] for e in events}
    assert "ev_0747_blue_coat" not in ids  # would deanonymise the figure
    assert "ev_0744_clara_exits" in ids  # public exit is fine


def test_pin_event_discovers_observation_clue():
    r = client.post("/api/events/ev_0756_sound/pin").json()
    assert any(c["clue_id"] == "clue_storage_sound" for c in r["new_clues"])
    clues = client.get("/api/clues").json()
    assert any(c["clue_id"] == "clue_storage_sound" for c in clues)


def test_inspect_kitchen_gates_till_weight_behind_missing_clue():
    r = client.post("/api/inspect", json={"location_id": "loc_cafe_kitchen"}).json()
    found = {c["clue_id"] for c in r["new_clues"]}
    assert "clue_blue_coat_damp" in found
    assert "clue_till_weight_found" not in found
    assert r["hint"] is not None

    # Discover the till weight is missing, then re-inspect.
    client.post("/api/inspect", json={"location_id": "loc_hobbs_cafe"})
    r2 = client.post("/api/inspect", json={"location_id": "loc_cafe_kitchen"}).json()
    assert any(c["clue_id"] == "clue_till_weight_found" for c in r2["new_clues"])


def test_clara_alibi_is_a_lie_but_lie_flag_not_leaked():
    r = client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_clara", "question_type": "alibi"},
    ).json()
    assert "fountain" in r["answer_text"].lower()
    assert r["new_claims"], "alibi should generate a claim"
    claim = r["new_claims"][0]
    assert "truthfulness" not in claim
    assert claim["player_known_status"] == "claimed"


def test_ben_timeline_reveals_sighting_and_sound():
    r = client.post(
        "/api/interview/ask",
        json={
            "agent_id": "agent_ben",
            "question_type": "timeline",
            "time_reference": "07:47",
        },
    ).json()
    revealed = {c["clue_id"] for c in r["revealed_clues"]}
    assert {"clue_ben_sighting", "clue_storage_sound"} <= revealed


def test_priya_confession_gated_on_ben_sighting():
    # Before Ben's sighting is known, Priya sticks to her story.
    r = client.post(
        "/api/interview/ask",
        json={
            "agent_id": "agent_priya",
            "question_type": "location",
            "topic_location_id": "loc_rear_alley",
        },
    ).json()
    assert not r["revealed_clues"]

    # Learn Ben's sighting, then ask again.
    client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_ben", "question_type": "timeline", "time_reference": "07:47"},
    )
    r2 = client.post(
        "/api/interview/ask",
        json={
            "agent_id": "agent_priya",
            "question_type": "location",
            "topic_location_id": "loc_rear_alley",
        },
    ).json()
    assert any(c["clue_id"] == "clue_ben_priya_meeting" for c in r2["revealed_clues"])


def test_cannot_ask_about_undiscovered_evidence():
    r = client.post(
        "/api/interview/ask",
        json={
            "agent_id": "agent_clara",
            "question_type": "evidence",
            "topic_clue_id": "clue_ledger_page",
        },
    )
    assert r.status_code == 400


def test_victim_cannot_be_interviewed():
    r = client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_marcus", "question_type": "alibi"},
    )
    assert r.status_code == 400


def test_notes_crud_and_board():
    note = client.post(
        "/api/notes",
        json={
            "note_type": "contradiction",
            "title": "Clara's fountain alibi conflicts with Ben's sighting",
            "body": "Clara claims fountain at 07:50; blue coat seen entering alley 07:47.",
            "linked_agent_ids": ["agent_clara", "agent_ben"],
            "pinned_to_agent_id": "agent_clara",
        },
    ).json()
    assert note["note_id"]

    board = client.get("/api/board").json()
    clara = next(s for s in board["suspects"] if s["agent"]["agent_id"] == "agent_clara")
    assert any(n["note_id"] == note["note_id"] for n in clara["pinned_notes"])
    assert board["contradiction_notes"]

    client.post("/api/suspicion", json={"agent_id": "agent_clara", "level": "prime_suspect"})
    board = client.get("/api/board").json()
    clara = next(s for s in board["suspects"] if s["agent"]["agent_id"] == "agent_clara")
    assert clara["suspicion"] == "prime_suspect"

    r = client.delete(f"/api/notes/{note['note_id']}")
    assert r.json()["deleted"]
