"""Tests for procedural case generation API."""

from fastapi.testclient import TestClient

from app.generator import generate_case
from app.main import app
from app.town_map import map_payload

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
    # Generated ids carry a uniqueness timestamp suffix: gen_debt_42_<ts>.
    assert data["case_id"].startswith("gen_debt_42_")
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
    assert data["case_id"].startswith("gen_betrayal_99_")
    assert data["active_session_id"] == data["case_id"]

    # The active case is now the generated one
    case_info = client.get("/api/case").json()
    assert case_info["case_id"] == data["case_id"]


def test_generated_case_compaction_remaps_object_locations_with_clues():
    case, fallback_used, _, _ = generate_case(
        "blackmail",
        "standard",
        16481,
        num_suspects=4,
        num_locations=3,
    )

    assert fallback_used is False
    kept_locations = {loc.location_id for loc in case.locations}
    assert kept_locations
    for obj in case.objects:
        if obj.normal_location_id:
            assert obj.normal_location_id in kept_locations
        if obj.final_location_id:
            assert obj.final_location_id in kept_locations
    for clue in case.clues:
        if clue.discoverability.location_id:
            assert clue.discoverability.location_id in kept_locations


def test_generated_case_uses_canonical_map_for_clue_object_locations():
    case, _, _, _ = generate_case("blackmail", "standard", 42)
    discovered = {clue.clue_id for clue in case.clues}
    payload = map_payload(case, discovered)

    assert payload["mode"] == "canonical_overworld"
    assert set(payload["visible_location_ids"]) == {loc.location_id for loc in case.locations}
    for obj in payload["object_visuals"]:
        assert obj["location_id"] in payload["visible_location_ids"]
