"""Tests for the visual map replay endpoint.

The map layer is a projection of the event log through the existing
visibility rules — these tests pin down that it can never become a truth
leak before accusation.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAFE_AMBIGUOUS_TYPES = {"sound_marker", "body_discovery", "unknown_figure", "hidden_activity"}


def _replay(**params):
    resp = client.get("/api/map/replay", params=params)
    assert resp.status_code == 200
    return resp.json()


def test_replay_shape_and_visual_metadata():
    data = _replay()
    assert data["mode"] == "player"
    assert data["map"]["asset"] == "town_canonical_v1"
    assert data["map"]["definition_id"] == "town_canonical_v1"
    assert data["map"]["image_tiles"]
    assert data["visual"]["mode"] == "canonical_overworld"
    assert data["map"]["width"] > 0 and data["map"]["height"] > 0
    assert data["time_range"]["start"] < data["time_range"]["end"]
    # Every location has a usable map position (authored or fallback).
    assert data["locations"]
    for loc in data["locations"]:
        assert loc["map_position"] is not None
        assert 0 <= loc["map_position"]["x"] <= data["map"]["width"]
        assert 0 <= loc["map_position"]["y"] <= data["map"]["height"]
    # Every agent has a sprite avatar but keeps their canonical name.
    for agent in data["agents"]:
        assert agent["sprite_asset"], agent["agent_id"]
        assert agent["full_name"]


def test_replay_does_not_expose_hidden_events():
    data = _replay()
    for e in data["events"]:
        assert e["visibility"] != "hidden"
        assert e["event_type"] != "murder"
        assert e["visual_event_type"] != "clue_marker" or e["visibility"] == "public"
    # The known hidden events of case_001 must be absent.
    ids = {e["event_id"] for e in data["events"]}
    assert "ev_0756_murder" not in ids
    assert "ev_0753_clara_rear_door" not in ids
    assert "ev_0802_weight_hidden" not in ids


def test_replay_never_names_the_killer_in_ambiguous_events():
    data = _replay()
    for e in data["events"]:
        if e["visibility"] != "public":
            # Ambiguous/partial events carry no agent identities and only
            # ambiguity-preserving marker types.
            assert e["agent_ids"] == []
            assert e["visual_event_type"] in SAFE_AMBIGUOUS_TYPES
    # The killer's ambiguous movements must not reveal her identity.
    for event_id in ("ev_0747_blue_coat", "ev_0758_rear_door"):
        e = next(ev for ev in data["events"] if ev["event_id"] == event_id)
        assert "Clara" not in e["description"]
        assert e["agent_ids"] == []


def test_replay_does_not_leak_truth_fields():
    data = _replay()
    banned_keys = {"truth_description", "linked_clue_ids", "object_ids", "visible_to_agent_ids", "audible_to_agent_ids"}
    for e in data["events"]:
        assert not banned_keys & set(e.keys())
    text = str(data)
    assert "killer" not in text.lower()
    assert "truth_description" not in text


def test_replay_respects_time_and_location_filters():
    data = _replay(start="07:40", end="08:00", location_id="loc_rear_alley")
    assert data["events"], "expected visible alley events in the murder window"
    for e in data["events"]:
        assert e["location_id"] == "loc_rear_alley"
        assert "07:40" <= e["time"] <= "08:00"


def test_replay_agent_filter_does_not_deanonymise_partials():
    # Following Clara must not surface the ambiguous blue-coat sighting.
    data = _replay(agent_id="agent_clara")
    for e in data["events"]:
        assert "agent_clara" in e["agent_ids"]
        assert e["visibility"] == "public"


def test_truth_replay_blocked_before_accusation():
    resp = client.get("/api/map/replay", params={"mode": "truth"})
    assert resp.status_code == 403


def test_truth_replay_available_after_accusation():
    accuse = client.post(
        "/api/accuse",
        json={
            "accused_agent_id": "agent_clara",
            "motive_answer": "blackmail over the ledger",
            "method_answer": "till weight",
            "opportunity_answer": "rear door of the storage room",
            "supporting_note_ids": [],
            "supporting_clue_ids": [],
        },
    )
    assert accuse.status_code == 200
    data = _replay(mode="truth")
    assert data["mode"] == "truth"
    ids = {e["event_id"] for e in data["events"]}
    assert "ev_0756_murder" in ids
    murder = next(e for e in data["events"] if e["event_id"] == "ev_0756_murder")
    assert murder["was_hidden"] is True
    assert "agent_clara" in murder["agent_ids"]


def test_generated_case_produces_map_replay():
    resp = client.post(
        "/api/cases/generate",
        json={
            "case_type": "debt",
            "difficulty": "standard",
            "seed": 4242,
            "activate": True,
            "mode": "deterministic",
            "fallback_allowed": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["validation"]["valid"]
    data = _replay()
    assert data["case_id"] == resp.json()["case_id"]
    for loc in data["locations"]:
        assert loc["map_position"] is not None
    for agent in data["agents"]:
        assert agent["sprite_asset"]
    for e in data["events"]:
        assert e["visibility"] != "hidden"
        assert e["event_type"] != "murder"
        if e["visibility"] != "public":
            assert e["agent_ids"] == []
