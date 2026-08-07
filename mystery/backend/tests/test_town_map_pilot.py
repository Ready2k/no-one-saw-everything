import json
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from app.case_store import get_case
from app.main import app
from app.town_map import (
    CANONICAL_ADJACENCY,
    CANONICAL_MAP,
    map_config,
    map_definition_for_case,
    map_payload,
)

client = TestClient(app)

AUTHORED_CASE_IDS = [f"case_{i:03d}" for i in range(1, 8)]

# backend/tests -> backend -> mystery, then into the frontend the API serves art from.
PUBLIC_ART_ROOT = Path(__file__).resolve().parent.parent.parent / "frontend" / "public"


def test_case_004_map_payload_hides_objects_until_their_clue_is_found():
    """The visual layer must not become a second way to read the case file.

    (This used to also assert mode/definition_id. Those moved to
    `test_all_authored_cases_use_their_configured_visual_contract`, which
    covers every case rather than this one — leaving this test to guard the
    one thing only it checks.)
    """
    payload = map_payload(get_case("case_004"), set())

    assert payload["visible_location_ids"]
    assert payload["objects"]
    assert all(obj["state"] == "visible" for obj in payload["object_visuals"])
    assert all(obj["marker_state"] == "suppressed" for obj in payload["object_visuals"])
    assert all(obj["safe_to_render"] is False for obj in payload["object_visuals"])

    discovered = map_payload(get_case("case_004"), {"clue_fountain_stone"})
    fountain = next(o for o in discovered["object_visuals"] if o["object_id"] == "obj_fountain_stone")
    assert fountain["state"] == "discovered"
    assert fountain["marker_state"] == "active"
    assert fountain["safe_to_render"] is True
    assert fountain["overlay_ids"] == ["overlay_missing_coping"]


def test_case_001_body_pocket_clues_are_anchored_in_storage_room():
    payload = map_payload(get_case("case_001"), {
        "clue_ledger_page",
        "clue_isabella_note",
        "clue_partnership_letter",
    })
    objects = {obj["object_id"]: obj for obj in payload["object_visuals"]}

    for object_id in ("obj_ledger_page", "obj_isabella_note", "obj_partnership_letter"):
        assert objects[object_id]["location_id"] == "loc_cafe_storage"
        assert objects[object_id]["safe_to_render"] is True


def test_object_marker_only_activates_from_clue_at_same_location():
    payload = map_payload(get_case("case_001"), {"clue_till_weight_missing"})
    till_weight = next(obj for obj in payload["object_visuals"] if obj["object_id"] == "obj_till_weight")

    assert till_weight["location_id"] == "loc_cafe_kitchen"
    assert till_weight["marker_state"] == "suppressed"
    assert till_weight["safe_to_render"] is False


def test_case_004_locations_include_function_tags_for_migration():
    payload = map_payload(get_case("case_004"), set())
    locations = payload["canonical_locations"]

    assert locations["loc_pub"]["function_tag"] == "pub"
    assert locations["loc_pub"]["building_role"] == "business"
    assert locations["loc_clinic"]["function_tag"] == "clinic"
    assert locations["loc_clinic"]["building_role"] == "public_service"
    assert "case_004" in locations["loc_ben_flat"]["case_ids"]




@pytest.mark.parametrize("case_id", AUTHORED_CASE_IDS)
def test_every_place_has_search_art_that_exists_on_disk(case_id):
    """Every location the player can open in Places must have art, and that
    art must actually be there.

    Most artwork assertions should not pin exact filenames: checking that the
    projected asset exists is more robust to art passes and catches the blank
    panel that actually hurts a player.
    """
    from app.projections import project_map_location

    case = get_case(case_id)
    for location in case.locations:
        illustration = project_map_location(location, case_id).get("illustration")
        assert illustration, f"{case_id}/{location.location_id} has no search art"
        asset = PUBLIC_ART_ROOT / illustration.lstrip("/")
        assert asset.is_file(), f"{case_id}/{location.location_id} -> missing {illustration}"


def test_recurring_square_art_preserves_one_village_across_case_times():
    """Shared geometry may change time and camera, never physical identity."""
    from app.place_library import location_search_illustration

    expected = {
        ("case_001", "loc_village_square"): "case_005/village_square_dawn_hd.avif",
        ("case_001", "loc_fountain"): "case_001/fountain_dawn_investigation_v5.avif",
        ("case_002", "loc_village_square"): "case_002/village_square_sunset_investigation_v1.avif",
        ("case_002", "loc_fountain"): "case_002/fountain_sunset_investigation_v1.avif",
        ("case_003", "loc_village_square"): "case_003/village_square_afternoon_investigation_v2.avif",
        ("case_004", "loc_village_square"): "case_004/village_square_midnight_investigation_v2.avif",
        ("case_004", "loc_fountain"): "case_004/fountain_midnight_investigation_v2.avif",
        ("case_004", "loc_fishery"): "case_004/fishery_midnight_investigation_v2.avif",
        ("case_004", "loc_lake"): "case_004/lovers_lake_midnight_investigation_v2.avif",
        ("case_004", "loc_woodland"): "case_004/whispering_woodland_midnight_investigation_v2.avif",
        ("case_004", "loc_meadow"): "case_004/green_meadow_midnight_investigation_v2.avif",
    }
    for (case_id, location_id), suffix in expected.items():
        assert location_search_illustration(location_id, case_id).endswith(suffix)


def test_rear_alley_and_owen_yard_never_fall_back_to_overhead_art():
    """Recurring searchable exteriors use eye-level 2.5D scenes in every case."""
    from app.place_library import location_search_illustration

    for case_id in AUTHORED_CASE_IDS:
        expected_alley = {
            "case_002": "case_002/rear_alley_bookshop_sunset_investigation_v1.avif",
            "case_005": "case_005/rear_alley_after_fire_investigation_v2.avif",
            "case_007": "case_007/rear_alley_fair_evening_v1.avif",
            "case_010": "case_010/rear_alley_fire_hd.avif",
        }.get(case_id, "case_001/rear_alley_investigation_v2.avif")
        assert location_search_illustration("loc_rear_alley", case_id).endswith(expected_alley)
        expected_yard = {
            "case_002": "case_002/owen_house_yard_sunset_investigation_v1.avif",
            "case_003": "case_002/owen_house_yard_sunset_investigation_v1.avif",
            "case_004": "case_004/owen_house_yard_midnight_investigation_v1.avif",
            "case_005": "case_005/owen_yard_dawn_hd.avif",
            "case_007": "case_004/owen_house_yard_midnight_investigation_v1.avif",
            "case_010": "case_010/owen_yard_dawn_hd.avif",
        }.get(case_id, "case_001/owen_house_yard_investigation_v2.avif")
        assert location_search_illustration("loc_owen_house", case_id).endswith(expected_yard)


@pytest.mark.parametrize("case_id", AUTHORED_CASE_IDS)
def test_every_inspect_clue_is_reachable_through_the_magnifying_glass(case_id):
    """The fairness invariant the coordinate tests were reaching for.

    Two tests used to pin 16 exact (x, y, radius) tuples across cases 002 and
    004. Hotspots are positioned against the artwork, so they *must* move when
    the art is regenerated — pinning them guarantees a false failure every art
    pass (case_002's had already gone red) while guarding nothing real:
    unauthored coordinates are filled in procedurally (`main.py`'s md5
    placement), so a missing coordinate was never a discoverability problem in
    the first place.

    What matters is that every inspect clue can actually be found once its
    prerequisites are met. That is asserted here for all seven cases, which is
    far more coverage than the two the pinned tests bought.
    """
    from app.session import get_session

    client.post("/api/cases/activate", json={"case_id": case_id})
    case = get_case(case_id)
    by_id = {clue.clue_id: clue for clue in case.clues}

    def prerequisite_closure(clue_id, seen=None):
        seen = set() if seen is None else seen
        for prereq in by_id[clue_id].discoverability.required_prior_clue_ids:
            if prereq not in seen:
                seen.add(prereq)
                prerequisite_closure(prereq, seen)
        return seen

    checked = 0
    for clue in case.clues:
        d = clue.discoverability
        # Body-pocket clues belong to the autopsy flow, not the room search.
        if d.method != "inspect" or "examine_body" in (d.reveal_on or []):
            continue
        client.post("/api/session/reset")
        # Seeded directly rather than through /api/discover_clue: a prerequisite
        # may itself be an *interview* clue, which that endpoint will not grant.
        get_session(case_id).discovered_clue_ids |= prerequisite_closure(clue.clue_id)

        response = client.post("/api/inspect", json={"location_id": d.location_id})
        assert response.status_code == 200, (case_id, clue.clue_id)
        hotspots = {h["clue_id"]: h for h in response.json()["hidden_clues"]}
        assert clue.clue_id in hotspots, (
            f"{case_id}/{clue.clue_id} never appears when searching {d.location_id}"
        )
        spot = hotspots[clue.clue_id]
        assert 0 <= spot["x"] <= 100 and 0 <= spot["y"] <= 100, (clue.clue_id, spot)
        assert spot["radius"] > 0, (clue.clue_id, spot)
        checked += 1

    assert checked, f"{case_id} has no inspect clues to check"


def test_scenario_expansion_locations_are_ready_for_generated_map_replay():
    """New reusable places use the seamless canonical world and HD scene art."""
    from app.place_library import location_art_asset, location_search_illustration
    from app.town_map import canonical_location_visuals

    church_position, church_bounds, church_layer = canonical_location_visuals("loc_st_alder_church")
    farm_position, farm_bounds, farm_layer = canonical_location_visuals("loc_willow_farmhouse")

    assert church_position and church_bounds and church_layer == "exterior"
    assert farm_position and farm_bounds and farm_layer == "exterior"
    assert church_bounds["x"] == 67 * 32
    assert church_bounds["y"] == 36 * 32
    assert farm_bounds["y"] == 108 * 32
    assert "loc_st_alder_church" in CANONICAL_ADJACENCY["loc_village_square"]
    assert location_art_asset("loc_st_alder_church", "internal").endswith("st_alder_church_interior_map_hd.avif")
    assert location_art_asset("loc_willow_farmhouse").endswith("willow_farmhouse_exterior_map_stamp_hd.avif")
    assert location_search_illustration("loc_st_alder_church").endswith("st_alder_church_search_hd.avif")
    assert location_search_illustration("loc_willow_farmhouse").endswith("willow_farmhouse_search_hd.avif")





def test_case_001_uses_the_canonical_village():
    payload = map_payload(get_case("case_001"), set())

    assert payload["mode"] == "canonical_overworld"
    assert payload["definition_id"] == "town_canonical_v1"
    assert map_config("case_001")["map"] is CANONICAL_MAP
    assert set(payload["canonical_locations"]) == set(payload["visible_location_ids"])


def test_case_002_exposes_exactly_its_authored_location_roster():
    """Pins case_002's visible set by name, so a location quietly appearing on
    or vanishing from the map is caught. The mode/definition_id it used to
    assert (`canonical_overworld`/`town_canonical_v1`) were superseded by the
    per-case art maps; case_001's equivalent test was updated at the time and
    this one was missed."""
    visible_locations = {
        "loc_village_square", "loc_fountain", "loc_elias_bench", "loc_bookshop",
        "loc_bookshop_back", "loc_rear_alley", "loc_hobbs_cafe",
        "loc_clinic", "loc_owen_house", "loc_priya_flat",
    }
    payload = map_payload(get_case("case_002"), set())

    assert payload["mode"] == "canonical_overworld"
    assert payload["definition_id"] == "town_canonical_v1"
    assert set(payload["visible_location_ids"]) == visible_locations
    assert set(payload["canonical_locations"]) == visible_locations



def test_all_authored_cases_use_their_configured_visual_contract():
    expected_contracts = {
        "case_001": ("canonical_overworld", "town_canonical_v1"),
        "case_002": ("canonical_overworld", "town_canonical_v1"),
        "case_003": ("canonical_overworld", "town_canonical_v1"),
        "case_004": ("canonical_overworld", "town_canonical_v1"),
        "case_005": ("canonical_overworld", "town_canonical_v1"),
        "case_006": ("canonical_overworld", "town_canonical_v1"),
        "case_007": ("canonical_overworld", "town_canonical_v1"),
        "case_010": ("canonical_overworld", "town_canonical_v1"),
    }
    for case_id, (expected_mode, expected_definition) in expected_contracts.items():
        case = get_case(case_id)
        payload = map_payload(case, set())

        assert payload["mode"] == expected_mode
        assert payload["definition_id"] == expected_definition
        assert set(payload["visible_location_ids"]) == {loc.location_id for loc in case.locations}
        assert set(payload["canonical_locations"]) == set(payload["visible_location_ids"])


def test_all_authored_cases_share_the_complete_cutaway_mosaic():
    for case_id in (*AUTHORED_CASE_IDS, "case_010"):
        definition = map_definition_for_case(case_id)
        exterior = definition["image_tiles"]["urls"]
        cutaway = definition["zoom_image_tiles"]["urls"]
        assert definition["zoom_image_tiles"]["threshold"] == 3.2
        assert len(exterior) == len(cutaway) == 3
        assert all(len(row) == 3 for row in cutaway)
        assert all(
            exterior[row][col] != cutaway[row][col]
            for row in range(3)
            for col in range(3)
        )
        assert definition["lighting_overlay"] == "runtime_lightingTint"


def test_cutaway_manifest_covers_every_declared_interior_location():
    manifest_path = (
        PUBLIC_ART_ROOT
        / "art/town/tiles_3x3_hd/current_village_v3_neutral/cutaway_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text())
    expected = {
        "loc_st_alder_church", "loc_pub", "loc_marcus_house", "loc_marcus_study",
        "loc_bookshop", "loc_bookshop_back", "loc_solicitors_office", "loc_clinic",
        "loc_clinic_dispensary", "loc_hobbs_cafe", "loc_cafe_kitchen",
        "loc_cafe_storage", "loc_clara_flat", "loc_priya_flat", "loc_owen_house",
        "loc_nadia_flat", "loc_ruth_cottage", "loc_willow_farmhouse",
    }
    assert set(manifest["coverage"]) == expected
    assert manifest["style"] == "lifelike_high_resolution_birdseye"


def test_all_authored_case_object_visuals_stay_in_visible_locations():
    for case_id in ("case_001", "case_002", "case_003", "case_004", "case_005", "case_006"):
        case = get_case(case_id)
        discovered = {clue.clue_id for clue in case.clues}
        payload = map_payload(case, discovered)
        visible_locations = set(payload["visible_location_ids"])

        assert payload["object_visuals"], case_id
        for obj in payload["object_visuals"]:
            assert obj["location_id"] in visible_locations
