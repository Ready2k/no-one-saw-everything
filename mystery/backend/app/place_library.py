"""Building place bundles and deterministic town dressing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LIBRARY_FILE = Path(__file__).parent / "data" / "town" / "building_library.json"


def load_building_library() -> dict[str, Any]:
    return json.loads(LIBRARY_FILE.read_text())


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


def dress_building(building: dict[str, Any], x: int, y: int, rotation: int = 0) -> dict[str, list[dict[str, Any]]]:
    """Generate replaceable structure, path and boundary tiles for a placement."""
    source_w, source_h = building["footprint"]["w"], building["footprint"]["h"]
    w, h = (source_h, source_w) if rotation % 180 else (source_w, source_h)
    rules = building.get("surrounding_rules", {})
    tiles: dict[str, list[dict[str, Any]]] = {"structures": [], "paths": [], "terrain_detail": []}
    tiles["structures"] = _tiles_for_rect(x, y, w, h, "tile_wall_exterior")
    if rules.get("front") == "path":
        tiles["paths"] = _tiles_for_rect(x, y + h, w, 2, "tile_path")
    side = rules.get("sides")
    if side in {"fence", "hedge", "flowerbed"}:
        tiles["terrain_detail"] = _tiles_for_rect(x - 1, y, 1, h, f"tile_{side}") + _tiles_for_rect(x + w, y, 1, h, f"tile_{side}")
    rear = rules.get("rear")
    if rear == "service_path":
        tiles["paths"] += _tiles_for_rect(x, y - 1, w, 1, "tile_path")
    elif rear in {"fence", "hedge", "garden"}:
        tiles["terrain_detail"] += _tiles_for_rect(x, y - 1, w, 1, "tile_flowerbed" if rear == "garden" else f"tile_{rear}")
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
