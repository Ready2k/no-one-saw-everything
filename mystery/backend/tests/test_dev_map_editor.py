import os
import json
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.town_map import validate_town_layout_payload


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
        "grid": {"cols": 64, "rows": 48, "tile_size": 32},
        "canonical_locations": {
            "loc_fountain": {
                "bounds": {"x": 29, "y": 19, "w": 10, "h": 9},
                "mode": "exterior"
            },
            "loc_village_square": {
                "bounds": {"x": 18, "y": 14, "w": 28, "h": 16}, # Completely overlaps / contains loc_fountain
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
                        "anchor": {"x": 36, "y": 23},
                        "semantic_asset_id": "obj_fountain_coping_stone",
                        "render_policy": "discovery_gated"
                    }
                }
            }
        },
        "tile_layers": {
            "base": {
                "tiles": [
                    {"x": 10, "y": 14, "tile_id": "tile_cobble"}
                ]
            }
        },
        "prop_instances": {
            "canonical": [
                {
                    "instance_id": "prop_fountain_main_001",
                    "asset_id": "prop_fountain_coping",
                    "location_id": "loc_fountain",
                    "x": 32,
                    "y": 22,
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
                    "x": 35,
                    "y": 24,
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
            "bounds": {"x": 29, "y": 19, "w": 10, "h": 9},
            "mode": "exterior"
        },
        "loc_clinic": {
            "bounds": {"x": 30, "y": 20, "w": 5, "h": 5}, # Overlaps with fountain, not allowed nesting pair
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
                "x": 32,
                "y": 22
            },
            {
                "instance_id": "prop_fountain_main_001", # Duplicate
                "asset_id": "prop_bench",
                "location_id": "loc_fountain",
                "x": 33,
                "y": 22
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
                "x": 35,
                "y": 24,
                "render_policy": "discovery_gated" # No object_id
            }
        ]
    }
    errors = validate_town_layout_payload(bad_payload)
    assert any("lacks a linked object_id" in e.lower() for e in errors)
