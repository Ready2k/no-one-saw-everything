"""Building place bundles and deterministic town dressing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LIBRARY_FILE = Path(__file__).parent / "data" / "town" / "building_library.json"
PLACE_ART_REGISTRY_FILE = Path(__file__).parent / "data" / "town" / "place_art_registry.json"


def load_building_library() -> dict[str, Any]:
    return json.loads(LIBRARY_FILE.read_text())


def load_place_art_registry() -> dict[str, Any]:
    """Return the searchable source of truth for case lighting and scene bindings."""
    return json.loads(PLACE_ART_REGISTRY_FILE.read_text())


_INTERIOR_LOCATION_PARENTS = {
    "loc_cafe_kitchen": "loc_hobbs_cafe",
    "loc_cafe_storage": "loc_hobbs_cafe",
    "loc_bookshop_back": "loc_bookshop",
    "loc_clinic_dispensary": "loc_clinic",
    "loc_marcus_study": "loc_marcus_house",
    "loc_clara_flat": "loc_hobbs_cafe",
    "loc_ben_flat": "flats_two_storey_v1",
    "loc_priya_flat": "flats_two_storey_v1",
    "loc_nadia_flat": "flats_two_storey_v1",
}


_CANONICAL_SEARCH_ILLUSTRATIONS = {
    "loc_back_lane": "/art/case_005/back_lane_dawn_hd.avif",
    "loc_ben_flat": "/art/case_001/ben_flat_investigation_v2.avif",
    "loc_bookshop": "/art/case_001/reed_bell_bookshop_investigation_v2.avif",
    "loc_bookshop_back": "/art/case_001/bookshop_back_room_investigation_v2.avif",
    "loc_cafe_kitchen": "/art/case_001/cafe_kitchen_investigation_v4.avif",
    "loc_cafe_storage": "/art/case_001/storage_room_interactive_wide_v1.avif",
    "loc_clara_flat": "/art/case_001/clara_flat_investigation_v4.avif",
    "loc_clinic": "/art/case_001/village_clinic_investigation_v2.avif",
    "loc_clinic_dispensary": "/art/case_001/clinic_dispensary_investigation_v2.avif",
    "loc_elias_bench": "/art/case_001/elias_bench_investigation_v4.avif",
    "loc_elias_house": "/art/case_001/elias_house_investigation_v4.avif",
    "loc_fountain": "/art/case_001/fountain_dawn_investigation_v5.avif",
    "loc_hobbs_cafe": "/art/case_001/hobbs_cafe_investigation_v4.avif",
    "loc_marcus_house": "/art/case_001/marcus_house_investigation_v4.avif",
    "loc_marcus_study": "/art/case_001/marcus_study_investigation_v2.avif",
    "loc_nadia_flat": "/art/case_001/nadia_flat_investigation_v4.avif",
    "loc_owen_house": "/art/case_001/owen_house_yard_investigation_v2.avif",
    "loc_priya_flat": "/art/case_001/priya_flat_investigation_v4.avif",
    "loc_pub": "/art/case_001/mallet_crown_pub_investigation_v2.avif",
    "loc_rear_alley": "/art/case_001/rear_alley_investigation_v2.avif",
    "loc_ruth_cottage": "/art/case_001/ruth_cottage_investigation_v2.avif",
    "loc_solicitors_office": "/art/case_001/solicitors_office_investigation_v2.avif",
    "loc_village_square": "/art/case_005/village_square_dawn_hd.avif",
    "loc_st_alder_church": "/art/town/interiors_hd/expansion_v1/st_alder_church_search_hd.avif",
    "loc_willow_farmhouse": "/art/town/interiors_hd/expansion_v1/willow_farmhouse_search_hd.avif",
}


_REUSABLE_SEARCH_ILLUSTRATIONS = {
    "loc_village_square": "/art/town/places_hd/village_square_hd.avif",
    "loc_fishery": "/art/town/places_hd/fishery_hd.avif",
    "loc_lake": "/art/town/places_hd/lovers_lake_hd.avif",
    "loc_woodland": "/art/town/places_hd/whispering_woodland_hd.avif",
    "loc_meadow": "/art/town/places_hd/green_meadow_hd.avif",
}


def location_search_illustration(location_id: str, case_id: str | None = None) -> str | None:
    """Return high-resolution searchable place art for authored locations."""
    case_sets = load_place_art_registry().get("case_bindings", {})
    case_illustration = case_sets.get(case_id or "", {}).get(location_id)
    if case_illustration:
        return case_illustration
    canonical = _CANONICAL_SEARCH_ILLUSTRATIONS.get(location_id)
    if canonical:
        return canonical
    return _REUSABLE_SEARCH_ILLUSTRATIONS.get(location_id)


def location_art_asset(location_id: str, view: str = "external") -> str | None:
    """Return the shared cosmetic art for a location without changing case truth."""
    library = load_building_library()
    variant = library.get("location_variants", {}).get(location_id)
    if variant and view == "internal":
        return variant.get("interior_asset")

    bindings = library.get("location_bindings", {})
    asset_id = bindings.get(location_id)
    parent = _INTERIOR_LOCATION_PARENTS.get(location_id)
    if parent and parent in bindings:
        asset_id = bindings[parent]
    elif parent in library.get("buildings", {}):
        asset_id = parent
    if not asset_id:
        return None
    asset = library.get("buildings", {}).get(asset_id)
    if not asset:
        return None
    return asset.get("interior_asset" if view == "internal" else "exterior_asset")


def _tiles_for_rect(x: int, y: int, w: int, h: int, tile_id: str) -> list[dict[str, Any]]:
    return [{"x": tx, "y": ty, "tile_id": tile_id} for tx in range(x, x + w) for ty in range(y, y + h)]


# Buildings rotate clockwise in 90° steps; art is authored door-south, so the
# front edge walks south → west → north → east. Mirrored by the frontend's
# dressBuilding in editorTypes.ts — keep the two in lockstep.
_EDGES = ["south", "west", "north", "east"]


def _edge_strip(x: int, y: int, w: int, h: int, edge: str, depth: int, tile_id: str) -> list[dict[str, Any]]:
    if edge == "south":
        return _tiles_for_rect(x, y + h, w, depth, tile_id)
    if edge == "north":
        return _tiles_for_rect(x, y - depth, w, depth, tile_id)
    if edge == "west":
        return _tiles_for_rect(x - depth, y, depth, h, tile_id)
    return _tiles_for_rect(x + w, y, depth, h, tile_id)


def dress_building(building: dict[str, Any], x: int, y: int, rotation: int = 0) -> dict[str, list[dict[str, Any]]]:
    """Generate replaceable structure, path and boundary tiles for a placement."""
    source_w, source_h = building["footprint"]["w"], building["footprint"]["h"]
    steps = (rotation // 90) % 4
    w, h = (source_h, source_w) if steps % 2 else (source_w, source_h)
    front, rear = _EDGES[steps], _EDGES[(steps + 2) % 4]
    side_edges = [_EDGES[(steps + 1) % 4], _EDGES[(steps + 3) % 4]]
    rules = building.get("surrounding_rules", {})
    tiles: dict[str, list[dict[str, Any]]] = {"structures": [], "paths": [], "terrain_detail": []}
    tiles["structures"] = _tiles_for_rect(x, y, w, h, "tile_wall_exterior")
    if rules.get("front") == "path":
        tiles["paths"] = _edge_strip(x, y, w, h, front, 2, "tile_path")
    side = rules.get("sides")
    if side in {"fence", "hedge", "flowerbed"}:
        for edge in side_edges:
            tiles["terrain_detail"] += _edge_strip(x, y, w, h, edge, 1, f"tile_{side}")
    rear_rule = rules.get("rear")
    if rear_rule == "service_path":
        tiles["paths"] += _edge_strip(x, y, w, h, rear, 1, "tile_path")
    elif rear_rule in {"fence", "hedge", "garden"}:
        tiles["terrain_detail"] += _edge_strip(x, y, w, h, rear, 1, "tile_flowerbed" if rear_rule == "garden" else f"tile_{rear_rule}")
    return tiles


def create_building_instance(asset_id: str, x: int, y: int, *, instance_id: str, location_id: str | None = None, rotation: int = 0) -> dict[str, Any]:
    library = load_building_library()["buildings"]
    if asset_id not in library:
        raise KeyError(f"Unknown building asset '{asset_id}'")
    building = library[asset_id]
    return {
        "instance_id": instance_id,
        "asset_id": asset_id,
        "location_id": location_id or instance_id,
        "x": x,
        "y": y,
        "rotation": rotation,
        "exterior_asset": building["exterior_asset"],
        "interior_asset": building["interior_asset"],
        "footprint": building["footprint"],
        "entrances": building["entrances"],
        "derived_tiles": dress_building(building, x, y, rotation),
    }
