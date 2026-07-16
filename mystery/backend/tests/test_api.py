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
    from helpers import inspect_and_discover

    r = client.post("/api/inspect", json={"location_id": "loc_cafe_kitchen"}).json()
    hotspots = {c["clue_id"] for c in r["hidden_clues"]}
    assert "clue_blue_coat_damp" in hotspots
    assert "clue_till_weight_found" not in hotspots
    assert r["hint"] is not None

    # Discover the till weight is missing, then re-inspect.
    inspect_and_discover(client, "loc_hobbs_cafe")
    r2 = client.post("/api/inspect", json={"location_id": "loc_cafe_kitchen"}).json()
    assert any(c["clue_id"] == "clue_till_weight_found" for c in r2["hidden_clues"])


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


def test_ben_timeline_splits_sighting_and_sound_by_when_asked():
    # These used to spill from a single question — two of five key clues in one breath. They are
    # now separate discoveries: the coat when you ask about ~07:47, the thud about ~07:56.
    coat = client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_ben", "question_type": "timeline", "time_reference": "07:47"},
    ).json()
    coat_clues = {c["clue_id"] for c in coat["revealed_clues"]}
    assert "clue_ben_sighting" in coat_clues
    assert "clue_storage_sound" not in coat_clues

    thud = client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_ben", "question_type": "timeline", "time_reference": "07:56"},
    ).json()
    thud_clues = {c["clue_id"] for c in thud["revealed_clues"]}
    assert "clue_storage_sound" in thud_clues


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


def test_victim_cannot_be_interviewed_but_can_be_examined(reset_app_state):
    # Examination returns cause of death but no longer automatically reveals clues
    r = client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_marcus", "question_type": "alibi"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "Examine body" in data["question_text"]
    assert "Cause of death appears to be" in data["answer_text"]
    assert "Please use the dedicated visual autopsy view" in data["answer_text"]
    
    # Check if there are clues revealed on the first examination
    first_clues = data.get("revealed_clues", [])
    assert len(first_clues) == 0

def test_examine_body_endpoint(reset_app_state):
    # Examine the body
    r = client.get("/api/examine_body/agent_marcus")
    assert r.status_code == 200
    data = r.json()
    
    assert data["location"]["name"] == "Victim's Body"
    assert len(data["hidden_clues"]) > 0
    assert "Cause of death appears to be" in data["location"]["description"]
    
    # Try examining a living agent
    r_bad = client.get("/api/examine_body/agent_clara")
    assert r_bad.status_code == 400
    assert "Only the victim can be examined this way" in r_bad.text

def test_body_examination_metadata_override(reset_app_state):
    from app.main import session, case_data
    from app.models import Clue, Discoverability
    
    sess = session()
    case = case_data()
    
    clue = Clue(
        clue_id="clue_mock_not_body",
        title="Mock not body",
        clue_type="physical",
        description="A clue in the storage room on Marcus's body but metadata overrides it.",
        discoverability=Discoverability(
            method="inspect",
            location_id=case.case.discovery_location_id,
            reveal_on=["some_other_trigger"]
        ),
        linked_agent_ids=[case.case.victim_id]
    )
    case.clues.append(clue)
    
    # Should not appear in body examination hidden clues
    r = client.get("/api/examine_body/agent_marcus")
    assert r.status_code == 200
    data = r.json()
    hidden_ids = [c["clue_id"] for c in data["hidden_clues"]]
    assert "clue_mock_not_body" not in hidden_ids
    
    # Now set it to examine_body
    clue.discoverability.reveal_on = ["examine_body"]
    r2 = client.get("/api/examine_body/agent_marcus")
    assert r2.status_code == 200
    data2 = r2.json()
    hidden_ids2 = [c["clue_id"] for c in data2["hidden_clues"]]
    assert "clue_mock_not_body" in hidden_ids2




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
