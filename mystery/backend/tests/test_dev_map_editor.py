import os
import json
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.town_map import validate_town_layout_payload
from app.place_library import create_building_instance, dress_building, load_building_library, location_art_asset
from app.case_store import get_case
from app.projections import project_location


def test_building_library_bundles_and_dressing_are_deterministic():
    library = load_building_library()
    assert {"cafe_small_v1", "clinic_small_v1", "flats_two_storey_v1", "pub_small_v1", "cottage_small_v1"} <= set(library["buildings"])

    building = library["buildings"]["cafe_small_v1"]
    dressed = dress_building(building, 20, 30)
    assert dressed["structures"]
    assert any(tile["tile_id"] == "tile_path" for tile in dressed["paths"])
    assert dressed == dress_building(building, 20, 30)

    instance = create_building_instance("clinic_small_v1", 40, 50, instance_id="clinic_main", location_id="loc_clinic")
    assert instance["exterior_asset"].endswith("clinic_small_v1_exterior.png")
    assert instance["interior_asset"].endswith("clinic_small_v1_interior.png")
    assert instance["derived_tiles"]["structures"]

    filler = library["buildings"]["filler_barn_medium_v1"]
    assert filler["filler"] is True
    assert filler["investigable"] is False
    assert filler["interior_asset"].endswith("filler_barn_medium_v1_interior.png")
    assert location_art_asset("loc_hobbs_cafe", "external").endswith("cafe_small_v1_exterior.png")
    assert location_art_asset("loc_hobbs_cafe", "internal").endswith("cafe_small_v1_interior.png")
    assert location_art_asset("loc_clara_flat", "internal").endswith("clara_flat_interior_production.png")
    cafe = next(loc for loc in get_case("case_001").locations if loc.location_id == "loc_hobbs_cafe")
    assert project_location(cafe)["illustration"].endswith("cafe_small_v1_exterior.png")


def test_dev_map_editor_endpoint_gating():
    client = TestClient(app)
    
    # Force disable
    os.environ["ENABLE_DEV_MAP_EDITOR"] = "false"
    
    response_get = client.get("/api/dev/map-editor/layout")
    assert response_get.status_code == 403
    
    response_post = client.post("/api/dev/map-editor/layout", json={})
    assert response_post.status_code == 403
    
    # Enable editor
    os.environ["ENABLE_DEV_MAP_EDITOR"] = "true"
    
    response_get_ok = client.get("/api/dev/map-editor/layout")
    assert response_get_ok.status_code == 200


def test_validate_town_layout_payload_constraints_v2():
    # Valid payload base structure
    valid_payload = {
        "version": "town_layout_editor_v2",
        "grid": {"cols": 192, "rows": 144, "tile_size": 32},
        "canonical_locations": {
            "loc_fountain": {
                "bounds": {"x": 93, "y": 67, "w": 10, "h": 9},
                "mode": "exterior"
            },
            "loc_village_square": {
                "bounds": {"x": 82, "y": 62, "w": 28, "h": 16}, # Completely overlaps / contains loc_fountain
                "mode": "exterior"
            }
        },
        "case_overrides": {
            "case_004": {
                "visible_locations": ["loc_fountain", "loc_village_square"],
                "location_bounds": {},
                "object_anchors": {
                    "obj_fountain_stone": {
                        "location_id": "loc_fountain",
                        "anchor": {"x": 100, "y": 71},
                        "semantic_asset_id": "obj_fountain_coping_stone",
                        "render_policy": "discovery_gated"
                    }
                }
            }
        },
        "tile_layers": {
            "base": {
                "tiles": [
                    {"x": 74, "y": 62, "tile_id": "tile_cobble"}
                ]
            }
        },
        "prop_instances": {
            "canonical": [
                {
                    "instance_id": "prop_fountain_main_001",
                    "asset_id": "prop_fountain_coping",
                    "location_id": "loc_fountain",
                    "x": 96,
                    "y": 70,
                    "w": 5,
                    "h": 5,
                    "layer": "props"
                }
            ],
            "case_004": [
                {
                    "instance_id": "case004_bootprint_001",
                    "asset_id": "prop_muddy_footprint",
                    "object_id": "obj_mud_bootprint",
                    "location_id": "loc_fountain",
                    "x": 99,
                    "y": 72,
                    "render_policy": "discovery_gated"
                }
            ]
        }
    }
    
    # Should validate clean (village square contains fountain, which is an allowed nesting pairing)
    errors = validate_town_layout_payload(valid_payload)
    assert not errors, f"Should be valid, got errors: {errors}"
    
    # 1. Invalid version
    bad_payload = dict(valid_payload)
    bad_payload["version"] = "town_layout_editor_v1"
    errors = validate_town_layout_payload(bad_payload)
    assert any("version" in e.lower() for e in errors)
    
    # 2. Location overlaps without allowed nesting
    bad_payload = dict(valid_payload)
    bad_payload["canonical_locations"] = {
        "loc_fountain": {
            "bounds": {"x": 93, "y": 67, "w": 10, "h": 9},
            "mode": "exterior"
        },
        "loc_clinic": {
            "bounds": {"x": 94, "y": 68, "w": 5, "h": 5}, # Overlaps with fountain, not allowed nesting pair
            "mode": "exterior"
        }
    }
    errors = validate_town_layout_payload(bad_payload)
    assert any("overlap detected" in e.lower() for e in errors)

    # 3. Invalid Layer Name
    bad_payload = dict(valid_payload)
    bad_payload["tile_layers"] = {
        "unsupported_layer_name": {
            "tiles": [{"x": 10, "y": 14, "tile_id": "tile_cobble"}]
        }
    }
    errors = validate_town_layout_payload(bad_payload)
    assert any("unknown layer name" in e.lower() for e in errors)

    # 4. Unknown Tile ID
    bad_payload = dict(valid_payload)
    bad_payload["tile_layers"] = {
        "base": {
            "tiles": [{"x": 10, "y": 14, "tile_id": "unknown_tile_type"}]
        }
    }
    errors = validate_town_layout_payload(bad_payload)
    assert any("unknown tile id" in e.lower() for e in errors)

    # 5. Duplicate Prop Instance ID
    bad_payload = dict(valid_payload)
    bad_payload["prop_instances"] = {
        "canonical": [
            {
                "instance_id": "prop_fountain_main_001",
                "asset_id": "prop_fountain_coping",
                "location_id": "loc_fountain",
                "x": 96,
                "y": 70
            },
            {
                "instance_id": "prop_fountain_main_001", # Duplicate
                "asset_id": "prop_bench",
                "location_id": "loc_fountain",
                "x": 97,
                "y": 70
            }
        ]
    }
    errors = validate_town_layout_payload(bad_payload)
    assert any("duplicate prop instance id" in e.lower() for e in errors)

    # 6. Discovery-gated prop lacks object_id
    bad_payload = dict(valid_payload)
    bad_payload["prop_instances"] = {
        "case_004": [
            {
                "instance_id": "case004_bootprint_001",
                "asset_id": "prop_muddy_footprint",
                "location_id": "loc_fountain",
                "x": 99,
                "y": 72,
                "render_policy": "discovery_gated" # No object_id
            }
        ]
    }
    errors = validate_town_layout_payload(bad_payload)
    assert any("lacks a linked object_id" in e.lower() for e in errors)


def test_underlay_tile_override_validation():
    from app.town_map import HD_TILE_CELLS

    base = {
        "version": "town_layout_editor_v2",
        "grid": {"cols": 192, "rows": 144, "tile_size": 32},
        "canonical_locations": {},
        "case_overrides": {},
        "tile_layers": {},
        "prop_instances": {},
    }
    assert HD_TILE_CELLS == ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]

    # Valid per-view overrides pass clean
    ok = dict(base)
    ok["underlay_tile_overrides"] = {
        "external": {"B2": "/art/town/tiles_3x3_hd/town_overworld_B2_blank_hd.png"},
        "internal": {"B2": "/art/town/tiles_3x3_hd/town_overworld_B2_blank_hd.png"},
    }
    assert not validate_town_layout_payload(ok)

    # Unknown view
    bad = dict(base)
    bad["underlay_tile_overrides"] = {"sideways": {"B2": "/art/x.png"}}
    assert any("unknown view" in e.lower() for e in validate_town_layout_payload(bad))

    # Unknown cell
    bad["underlay_tile_overrides"] = {"external": {"D4": "/art/x.png"}}
    assert any("mosaic cell" in e.lower() for e in validate_town_layout_payload(bad))

    # URL outside /art/ or not a PNG
    bad["underlay_tile_overrides"] = {"external": {"B2": "https://evil.example/x.png"}}
    assert any("/art/" in e for e in validate_town_layout_payload(bad))
    bad["underlay_tile_overrides"] = {"external": {"B2": "/art/town/x.svg"}}
    assert any("/art/" in e for e in validate_town_layout_payload(bad))


def test_canonical_map_definition_applies_tile_overrides():
    from app.town_map import CANONICAL_MAP, canonical_map_definition

    blank = "/art/town/tiles_3x3_hd/town_overworld_B2_blank_hd.png"
    layout = {
        "underlay_tile_overrides": {
            "external": {"B2": blank, "A1": "/art/town/tiles_3x3_hd/custom_A1.png"},
            "internal": {"B2": blank},
        }
    }
    definition = canonical_map_definition(layout)
    assert definition["image_tiles"]["urls"][1][1] == blank
    assert definition["image_tiles"]["urls"][0][0] == "/art/town/tiles_3x3_hd/custom_A1.png"
    assert definition["zoom_image_tiles"]["urls"][1][1] == blank
    # Untouched cells keep the defaults; CANONICAL_MAP itself is never mutated
    assert definition["image_tiles"]["urls"][2][2] == CANONICAL_MAP["image_tiles"]["urls"][2][2]
    assert CANONICAL_MAP["image_tiles"]["urls"][1][1].endswith("all_cases_external_hd.png")

    # No overrides -> the shared definition is returned unchanged
    assert canonical_map_definition({}) is CANONICAL_MAP


def test_dress_building_rotation():
    building = {
        "footprint": {"w": 4, "h": 3},
        "surrounding_rules": {"front": "path", "sides": "fence", "rear": "service_path"},
    }
    cells = lambda tiles: {(t["x"], t["y"]) for t in tiles}

    r0 = dress_building(building, 20, 30)
    assert cells(r0["structures"]) == {(20 + dx, 30 + dy) for dx in range(4) for dy in range(3)}
    # Door faces south: 2-deep front path below, 1-deep service path above.
    assert cells(r0["paths"]) == {(20 + dx, 33 + dy) for dx in range(4) for dy in range(2)} | {(20 + dx, 29) for dx in range(4)}
    assert cells(r0["terrain_detail"]) == {(19, 30 + dy) for dy in range(3)} | {(24, 30 + dy) for dy in range(3)}

    r90 = dress_building(building, 20, 30, rotation=90)
    # Footprint swaps to 3x4 and the whole dressing rotates: front west, rear east, sides north/south.
    assert cells(r90["structures"]) == {(20 + dx, 30 + dy) for dx in range(3) for dy in range(4)}
    assert cells(r90["paths"]) == {(18 + dx, 30 + dy) for dx in range(2) for dy in range(4)} | {(23, 30 + dy) for dy in range(4)}
    assert cells(r90["terrain_detail"]) == {(20 + dx, 29) for dx in range(3)} | {(20 + dx, 34) for dx in range(3)}

    r180 = dress_building(building, 20, 30, rotation=180)
    assert cells(r180["structures"]) == cells(r0["structures"])
    assert cells(r180["paths"]) == {(20 + dx, 28 + dy) for dx in range(4) for dy in range(2)} | {(20 + dx, 33) for dx in range(4)}

    r270 = dress_building(building, 20, 30, rotation=270)
    assert cells(r270["paths"]) == {(23 + dx, 30 + dy) for dx in range(2) for dy in range(4)} | {(19, 30 + dy) for dy in range(4)}

    assert dress_building(building, 20, 30, rotation=90) == r90


def test_tile_art_variants_listing():
    from app.town_map import list_hd_tile_variants

    os.environ["ENABLE_DEV_MAP_EDITOR"] = "true"
    variants = list_hd_tile_variants()
    b2_urls = [v["url"] for v in variants["B2"]]
    assert "/art/town/tiles_3x3_hd/town_overworld_B2_blank_hd.png" in b2_urls
    assert all(url.startswith("/art/town/tiles_3x3_hd/") for urls in variants.values() for url in [u["url"] for u in urls])

    client = TestClient(app)
    data = client.get("/api/dev/map-editor/layout").json()
    assert data["tile_art_variants"]["B2"] == variants["B2"]
