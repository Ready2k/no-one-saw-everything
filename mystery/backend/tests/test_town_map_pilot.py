from types import SimpleNamespace

from app.case_store import get_case
from app.town_map import map_payload


def test_case_004_uses_canonical_overworld_contract_without_revealing_objects():
    payload = map_payload(get_case("case_004"), set())

    assert payload["mode"] == "canonical_overworld"
    assert payload["definition_id"] == "town_canonical_v1"
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


def test_case_004_locations_include_function_tags_for_migration():
    payload = map_payload(get_case("case_004"), set())
    locations = payload["canonical_locations"]

    assert locations["loc_pub"]["function_tag"] == "pub"
    assert locations["loc_pub"]["building_role"] == "business"
    assert locations["loc_clinic"]["function_tag"] == "clinic"
    assert locations["loc_clinic"]["building_role"] == "public_service"
    assert "case_004" in locations["loc_ben_flat"]["case_ids"]


def test_case_004_places_use_hd_search_illustrations():
    from app.projections import project_map_location

    case = get_case("case_004")
    locations = {loc.location_id: project_map_location(loc, case.case.case_id) for loc in case.locations}

    assert locations["loc_fountain"]["illustration"] == "/art/case_004/fountain_closeup.png"
    assert locations["loc_pub"]["illustration"].endswith("/mallet_crown_pub_full_interior_hd.png")
    assert locations["loc_ben_flat"]["illustration"].endswith("/ben_flat_interior_hd.png")
    assert locations["loc_priya_flat"]["illustration"].endswith("/priya_flat_interior_hd.png")
    assert locations["loc_elias_house"]["illustration"].endswith("/elias_cottage_full_interior_hd.png")
    assert locations["loc_owen_house"]["illustration"].endswith("/owen_house_workshop_yard_hd.png")
    assert locations["loc_clinic"]["illustration"].endswith("/village_clinic_full_interior_hd.png")


def test_case_004_inspect_clues_have_authored_search_hotspots():
    case = get_case("case_004")
    expected = {
        "clue_blackmail_letters": ("loc_ben_flat", 28, 52, 7),
        "clue_arson_clipping": ("loc_ben_flat", 46, 61, 6),
        "clue_ben_cancel_text": ("loc_ben_flat", 51, 57, 6),
        "clue_jacket_mud": ("loc_ben_flat", 16, 56, 7),
        "clue_fountain_stone": ("loc_fountain", 78, 45, 7),
        "clue_bootprint": ("loc_fountain", 71, 57, 7),
        "clue_fred_lighter_found": ("loc_fountain", 45, 69, 7),
        "clue_fred_ledger_debt": ("loc_pub", 76, 23, 7),
    }

    clues = {clue.clue_id: clue for clue in case.clues}
    for clue_id, (location_id, x, y, radius) in expected.items():
        discoverability = clues[clue_id].discoverability
        assert discoverability.method == "inspect"
        assert discoverability.location_id == location_id
        assert discoverability.x == x
        assert discoverability.y == y
        assert discoverability.radius == radius


def test_unmigrated_cases_keep_legacy_visual_fallback_contract():
    for case_id in ("case_001", "case_002", "case_003", "case_005", "case_006"):
        # The visual contract only needs the case id. Avoid loading unrelated
        # static case truth in this regression test; those files may be under
        # separate authoring/validation work.
        payload = map_payload(SimpleNamespace(case=SimpleNamespace(case_id=case_id)), set())
        assert payload["mode"] == "legacy_fallback"
        assert payload["definition_id"] == "legacy_the_ville"
        assert payload["objects"] == []
