"""Reusable visual-only town map definitions.

This module is deliberately separate from case truth. It maps authoritative
location/object/clue ids to visual geometry and safe presentation metadata.
It must never decide discovery, deduction, event visibility, or access rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import CaseData

TOWN_LAYOUT_FILE = Path(__file__).parent / "data" / "town" / "town_layout.json"


ALLOWED_TILES = {
    "tile_grass", "tile_mud", "tile_cobble", "tile_path", "tile_floor_wood",
    "tile_floor_stone", "tile_wall_exterior", "tile_wall_interior", "tile_water",
    "tile_water_edge", "tile_fence", "tile_hedge", "tile_flowerbed", "tile_tree",
    "tile_shadow_soft"
}

ALLOWED_PROPS = {
    "prop_fountain_coping", "prop_lamp", "prop_bench", "prop_cafe_counter",
    "prop_till", "prop_mop_bucket", "prop_coat_rack", "prop_crate",
    "prop_bookshop_shelf", "prop_desk", "prop_letter_opener", "prop_broken_window",
    "prop_clinic_bed", "prop_dispensary_shelf", "prop_medicine_cabinet",
    "prop_pub_bar", "prop_pub_stool", "prop_pub_ledger", "prop_lighter",
    "prop_fireplace", "prop_cocoa_mug", "prop_books", "prop_garden_plant",
    "prop_foxglove", "prop_letters", "prop_documents", "prop_phone", "prop_key",
    "prop_belt", "prop_boots", "prop_muddy_footprint"
}

ALLOWED_LAYERS = {
    "base", "terrain_detail", "paths", "interior_floors", "walls", "structures",
    "props", "case_overlays", "object_anchors", "evidence_markers", "fog", "debug_bounds"
}

ALLOWED_NESTING = {
    ("loc_village_square", "loc_fountain"),
    ("loc_hobbs_cafe", "loc_cafe_kitchen"),
    ("loc_hobbs_cafe", "loc_cafe_storage"),
    ("loc_bookshop", "loc_bookshop_back"),
    ("loc_clinic", "loc_clinic_dispensary"),
    ("loc_marcus_house", "loc_marcus_study"),
    ("loc_village_square", "loc_elias_bench")
}

def validate_town_layout_payload(payload: Any) -> list[str]:
    """Validates the layout payload and returns a list of error strings.
    If the list is empty, the payload is valid.
    """
    errors = []
    
    if not isinstance(payload, dict):
        return ["Payload must be a JSON object"]
        
    if payload.get("version") != "town_layout_editor_v2":
        errors.append("Invalid layout version. Expected 'town_layout_editor_v2'")
        
    grid = payload.get("grid")
    if not isinstance(grid, dict):
        errors.append("Grid configuration must be a JSON object")
    else:
        if grid.get("cols") != 192 or grid.get("rows") != 144:
            errors.append("Grid size must be exactly 192 columns by 144 rows")
        if grid.get("tile_size") != 32:
            errors.append("Tile size must be exactly 32")
            
    from .case_store import list_all_cases, get_case
    try:
        valid_cases = list_all_cases()
        valid_case_ids = {c["case_id"] for c in valid_cases}
    except Exception as e:
        valid_case_ids = set()
        errors.append(f"Failed to retrieve list of cases from store: {e}")

    valid_location_ids = set(CANONICAL_LOCATIONS.keys())
    
    # 1. Validate canonical_locations
    canonical_locs = payload.get("canonical_locations", {})
    if not isinstance(canonical_locs, dict):
        errors.append("canonical_locations must be a JSON object")
    else:
        effective_locs = {}
        for loc_id, loc_data in canonical_locs.items():
            if not isinstance(loc_data, dict):
                errors.append(f"Location data for {loc_id} must be an object")
                continue
            
            if loc_id not in valid_location_ids:
                errors.append(f"Canonical location ID '{loc_id}' is not in the canonical contract")
                
            bounds = loc_data.get("bounds")
            if not isinstance(bounds, dict):
                errors.append(f"Location {loc_id} missing bounds object")
            else:
                x = bounds.get("x")
                y = bounds.get("y")
                w = bounds.get("w")
                h = bounds.get("h")
                if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (x, y, w, h)):
                    errors.append(f"Bounds coordinates for {loc_id} must be numbers (tile coordinates)")
                else:
                    if w <= 0 or h <= 0:
                        errors.append(f"Bounds width and height for {loc_id} must be positive")
                    if x < 0 or y < 0 or x + w > 192 or y + h > 144:
                        errors.append(f"Bounds for {loc_id} must remain within the 192x144 grid")
                    effective_locs[loc_id] = {"x": x, "y": y, "w": w, "h": h}
            
            mode = loc_data.get("mode")
            if mode not in ("interior", "exterior"):
                errors.append(f"Location {loc_id} has invalid mode: '{mode}'. Must be 'interior' or 'exterior'")

        # Validate Overlaps with Nesting Rules
        loc_ids = list(effective_locs.keys())
        for i in range(len(loc_ids)):
            for j in range(i + 1, len(loc_ids)):
                idA = loc_ids[i]
                idB = loc_ids[j]
                
                if (idA, idB) in ALLOWED_NESTING or (idB, idA) in ALLOWED_NESTING:
                    continue
                    
                bA = effective_locs[idA]
                bB = effective_locs[idB]
                overlap = not (
                    bA["x"] + bA["w"] <= bB["x"] or
                    bB["x"] + bB["w"] <= bA["x"] or
                    bA["y"] + bA["h"] <= bB["y"] or
                    bB["y"] + bB["h"] <= bA["y"]
                )
                if overlap:
                    errors.append(f"Overlap detected between top-level locations '{idA}' and '{idB}' without allowed nesting relationship")

    # 2. Validate case overrides
    case_overrides = payload.get("case_overrides", {})
    if not isinstance(case_overrides, dict):
        errors.append("case_overrides must be a JSON object")
    else:
        for case_id, override_data in case_overrides.items():
            if case_id not in valid_case_ids:
                errors.append(f"Case ID '{case_id}' in overrides does not exist in the database")
                continue
                
            if not isinstance(override_data, dict):
                errors.append(f"Override data for {case_id} must be an object")
                continue
                
            try:
                case_info = get_case(case_id)
                case_locations = {l.location_id for l in case_info.locations}
                case_objects = {o.object_id: o for o in case_info.objects}
            except Exception as e:
                errors.append(f"Failed to load case data for {case_id} validation: {e}")
                continue
                
            visible_locs = override_data.get("visible_locations", [])
            if not isinstance(visible_locs, list):
                errors.append(f"visible_locations in case {case_id} must be a list")
            else:
                for loc_id in visible_locs:
                    if loc_id not in case_locations and loc_id not in valid_location_ids:
                        errors.append(f"Visible location ID '{loc_id}' in case {case_id} is not valid")
            
            loc_bounds = override_data.get("location_bounds", {})
            effective_case_locs = {}
            for loc_id in visible_locs:
                if loc_bounds and loc_id in loc_bounds:
                    b = loc_bounds[loc_id]
                    effective_case_locs[loc_id] = {"x": b.get("x", 0), "y": b.get("y", 0), "w": b.get("w", 1), "h": b.get("h", 1)}
                elif loc_id in effective_locs:
                    effective_case_locs[loc_id] = effective_locs[loc_id]
                elif loc_id in _BOUNDS_TILES:
                    tx, ty, tw, th = _BOUNDS_TILES[loc_id]
                    effective_case_locs[loc_id] = {"x": tx, "y": ty, "w": tw, "h": th}

            case_loc_ids = list(effective_case_locs.keys())
            for i in range(len(case_loc_ids)):
                for j in range(i + 1, len(case_loc_ids)):
                    idA = case_loc_ids[i]
                    idB = case_loc_ids[j]
                    if (idA, idB) in ALLOWED_NESTING or (idB, idA) in ALLOWED_NESTING:
                        continue
                    bA = effective_case_locs[idA]
                    bB = effective_case_locs[idB]
                    overlap = not (
                        bA["x"] + bA["w"] <= bB["x"] or
                        bB["x"] + bB["w"] <= bA["x"] or
                        bA["y"] + bA["h"] <= bB["y"] or
                        bB["y"] + bB["h"] <= bA["y"]
                    )
                    if overlap:
                        errors.append(f"Overlap detected in case {case_id} between locations '{idA}' and '{idB}' without allowed nesting relationship")

            if not isinstance(loc_bounds, dict):
                errors.append(f"location_bounds override in case {case_id} must be an object")
            else:
                for loc_id, bounds in loc_bounds.items():
                    if loc_id not in case_locations and loc_id not in valid_location_ids:
                        errors.append(f"Overridden location ID '{loc_id}' in case {case_id} is not valid")
                    if not isinstance(bounds, dict):
                        errors.append(f"Overridden bounds for {loc_id} in case {case_id} must be an object")
                        continue
                    x = bounds.get("x")
                    y = bounds.get("y")
                    w = bounds.get("w")
                    h = bounds.get("h")
                    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (x, y, w, h)):
                        errors.append(f"Overridden bounds coordinates for {loc_id} in case {case_id} must be numbers")
                    else:
                        if w <= 0 or h <= 0:
                            errors.append(f"Overridden bounds width and height for {loc_id} in case {case_id} must be positive")
                        if x < 0 or y < 0 or x + w > 192 or y + h > 144:
                            errors.append(f"Overridden bounds for {loc_id} in case {case_id} must remain within 192x144 grid")
            
            def get_effective_bounds(l_id: str) -> dict[str, int] | None:
                if l_id in loc_bounds:
                    return loc_bounds[l_id]
                if l_id in canonical_locs:
                    b = canonical_locs[l_id].get("bounds")
                    if b:
                        return {"x": b["x"], "y": b["y"], "w": b["w"], "h": b["h"]}
                if l_id in _BOUNDS_TILES:
                    tx, ty, tw, th = _BOUNDS_TILES[l_id]
                    return {"x": tx, "y": ty, "w": tw, "h": th}
                return None

            obj_anchors = override_data.get("object_anchors", {})
            if not isinstance(obj_anchors, dict):
                errors.append(f"object_anchors in case {case_id} must be an object")
            else:
                for obj_id, anchor_data in obj_anchors.items():
                    if obj_id not in case_objects:
                        errors.append(f"Object ID '{obj_id}' in case {case_id} does not exist in objects.json")
                        continue
                    if not isinstance(anchor_data, dict):
                        errors.append(f"Anchor data for {obj_id} in case {case_id} must be an object")
                        continue
                        
                    loc_id = anchor_data.get("location_id")
                    if not loc_id:
                        errors.append(f"Object '{obj_id}' in case {case_id} lacks location_id")
                    elif loc_id not in case_locations and loc_id not in valid_location_ids:
                        errors.append(f"Object '{obj_id}' in case {case_id} assigned to unknown location '{loc_id}'")
                        
                    render_policy = anchor_data.get("render_policy")
                    if render_policy != "debug_only" and loc_id and loc_id not in visible_locs:
                        errors.append(f"Object anchor '{obj_id}' in case {case_id} is assigned to hidden location '{loc_id}' but render policy is not 'debug_only'")

                    anchor = anchor_data.get("anchor")
                    if not isinstance(anchor, dict):
                        errors.append(f"Object '{obj_id}' in case {case_id} lacks anchor coordinate object")
                    else:
                        ax = anchor.get("x")
                        ay = anchor.get("y")
                        if not isinstance(ax, (int, float)) or isinstance(ax, bool) or not isinstance(ay, (int, float)) or isinstance(ay, bool):
                            errors.append(f"Anchor coordinates for '{obj_id}' in case {case_id} must be numbers")
                        else:
                            if ax < 0 or ay < 0 or ax >= 192 or ay >= 144:
                                errors.append(f"Anchor coordinates for '{obj_id}' in case {case_id} lie outside grid")
                                
                            is_external = anchor_data.get("external", False) or render_policy == "external"
                            if not is_external and loc_id:
                                eff_bounds = get_effective_bounds(loc_id)
                                if eff_bounds:
                                    bx = eff_bounds["x"]
                                    by = eff_bounds["y"]
                                    bw = eff_bounds["w"]
                                    bh = eff_bounds["h"]
                                    if not (bx <= ax < bx + bw and by <= ay < by + bh):
                                        errors.append(
                                            f"Object anchor for '{obj_id}' at ({ax}, {ay}) is outside the bounds of '{loc_id}' "
                                            f"({bx}, {by}, {bw}, {bh}) and not marked as external"
                                        )

                    semantic_asset_id = anchor_data.get("semantic_asset_id")
                    if semantic_asset_id is not None and not isinstance(semantic_asset_id, str):
                        errors.append(f"semantic_asset_id for '{obj_id}' in case {case_id} must be a string")

    # 3. Validate tile_layers (Sparse format)
    tile_layers = payload.get("tile_layers", {})
    if not isinstance(tile_layers, dict):
        errors.append("tile_layers must be a JSON object")
    else:
        for layer_name, layer_data in tile_layers.items():
            if layer_name not in ALLOWED_LAYERS:
                errors.append(f"Unknown layer name '{layer_name}' in tile_layers")
            if not isinstance(layer_data, dict):
                errors.append(f"Layer data for '{layer_name}' must be an object")
                continue
            tiles_list = layer_data.get("tiles", [])
            if not isinstance(tiles_list, list):
                errors.append(f"tiles under layer '{layer_name}' must be a list")
                continue
            for tile in tiles_list:
                if not isinstance(tile, dict):
                    errors.append(f"Tile entry in '{layer_name}' must be an object")
                    continue
                tx = tile.get("x")
                ty = tile.get("y")
                tile_id = tile.get("tile_id")
                if not isinstance(tx, int) or isinstance(tx, bool) or not isinstance(ty, int) or isinstance(ty, bool):
                    errors.append(f"Tile coordinates under '{layer_name}' must be integers")
                else:
                    if tx < 0 or tx >= 192 or ty < 0 or ty >= 144:
                        errors.append(f"Tile coordinate ({tx}, {ty}) under '{layer_name}' sits outside the 192x144 grid")
                if tile_id not in ALLOWED_TILES:
                    errors.append(f"Unknown tile ID '{tile_id}' under layer '{layer_name}'")

    # 4. Validate prop_instances
    prop_instances = payload.get("prop_instances", {})
    if not isinstance(prop_instances, dict):
        errors.append("prop_instances must be a JSON object")
    else:
        all_objects = {}
        for c in valid_cases:
            try:
                c_data = get_case(c["case_id"])
                for o in c_data.objects:
                    all_objects[o.object_id] = o
            except Exception:
                pass

        for scope_id, instances in prop_instances.items():
            if scope_id != "canonical" and scope_id not in valid_case_ids:
                errors.append(f"Prop scope ID '{scope_id}' must be 'canonical' or a valid case ID")
                continue
            if not isinstance(instances, list):
                errors.append(f"Prop instances for scope '{scope_id}' must be a list")
                continue
            
            seen_ids = set()
            for prop in instances:
                if not isinstance(prop, dict):
                    errors.append(f"Prop instance entry in scope '{scope_id}' must be an object")
                    continue
                instance_id = prop.get("instance_id")
                asset_id = prop.get("asset_id")
                location_id = prop.get("location_id")
                px = prop.get("x")
                py = prop.get("y")
                
                if not instance_id or not asset_id or not location_id or px is None or py is None:
                    errors.append(f"Prop instance in scope '{scope_id}' is missing required fields (instance_id, asset_id, location_id, x, y)")
                    continue
                
                if not isinstance(instance_id, str):
                    errors.append(f"instance_id '{instance_id}' under scope '{scope_id}' must be a string")
                else:
                    if instance_id in seen_ids:
                        errors.append(f"Duplicate prop instance ID '{instance_id}' within scope '{scope_id}'")
                    seen_ids.add(instance_id)

                if asset_id not in ALLOWED_PROPS:
                    errors.append(f"Unknown prop asset ID '{asset_id}' under scope '{scope_id}'")

                if location_id not in valid_location_ids:
                    errors.append(f"Prop instance '{instance_id}' is assigned to unknown location '{location_id}'")

                if not isinstance(px, (int, float)) or isinstance(px, bool) or not isinstance(py, (int, float)) or isinstance(py, bool):
                    errors.append(f"Prop coordinates for '{instance_id}' must be numbers")
                else:
                    if px < 0 or px >= 192 or py < 0 or py >= 144:
                        errors.append(f"Prop coordinate ({px}, {py}) sits outside the 192x144 grid")
                
                p_layer = prop.get("layer", "props")
                if p_layer not in ALLOWED_LAYERS:
                    errors.append(f"Unknown layer name '{p_layer}' in prop instance '{instance_id}'")
                
                r_policy = prop.get("render_policy", "always_visible")
                if r_policy not in ("always_visible", "case_visible", "discovery_gated", "hidden_until_revealed", "debug_only"):
                    errors.append(f"Unsupported render policy '{r_policy}' in prop '{instance_id}'")

                obj_id = prop.get("object_id")
                if r_policy == "discovery_gated" and not obj_id:
                    errors.append(f"Prop instance '{instance_id}' has policy 'discovery_gated' but lacks a linked object_id")
                
                if obj_id:
                    if obj_id not in all_objects:
                        errors.append(f"Prop instance '{instance_id}' links to unknown object ID '{obj_id}'")

    return errors


def load_town_layout() -> dict[str, Any] | None:
    """Loads the town layout from disk and validates it.
    Returns the validated dictionary, or None if missing or invalid.
    """
    if not TOWN_LAYOUT_FILE.exists():
        return None
    try:
        data = json.loads(TOWN_LAYOUT_FILE.read_text())
        errors = validate_town_layout_payload(data)
        if errors:
            import logging
            logging.getLogger(__name__).warning(f"Loaded layout file contains validation errors: {errors}")
            return None
        return data
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error loading or parsing town layout: {e}")
        return None

CANONICAL_MAP: dict[str, Any] = {
    "definition_id": "town_canonical_v1",
    "asset": "town_canonical_v1",
    "image": "/art/town/town_canonical_v2_overworld_day.png",
    # HD overworld sliced into a 3x3 mosaic (rows A-C top->bottom, cols 1-3
    # left->right; B2 is the town centre). Each cell is 2048x1536 = 64x48
    # tiles. Clients that understand image_tiles should prefer it over the
    # single `image` above, which is kept as a fallback.
    "image_tiles": {
        "cols": 3,
        "rows": 3,
        "urls": [
            [
                (
                    "/art/town/tiles_3x3_hd/town_overworld_B2_all_cases_external_hd.png"
                    if row == "B" and col == 2
                    else f"/art/town/tiles_3x3_hd/town_overworld_{row}{col}_hd.png"
                )
                for col in (1, 2, 3)
            ]
            for row in ("A", "B", "C")
        ],
    },
    # When the user zooms into the centre town tile, swap B2 from the
    # exterior overview into the roofless investigation interior.
    "zoom_image_tiles": {
        "threshold": 3.2,
        "urls": [
            [
                (
                    "/art/town/tiles_3x3_hd/town_overworld_B2_interior_hd.png"
                    if row == "B" and col == 2
                    else f"/art/town/tiles_3x3_hd/town_overworld_{row}{col}_hd.png"
                )
                for col in (1, 2, 3)
            ]
            for row in ("A", "B", "C")
        ],
    },
    "width": 6144,
    "height": 4608,
    "tile_size": 32,
    "grid": {"cols": 192, "rows": 144},
    "origin": "north_west",
    "base_palette": "neutral_daylight_soft_ambient",
    "lighting_overlay": "runtime_lightingTint",
}

# Canonical layout bounds from docs/canonical_town_layout.md, converted from
# tiles to canonical map pixels. These are visual recommendations only.
_BOUNDS_TILES: dict[str, tuple[int, int, int, int]] = {
    "loc_village_square": (82, 62, 28, 16),
    "loc_fountain": (93, 67, 10, 9),
    "loc_marcus_house": (92, 53, 11, 8),
    "loc_marcus_study": (95, 55, 8, 6),
    "loc_hobbs_cafe": (82, 55, 11, 8),
    "loc_cafe_kitchen": (84, 60, 5, 5),
    "loc_cafe_storage": (89, 60, 5, 5),
    "loc_clinic": (103, 63, 9, 8),
    "loc_clinic_dispensary": (109, 64, 6, 6),
    "loc_bookshop": (74, 57, 10, 8),
    "loc_bookshop_back": (74, 61, 10, 6),
    "loc_rear_alley": (86, 53, 20, 4),
    "loc_pub": (73, 54, 11, 10),
    "loc_owen_house": (111, 61, 11, 10),
    "loc_elias_house": (88, 79, 8, 7),
    "loc_clara_flat": (83, 51, 7, 5),
    "loc_ben_flat": (69, 72, 7, 5),
    "loc_priya_flat": (70, 77, 7, 5),
    "loc_nadia_flat": (104, 58, 6, 5),
    "loc_ruth_cottage": (112, 77, 11, 9),
    "loc_solicitors_office": (106, 85, 9, 6),
    "loc_elias_bench": (95, 70, 4, 2),
    "loc_fishery": (107, 56, 5, 5),
    "loc_lake": (66, 50, 14, 10),
    "loc_woodland": (65, 82, 3, 12),
    "loc_meadow": (94, 85, 12, 9),
}


def _tile_bounds(bounds: tuple[int, int, int, int]) -> dict[str, int]:
    x, y, width, height = bounds
    return {"x": x * 32, "y": y * 32, "width": width * 32, "height": height * 32}


def _center(bounds: dict[str, int]) -> dict[str, int]:
    return {"x": bounds["x"] + bounds["width"] // 2, "y": bounds["y"] + bounds["height"] // 2}


CANONICAL_LOCATIONS: dict[str, dict[str, Any]] = {
    location_id: {"bounds": _tile_bounds(bounds), "layer": "interior" if location_id in {
        "loc_cafe_kitchen", "loc_cafe_storage", "loc_bookshop_back",
        "loc_clinic_dispensary", "loc_marcus_study", "loc_clara_flat",
        "loc_ben_flat", "loc_priya_flat", "loc_nadia_flat",
    } else "exterior"}
    for location_id, bounds in _BOUNDS_TILES.items()
}
for _location in CANONICAL_LOCATIONS.values():
    _location["position"] = _center(_location["bounds"])


CANONICAL_ADJACENCY: dict[str, list[str]] = {
    "loc_village_square": [
        "loc_fountain", "loc_hobbs_cafe", "loc_bookshop", "loc_clinic",
        "loc_pub", "loc_marcus_house", "loc_owen_house", "loc_elias_house",
        "loc_priya_flat", "loc_nadia_flat", "loc_ben_flat", "loc_ruth_cottage",
        "loc_solicitors_office", "loc_fishery", "loc_lake", "loc_woodland", "loc_meadow",
    ],
    "loc_fountain": ["loc_village_square", "loc_elias_bench"],
    "loc_hobbs_cafe": ["loc_village_square", "loc_cafe_kitchen", "loc_clara_flat"],
    "loc_cafe_kitchen": ["loc_hobbs_cafe", "loc_cafe_storage"],
    "loc_cafe_storage": ["loc_cafe_kitchen", "loc_rear_alley"],
    "loc_rear_alley": ["loc_village_square", "loc_hobbs_cafe", "loc_bookshop"],
    "loc_bookshop": ["loc_village_square", "loc_bookshop_back", "loc_rear_alley"],
    "loc_bookshop_back": ["loc_bookshop", "loc_rear_alley"],
    "loc_clinic": ["loc_village_square", "loc_clinic_dispensary"],
    "loc_clinic_dispensary": ["loc_clinic"],
    "loc_marcus_house": ["loc_village_square", "loc_marcus_study"],
    "loc_marcus_study": ["loc_marcus_house"],
    "loc_owen_house": ["loc_village_square"],
    "loc_elias_house": ["loc_village_square"],
    "loc_elias_bench": ["loc_village_square", "loc_fountain"],
    "loc_clara_flat": ["loc_hobbs_cafe"],
    "loc_priya_flat": ["loc_village_square"],
    "loc_nadia_flat": ["loc_village_square", "loc_clinic"],
    "loc_ben_flat": ["loc_village_square"],
    "loc_pub": ["loc_village_square"],
    "loc_ruth_cottage": ["loc_village_square"],
    "loc_solicitors_office": ["loc_village_square"],
    "loc_fishery": ["loc_village_square"],
    "loc_lake": ["loc_village_square"],
    "loc_woodland": ["loc_village_square"],
    "loc_meadow": ["loc_village_square"],
}

LOCATION_FUNCTION_TAGS: dict[str, dict[str, Any]] = {
    "loc_village_square": {"display_name": "Village Square", "function_tag": "public_square", "building_role": "landmark", "case_ids": ["case_001", "case_002", "case_003", "case_004", "case_005", "case_006"], "zoom_behavior": "external"},
    "loc_fountain": {"display_name": "Village Fountain", "function_tag": "fountain", "building_role": "landmark", "case_ids": ["case_001", "case_002", "case_003", "case_004", "case_005"], "zoom_behavior": "external"},
    "loc_elias_bench": {"display_name": "Elias's Bench", "function_tag": "bench", "building_role": "landmark", "case_ids": ["case_003"], "zoom_behavior": "external"},
    "loc_hobbs_cafe": {"display_name": "Hobbs Cafe", "function_tag": "cafe", "building_role": "business", "case_ids": ["case_001", "case_002", "case_003", "case_005"], "zoom_behavior": "external_to_internal"},
    "loc_cafe_kitchen": {"display_name": "Cafe Kitchen", "function_tag": "kitchen", "building_role": "service_room", "case_ids": ["case_001"], "parent_location_id": "loc_hobbs_cafe", "zoom_behavior": "internal"},
    "loc_cafe_storage": {"display_name": "Cafe Storage Room", "function_tag": "storage", "building_role": "service_room", "case_ids": ["case_001"], "parent_location_id": "loc_hobbs_cafe", "zoom_behavior": "internal"},
    "loc_clara_flat": {"display_name": "Clara's Flat", "function_tag": "flat", "building_role": "residence", "case_ids": ["case_001", "case_003", "case_005"], "parent_location_id": "loc_hobbs_cafe", "zoom_behavior": "internal"},
    "loc_bookshop": {"display_name": "Reed & Bell Bookshop", "function_tag": "bookshop", "building_role": "business", "case_ids": ["case_001", "case_002", "case_005", "case_006"], "zoom_behavior": "external_to_internal"},
    "loc_bookshop_back": {"display_name": "Bookshop Back Room", "function_tag": "back_office", "building_role": "service_room", "case_ids": ["case_002"], "parent_location_id": "loc_bookshop", "zoom_behavior": "internal"},
    "loc_rear_alley": {"display_name": "Rear Alley", "function_tag": "service_alley", "building_role": "exterior_service", "case_ids": ["case_001", "case_002", "case_005"], "zoom_behavior": "external"},
    "loc_clinic": {"display_name": "Village Clinic", "function_tag": "clinic", "building_role": "public_service", "case_ids": ["case_001", "case_002", "case_003", "case_004", "case_005", "case_006"], "zoom_behavior": "external_to_internal"},
    "loc_clinic_dispensary": {"display_name": "Clinic Dispensary", "function_tag": "dispensary", "building_role": "service_room", "case_ids": ["case_003"], "parent_location_id": "loc_clinic", "zoom_behavior": "internal"},
    "loc_marcus_house": {"display_name": "Marcus Bell's House", "function_tag": "house", "building_role": "residence", "case_ids": ["case_001", "case_006"], "zoom_behavior": "external_to_internal"},
    "loc_marcus_study": {"display_name": "Marcus's Study", "function_tag": "study", "building_role": "private_room", "case_ids": ["case_006"], "parent_location_id": "loc_marcus_house", "zoom_behavior": "internal"},
    "loc_owen_house": {"display_name": "Owen Price's House & Yard", "function_tag": "house_and_yard", "building_role": "residence_workyard", "case_ids": ["case_001", "case_002", "case_003", "case_004", "case_005"], "zoom_behavior": "external_to_internal"},
    "loc_pub": {"display_name": "The Mallet & Crown", "function_tag": "pub", "building_role": "business", "case_ids": ["case_004"], "zoom_behavior": "external_to_internal"},
    "loc_ben_flat": {"display_name": "Ben's Flat", "function_tag": "flat", "building_role": "residence", "case_ids": ["case_004"], "zoom_behavior": "internal"},
    "loc_priya_flat": {"display_name": "Priya's Flat", "function_tag": "flat", "building_role": "residence", "case_ids": ["case_001", "case_002", "case_004", "case_006"], "zoom_behavior": "internal"},
    "loc_nadia_flat": {"display_name": "Nadia's Flat", "function_tag": "flat", "building_role": "residence", "case_ids": ["case_001"], "zoom_behavior": "internal"},
    "loc_elias_house": {"display_name": "Elias's Cottage", "function_tag": "cottage", "building_role": "residence", "case_ids": ["case_001", "case_004"], "zoom_behavior": "external_to_internal"},
    "loc_ruth_cottage": {"display_name": "Ruth's Cottage", "function_tag": "cottage", "building_role": "residence_garden", "case_ids": ["case_006"], "zoom_behavior": "external_to_internal"},
    "loc_solicitors_office": {"display_name": "Whittle & Cross Solicitors", "function_tag": "solicitors_office", "building_role": "office", "case_ids": ["case_006"], "zoom_behavior": "external_to_internal"},
    "loc_fishery": {"display_name": "Fishery", "function_tag": "fishery", "building_role": "exterior_worksite", "case_ids": ["case_004"], "zoom_behavior": "external"},
    "loc_lake": {"display_name": "Lover's Lake", "function_tag": "lake", "building_role": "landmark", "case_ids": ["case_004"], "zoom_behavior": "external"},
    "loc_woodland": {"display_name": "Whispering Woodland", "function_tag": "woodland", "building_role": "landmark", "case_ids": ["case_004"], "zoom_behavior": "external"},
    "loc_meadow": {"display_name": "Green Meadow", "function_tag": "meadow", "building_role": "landmark", "case_ids": ["case_004"], "zoom_behavior": "external"},
}


def _tagged_location_payload(
    location_id: str,
    position: dict[str, int],
    bounds: dict[str, int],
    layer: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"bounds": bounds, "position": position, "layer": layer}
    tag = LOCATION_FUNCTION_TAGS.get(location_id)
    if tag:
        payload.update(tag)
    return payload


# Semantic asset IDs are visual-only. Existing object IDs remain the state
# keys. The renderer can start with glyph/CSS placeholders and later swap in
# raster prop assets without changing case logic.
SEMANTIC_ASSETS: dict[str, dict[str, Any]] = {
    "loc_village_square": {"category": "location", "asset": "struct_village_square"},
    "loc_fountain": {"category": "location", "asset": "prop_fountain_coping"},
    "loc_hobbs_cafe": {"category": "location", "asset": "struct_hobbs_cafe_cutaway"},
    "loc_cafe_kitchen": {"category": "location", "asset": "struct_cafe_kitchen_cutaway"},
    "loc_cafe_storage": {"category": "location", "asset": "struct_cafe_storage_cutaway"},
    "loc_fishery": {"category": "location", "asset": "struct_fishery"},
    "loc_lake": {"category": "location", "asset": "struct_lake"},
    "loc_woodland": {"category": "location", "asset": "struct_woodland"},
    "loc_meadow": {"category": "location", "asset": "struct_meadow"},
    "obj_fountain_stone": {"category": "evidence", "asset": "obj_fountain_coping_stone", "glyph": "◆"},
    "obj_blackmail_letters": {"category": "evidence", "asset": "obj_blackmail_letters", "glyph": "✉"},
    "obj_ben_phone": {"category": "evidence", "asset": "obj_phone", "glyph": "☎"},
    "obj_owen_pub_receipt": {"category": "evidence", "asset": "obj_pub_receipt", "glyph": "▤"},
    "obj_mud_bootprint": {"category": "evidence", "asset": "obj_muddy_bootprint", "glyph": "●"},
    "obj_arson_clipping": {"category": "evidence", "asset": "obj_arson_clipping", "glyph": "▤"},
    "obj_ben_jacket_mud": {"category": "evidence", "asset": "obj_muddy_jacket", "glyph": "◆"},
    "obj_fred_lighter": {"category": "evidence", "asset": "obj_pub_lighter", "glyph": "✦"},
    "obj_pub_ledger": {"category": "evidence", "asset": "obj_pub_ledger", "glyph": "▤"},
}

OBJECT_OVERLAYS: dict[str, list[str]] = {
    "obj_fountain_stone": ["overlay_missing_coping"],
    "obj_mud_bootprint": ["overlay_muddy_footprint"],
}


CASE_MAPS: dict[str, dict[str, Any]] = {
    "case_004": {
        "mode": "canonical_overworld",
        "map": CANONICAL_MAP,
        "visible_location_ids": [
            "loc_village_square", "loc_fountain", "loc_pub", "loc_owen_house",
            "loc_clinic", "loc_elias_house", "loc_priya_flat", "loc_ben_flat",
        ],
        "overlays": [
            "overlay_case_004_runtime_lighting",
            "overlay_missing_coping",
            "overlay_muddy_footprint",
        ],
        "crop_padding_by_location": {
            "loc_village_square": 2.1,
            "loc_fountain": 2.0,
            "loc_pub": 2.55,
            "loc_ben_flat": 2.2,
            "loc_priya_flat": 2.2,
        },
    }
}

# The temporary daylight pilot image is a versioned reference asset, not a
# canonical tilemap. These bounds are measured in its 1448x1086 image space
# and scaled to the canonical 2048x1536 response space. This keeps Places and
# Map Replay aligned with the actual buildings while the full canonical art
# library is still pending.
_PILOT_SOURCE_SIZE = (1448, 1086)
_PILOT_SOURCE_BOUNDS: dict[str, tuple[int, int, int, int]] = {
    "loc_village_square": (50, 350, 925, 360),
    "loc_fountain": (605, 420, 245, 205),
    "loc_pub": (82, 66, 450, 395),
    "loc_clinic": (760, 16, 375, 320),
    "loc_owen_house": (975, 350, 300, 390),
    "loc_elias_house": (205, 710, 190, 245),
    "loc_priya_flat": (380, 710, 190, 245),
    "loc_ben_flat": (700, 710, 270, 245),
}


def _scale_pilot_bounds(bounds: tuple[int, int, int, int]) -> dict[str, int]:
    sx = CANONICAL_MAP["width"] / _PILOT_SOURCE_SIZE[0]
    sy = CANONICAL_MAP["height"] / _PILOT_SOURCE_SIZE[1]
    x, y, width, height = bounds
    return {
        "x": round(x * sx),
        "y": round(y * sy),
        "width": round(width * sx),
        "height": round(height * sy),
    }


def pilot_location_visuals(location_id: str) -> tuple[dict[str, int] | None, dict[str, int] | None, str | None]:
    # Check if a dynamic validated layout exists
    layout = load_town_layout()
    if layout:
        case_override = layout.get("case_overrides", {}).get("case_004", {})
        visible_locations = case_override.get("visible_locations", [])
        if location_id in visible_locations:
            bounds_override = case_override.get("location_bounds", {}).get(location_id)
            if bounds_override:
                x, y, w, h = bounds_override["x"], bounds_override["y"], bounds_override["w"], bounds_override["h"]
                px_bounds = {"x": x * 32, "y": y * 32, "width": w * 32, "height": h * 32}
                px_pos = _center(px_bounds)
                layer = "exterior"
                canonical_loc_data = layout.get("canonical_locations", {}).get(location_id)
                if canonical_loc_data and "mode" in canonical_loc_data:
                    layer = canonical_loc_data["mode"]
                elif location_id in {
                    "loc_cafe_kitchen", "loc_cafe_storage", "loc_bookshop_back",
                    "loc_clinic_dispensary", "loc_marcus_study", "loc_clara_flat",
                    "loc_ben_flat", "loc_priya_flat", "loc_nadia_flat"
                }:
                    layer = "interior"
                return px_pos, px_bounds, layer
                
            canonical_loc_data = layout.get("canonical_locations", {}).get(location_id)
            if canonical_loc_data and "bounds" in canonical_loc_data:
                b = canonical_loc_data["bounds"]
                x, y, w, h = b["x"], b["y"], b["w"], b["h"]
                px_bounds = {"x": x * 32, "y": y * 32, "width": w * 32, "height": h * 32}
                px_pos = _center(px_bounds)
                layer = canonical_loc_data.get("mode", "exterior")
                return px_pos, px_bounds, layer

    # Default fallback to existing pilot bounds
    source_bounds = _PILOT_SOURCE_BOUNDS.get(location_id)
    if not source_bounds:
        return canonical_location_visuals(location_id)
    bounds = _scale_pilot_bounds(source_bounds)
    return _center(bounds), bounds, "interior" if location_id in {
        "loc_pub", "loc_ben_flat", "loc_priya_flat", "loc_elias_house"
    } else "exterior"


def map_config(case_id: str) -> dict[str, Any] | None:
    return CASE_MAPS.get(case_id)


def _clue_ids_by_object(case: CaseData) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for clue in case.clues:
        for object_id in clue.linked_object_ids or []:
            result.setdefault(object_id, []).append(clue.clue_id)
    return result


def pilot_objects(
    case: CaseData,
    discovered_clue_ids: set[str],
    visible_location_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return safe Case 004 visual object states.

    A visible-but-undiscovered object is deliberately suppressed: the map
    knows the semantic anchor exists, but the client receives no evidence
    marker to render. A discovered state is only true when the existing clue
    discovery session contains one of the object's linked clue IDs.
    """
    if case.case.case_id != "case_004":
        return []
    
    # Load dynamic object anchors from town_layout.json if available
    layout = load_town_layout()
    overridden_anchors = {}
    if layout:
        overridden_anchors = layout.get("case_overrides", {}).get("case_004", {}).get("object_anchors", {})

    clue_ids = _clue_ids_by_object(case)
    objects = []
    for obj in case.objects:
        visual = SEMANTIC_ASSETS.get(obj.object_id)
        if not visual:
            continue
        location_id = obj.final_location_id or obj.normal_location_id
        location = CANONICAL_LOCATIONS.get(location_id or "")
        if not location:
            continue
        
        override = overridden_anchors.get(obj.object_id)
        if override and "anchor" in override:
            ax, ay = override["anchor"]["x"], override["anchor"]["y"]
            anchor_pos = {"x": ax * 32, "y": ay * 32}
        else:
            _, pilot_bounds, _ = pilot_location_visuals(location_id or "")
            object_bounds = pilot_bounds or location["bounds"]
            anchor_pos = _object_position(obj.object_id, object_bounds)
            
        linked = clue_ids.get(obj.object_id, [])
        discovered = any(clue_id in discovered_clue_ids for clue_id in linked)
        location_visible = visible_location_ids is None or location_id in visible_location_ids
        state = "discovered" if discovered else ("visible" if location_visible else "hidden")
        marker_state = "active" if discovered else "suppressed"
        
        objects.append({
            "object_id": obj.object_id,
            "semantic_asset_id": override.get("semantic_asset_id", visual["asset"]) if override else visual["asset"],
            "category": visual["category"],
            "location_id": location_id,
            "anchor": anchor_pos,
            "position": anchor_pos,
            "state": state,
            "marker_state": marker_state,
            "render_mode": "evidence_marker" if discovered else "suppressed",
            "safe_to_render": discovered,
            "glyph": visual.get("glyph"),
            "clue_ids": linked,
            "overlay_ids": OBJECT_OVERLAYS.get(obj.object_id, []),
            "damaged": obj.object_id in {"obj_fountain_stone", "obj_mud_bootprint"},
        })
    return objects


def _object_position(object_id: str, bounds: dict[str, int]) -> dict[str, int]:
    offsets = {
        "obj_fountain_stone": (bounds["width"] - 42, bounds["height"] // 2),
        "obj_mud_bootprint": (bounds["width"] // 2 + 34, bounds["height"] - 28),
        "obj_owen_pub_receipt": (bounds["width"] // 2 - 8, bounds["height"] // 2),
        "obj_fred_lighter": (bounds["width"] // 2 + 28, bounds["height"] + 18),
        "obj_blackmail_letters": (bounds["width"] // 2 - 20, bounds["height"] // 2),
        "obj_arson_clipping": (bounds["width"] // 2 + 22, bounds["height"] // 2),
        "obj_ben_phone": (bounds["width"] - 34, bounds["height"] // 2 - 24),
        "obj_ben_jacket_mud": (bounds["width"] // 2, bounds["height"] - 24),
        "obj_pub_ledger": (22, bounds["height"] // 2 - 16),
    }
    dx, dy = offsets.get(object_id, (bounds["width"] // 2, bounds["height"] // 2))
    return {"x": bounds["x"] + dx, "y": bounds["y"] + dy}


def map_payload(case: CaseData, discovered_clue_ids: set[str]) -> dict[str, Any]:
    """Return the visual-only contract for the active case."""
    config = map_config(case.case.case_id)
    if not config:
        return {
            "mode": "legacy_fallback",
            "definition_id": "legacy_the_ville",
            "visible_location_ids": None,
            "overlays": [],
            "objects": [],
            "adjacency": {},
            "canonical_locations": {},
        }
        
    layout = load_town_layout()
    visible_location_ids_list = config["visible_location_ids"]
    if layout:
        case_override = layout.get("case_overrides", {}).get(case.case.case_id, {})
        if "visible_locations" in case_override:
            visible_location_ids_list = case_override["visible_locations"]

    visible_location_ids = set(visible_location_ids_list)
    object_visuals = pilot_objects(case, discovered_clue_ids, visible_location_ids)
    
    canonical_locations_dict = {}
    for loc_id in visible_location_ids_list:
        pos, bounds, layer = pilot_location_visuals(loc_id)
        if pos and bounds:
            canonical_locations_dict[loc_id] = _tagged_location_payload(loc_id, pos, bounds, layer)
        elif loc_id in CANONICAL_LOCATIONS:
            location = CANONICAL_LOCATIONS[loc_id]
            canonical_locations_dict[loc_id] = _tagged_location_payload(
                loc_id,
                location["position"],
                location["bounds"],
                location["layer"],
            )

    return {
        "mode": config["mode"],
        "definition_id": config["map"]["definition_id"],
        "visible_location_ids": visible_location_ids_list,
        "overlays": config["overlays"],
        "crop_padding_by_location": config.get("crop_padding_by_location", {}),
        "object_visuals": object_visuals,
        "objects": object_visuals,
        "adjacency": {k: v for k, v in CANONICAL_ADJACENCY.items() if k in visible_location_ids},
        "canonical_locations": canonical_locations_dict,
    }


def canonical_location_visuals(location_id: str) -> tuple[dict[str, int] | None, dict[str, int] | None, str | None]:
    location = CANONICAL_LOCATIONS.get(location_id)
    if not location:
        return None, None, None
    return location["position"], location["bounds"], location["layer"]
