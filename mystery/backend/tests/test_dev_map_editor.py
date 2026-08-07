import os
import json
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.town_map import load_town_layout, validate_town_layout_payload
from app.place_library import create_building_instance, dress_building, load_building_library, location_art_asset


def test_building_library_bundles_and_dressing_are_deterministic():
    library = load_building_library()
    assert {"cafe_small_v1", "clinic_small_v1", "flats_two_storey_v1", "pub_small_v1", "cottage_small_v1"} <= set(library["buildings"])

    building = library["buildings"]["cafe_small_v1"]
    dressed = dress_building(building, 20, 30)
    assert dressed["structures"]
    assert any(tile["tile_id"] == "tile_path" for tile in dressed["paths"])
    assert dressed == dress_building(building, 20, 30)

    instance = create_building_instance("clinic_small_v1", 40, 50, instance_id="clinic_main", location_id="loc_clinic")
    assert instance["exterior_asset"].endswith("clinic_small_v1_exterior.avif")
    assert instance["interior_asset"].endswith("clinic_small_v1_interior.avif")
    assert instance["derived_tiles"]["structures"]

    filler = library["buildings"]["filler_barn_medium_v1"]
    assert filler["filler"] is True
    assert filler["investigable"] is False
    assert filler["interior_asset"].endswith("filler_barn_medium_v1_interior.avif")
    assert location_art_asset("loc_hobbs_cafe", "external").endswith("cafe_small_v1_exterior.avif")
    assert location_art_asset("loc_hobbs_cafe", "internal").endswith("cafe_small_v1_interior.avif")
    assert location_art_asset("loc_clara_flat", "internal").endswith("clara_flat_interior_production.avif")
    # The Places *search* illustration is a different art surface from the map
    # stamps above, and now comes from the shared modern scene library rather
    # than the building bundle — so it is no longer this test's business.
    # test_town_map_pilot.py::test_every_place_has_search_art_that_exists_on_disk
    # owns it, across every case rather than this one location.


def test_dev_map_editor_endpoint_gating():
    client = TestClient(app)
    
    # Force disable
    os.environ["ENABLE_DEV_MAP_EDITOR"] = "false"
    assert client.get("/api/config").json()["dev_map_editor_enabled"] is False
    
    response_get = client.get("/api/dev/map-editor/layout")
    assert response_get.status_code == 403
    
    response_post = client.post("/api/dev/map-editor/layout", json={})
    assert response_post.status_code == 403
    
    # Enable editor
    os.environ["ENABLE_DEV_MAP_EDITOR"] = "true"
    assert client.get("/api/config").json()["dev_map_editor_enabled"] is True
    
    response_get_ok = client.get("/api/dev/map-editor/layout")
    assert response_get_ok.status_code == 200


def test_editor_exposes_scenario_expansion_buildings(monkeypatch):
    monkeypatch.setenv("ENABLE_DEV_MAP_EDITOR", "true")

    data = TestClient(app).get("/api/dev/map-editor/layout").json()
    buildings = data["building_library"]["buildings"]

    assert buildings["st_alder_church_v1"]["interior_asset"].endswith("st_alder_church_interior_map_hd.avif")
    assert buildings["willow_farmhouse_v1"]["exterior_asset"].endswith("willow_farmhouse_exterior_map_stamp_hd.avif")
    assert data["canonical_recommended_locations"]["loc_st_alder_church"]["bounds"] == {
        "x": 67, "y": 36, "w": 18, "h": 15,
    }


def test_save_conflict_detection(tmp_path, monkeypatch):
    """Two sessions loading the same layout and saving around the same time
    must not silently clobber each other — the second save should 409, not
    overwrite the first session's change with no way to recover it."""
    import app.town_map as town_map

    layout_file = tmp_path / "town_layout.json"
    monkeypatch.setattr(town_map, "TOWN_LAYOUT_FILE", layout_file)
    os.environ["ENABLE_DEV_MAP_EDITOR"] = "true"
    client = TestClient(app)

    base_payload = {
        "version": "town_layout_editor_v2",
        "grid": {"cols": 192, "rows": 144, "tile_size": 32},
        "canonical_locations": {},
        "case_overrides": {},
        "tile_layers": {},
        "prop_instances": {},
        "building_instances": [],
        "lights": {},
    }

    # Both sessions load the same (nonexistent-yet) starting state.
    v0 = client.get("/api/dev/map-editor/layout").json()["layout_version"]

    # Session A saves first — should succeed, and its new version differs.
    res_a = client.post(
        "/api/dev/map-editor/layout",
        json={**base_payload, "prop_instances": {"canonical": []}},
        headers={"X-Base-Layout-Version": v0},
    )
    assert res_a.status_code == 200
    v1 = res_a.json()["layout_version"]
    assert v1 != v0

    # Session B, still holding the stale v0 it loaded before A's save,
    # attempts to save — must be rejected, not silently overwrite A's change.
    res_b = client.post(
        "/api/dev/map-editor/layout",
        json={**base_payload, "building_instances": []},
        headers={"X-Base-Layout-Version": v0},
    )
    assert res_b.status_code == 409

    # A's change is still intact on disk.
    assert json.loads(layout_file.read_text())["prop_instances"] == {"canonical": []}

    # Session B reloads (picks up v1) and saves again — now succeeds.
    res_b_retry = client.post(
        "/api/dev/map-editor/layout",
        json={**base_payload, "building_instances": []},
        headers={"X-Base-Layout-Version": v1},
    )
    assert res_b_retry.status_code == 200

    # Omitting the header entirely (older client, or an intentional force-save) still works.
    res_force = client.post("/api/dev/map-editor/layout", json=base_payload)
    assert res_force.status_code == 200


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
    from app.town_map import (
        B2_LIVING_TOWN_V2_EXTERNAL_URL,
        B2_LIVING_TOWN_V2_INTERNAL_URL,
        CANONICAL_MAP,
        LIVING_TOWN_V2_INTERNAL_TILE_URLS,
        LIVING_TOWN_V2_TILE_URLS,
        canonical_map_definition,
    )

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
    assert CANONICAL_MAP["image_tiles"]["urls"][0][0] == LIVING_TOWN_V2_TILE_URLS["A1"]
    assert CANONICAL_MAP["image_tiles"]["urls"][1][1] == B2_LIVING_TOWN_V2_EXTERNAL_URL
    assert CANONICAL_MAP["zoom_image_tiles"]["urls"][1][1] == B2_LIVING_TOWN_V2_INTERNAL_URL
    assert CANONICAL_MAP["zoom_image_tiles"]["urls"][0][1] == LIVING_TOWN_V2_INTERNAL_TILE_URLS["A2"]
    assert CANONICAL_MAP["zoom_image_tiles"]["urls"][0][1] != CANONICAL_MAP["image_tiles"]["urls"][0][1]

    # No overrides -> the shared definition is returned unchanged
    assert canonical_map_definition({}) is CANONICAL_MAP


def test_current_village_pub_and_solicitors_use_their_visible_plots():
    layout = load_town_layout()
    assert layout is not None

    assert layout["canonical_locations"]["loc_pub"]["bounds"] == {
        "x": 89, "y": 37, "w": 12, "h": 10,
    }
    assert layout["canonical_locations"]["loc_solicitors_office"]["bounds"] == {
        "x": 88, "y": 65, "w": 9, "h": 10,
    }

    ledger = layout["case_overrides"]["case_004"]["object_anchors"]["obj_pub_ledger"]
    assert ledger["location_id"] == "loc_pub"
    assert ledger["anchor"] == {"x": 95, "y": 43}

    pub = layout["canonical_locations"]["loc_pub"]["bounds"]
    for light_id in ("pub_window_left", "pub_window_right"):
        light = layout["lights"][light_id]
        assert pub["x"] <= light["x"] <= pub["x"] + pub["w"]
        assert pub["y"] <= light["y"] <= pub["y"] + pub["h"]


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


def test_light_validation():
    base = {
        "version": "town_layout_editor_v2",
        "grid": {"cols": 192, "rows": 144, "tile_size": 32},
        "canonical_locations": {},
        "case_overrides": {},
        "tile_layers": {},
        "prop_instances": {},
    }

    valid_light = {
        "location_id": "loc_pub",
        "semantic_asset_id": "light_window_warm",
        "x": 96.2, "y": 70.7, "width": 3.1, "height": 2.0,
        "from": "17:30", "to": "23:15", "opacity": 0.78,
        "x_internal": 105.6, "y_internal": 68.8, "width_internal": 3.4, "height_internal": 3.4,
        "semantic_asset_id_internal": "light_fireplace_glow", "opacity_internal": 0.8,
    }
    ok = dict(base)
    ok["lights"] = {"pub_window_left": valid_light}
    assert not validate_town_layout_payload(ok), validate_town_layout_payload(ok)

    # Unknown location_id
    bad = dict(base)
    bad["lights"] = {"x": {**valid_light, "location_id": "loc_does_not_exist"}}
    assert any("unknown location" in e.lower() for e in validate_town_layout_payload(bad))

    # Unknown semantic_asset_id
    bad["lights"] = {"x": {**valid_light, "semantic_asset_id": "light_disco_ball"}}
    assert any("semantic_asset_id" in e for e in validate_town_layout_payload(bad))

    # Non-positive width
    bad["lights"] = {"x": {**valid_light, "width": 0}}
    assert any("positive" in e.lower() for e in validate_town_layout_payload(bad))

    # Out-of-grid centre
    bad["lights"] = {"x": {**valid_light, "x": 999}}
    assert any("192x144 grid" in e for e in validate_town_layout_payload(bad))

    # Bad time format
    bad["lights"] = {"x": {**valid_light, "from": "5:30pm"}}
    assert any("'from' time" in e for e in validate_town_layout_payload(bad))

    # Opacity out of range
    bad["lights"] = {"x": {**valid_light, "opacity": 1.5}}
    assert any("opacity" in e.lower() for e in validate_town_layout_payload(bad))

    # Bad internal semantic_asset_id
    bad["lights"] = {"x": {**valid_light, "semantic_asset_id_internal": "light_disco_ball"}}
    assert any("semantic_asset_id_internal" in e for e in validate_town_layout_payload(bad))


def test_resolve_town_lights_scopes_by_visible_locations():
    from app.town_map import resolve_town_lights

    layout = {
        "lights": {
            "pub_glow": {
                "location_id": "loc_pub",
                "semantic_asset_id": "light_window_warm",
                "x": 96, "y": 70, "width": 3, "height": 2,
                "from": "17:30", "to": "23:15",
            },
            "clinic_glow": {
                "location_id": "loc_clinic",
                "semantic_asset_id": "light_window_cool",
                "x": 105, "y": 74, "width": 2, "height": 2,
                "from": "18:00", "to": "06:00",
            },
        }
    }

    # A case whose visible locations include the clinic but not the pub only
    # sees the clinic's light — this is the case_001/002 cross-bleed fix.
    resolved = resolve_town_lights(layout, {"loc_clinic"})
    assert [l["id"] for l in resolved] == ["clinic_glow"]
    assert resolved[0]["x"] == 105 * 32

    resolved_both = resolve_town_lights(layout, {"loc_pub", "loc_clinic"})
    assert {l["id"] for l in resolved_both} == {"pub_glow", "clinic_glow"}

    # No layout at all falls back to the hardcoded default list, still scoped.
    from app.town_map import TOWN_LIGHT_OVERLAYS
    fallback = resolve_town_lights(None, {l["location_id"] for l in TOWN_LIGHT_OVERLAYS})
    assert len(fallback) == len(TOWN_LIGHT_OVERLAYS)
    assert resolve_town_lights(None, set()) == []


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
