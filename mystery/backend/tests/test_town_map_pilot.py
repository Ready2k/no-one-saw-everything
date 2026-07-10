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


def test_unmigrated_cases_keep_legacy_visual_fallback_contract():
    for case_id in ("case_001", "case_002", "case_003", "case_005", "case_006"):
        # The visual contract only needs the case id. Avoid loading unrelated
        # static case truth in this regression test; those files may be under
        # separate authoring/validation work.
        payload = map_payload(SimpleNamespace(case=SimpleNamespace(case_id=case_id)), set())
        assert payload["mode"] == "legacy_fallback"
        assert payload["definition_id"] == "legacy_the_ville"
        assert payload["objects"] == []
