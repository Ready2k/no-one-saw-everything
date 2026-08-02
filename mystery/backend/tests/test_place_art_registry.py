from pathlib import Path

from app.case_store import get_case
from app.place_library import load_place_art_registry, location_search_illustration


PUBLIC_ROOT = Path(__file__).parents[2] / "frontend" / "public"


def test_registry_bindings_exist_and_are_the_runtime_source_of_truth():
    registry = load_place_art_registry()
    for case_id, bindings in registry["case_bindings"].items():
        for location_id, asset in bindings.items():
            assert (PUBLIC_ROOT / asset.lstrip("/")).is_file(), f"missing {asset}"
            assert location_search_illustration(location_id, case_id) == asset


def test_registry_coverage_labels_cannot_overstate_case_artwork():
    registry = load_place_art_registry()
    for case_id, profile in registry["case_profiles"].items():
        location_ids = {location.location_id for location in get_case(case_id).locations}
        bound_ids = set(registry["case_bindings"][case_id])
        assert bound_ids <= location_ids
        if profile["coverage"] == "complete":
            assert bound_ids == location_ids
        elif profile["coverage"] == "missing":
            assert not bound_ids
        else:
            assert bound_ids < location_ids


def test_every_authored_case_has_searchable_time_metadata():
    registry = load_place_art_registry()
    assert set(registry["case_profiles"]) == set(registry["case_bindings"])
    for profile in registry["case_profiles"].values():
        assert profile["clock_range"]
        assert profile["lighting_phase"]
        assert profile["weather"]
        assert profile["coverage"] in {"complete", "partial", "missing"}


def test_every_shipped_case_has_an_explicit_scene_for_every_location():
    registry = load_place_art_registry()
    assert all(profile["coverage"] == "complete" for profile in registry["case_profiles"].values())
