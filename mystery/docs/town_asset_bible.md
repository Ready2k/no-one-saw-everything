# Town Asset Bible

Status: design specification plus current runtime asset contract.

Implementation note: the Case 004 pilot now consumes a code-backed version of this contract from `backend/app/town_map.py`. The canonical overworld is a 3x3 HD tile mosaic under `frontend/public/art/town/tiles_3x3_hd/`. B2 is paired for zoom behavior: `town_overworld_B2_all_cases_external_hd.png` for overview/exterior and `town_overworld_B2_interior_hd.png` for close/interior. Discovered object glyphs remain temporary renderer hooks, not final art.

### Location function tags

Location functions are stored as metadata, not painted into the raster map. `LOCATION_FUNCTION_TAGS` in `backend/app/town_map.py` maps each existing `loc_*` ID to:

- `display_name`: human-facing label used for migration/debugging;
- `function_tag`: stable role such as `pub`, `clinic`, `bookshop`, `flat`, `cafe`, `fountain`, `service_alley`;
- `building_role`: broader category such as `business`, `residence`, `public_service`, `landmark`, `office`;
- `case_ids`: cases that use that location;
- optional `parent_location_id`: sub-rooms/flats nested under a larger building;
- `zoom_behavior`: `external`, `internal`, or `external_to_internal`.

The API exposes these tags through `visual.canonical_locations`. Future migrations should prefer these tags plus canonical bounds over inferring meaning from the painted image.

### Semantic object/evidence contract

Case 004 exposes `visual.object_visuals` from the map replay projection. Each entry keeps the authoritative `object_id`, adds a stable `semantic_asset_id`, and includes `anchor`, `location_id`, `state`, `marker_state`, `render_mode`, `safe_to_render`, `overlay_ids`, and linked clue IDs. The states are:

- `hidden`: the object is outside the case-visible/fog-revealed location set; it is never rendered.
- `visible`: the location is visible, but the linked clue has not been discovered; the evidence marker is suppressed and `safe_to_render` is false.
- `discovered`: the existing session contains one of the object's linked clue IDs; the evidence marker may render.

`overlay_ids` express case presentation such as `overlay_missing_coping` and `overlay_muddy_footprint`. The frontend renderer currently uses temporary glyphs for discovered evidence only. Final sprites can replace the glyph field by `semantic_asset_id` without changing case data or discovery logic. Future cases should add a semantic asset mapping and anchor in the visual map definition, then derive state only from their existing clue session and visible-location set.

## Style and technical contract

- Cute top-down orthographic RPG, roofless/opened buildings, readable interiors, modest outlines, warm daylight/soft ambient base.
- Use a 32px tile and character-frame contract so the existing 32px sprite sheets remain compatible. The full canonical overworld is 192x144 tiles (6144x4608), composed from 3x3 cells of 64x48 tiles (2048x1536). B2 is the centre town cell.
- Keep global lighting neutral in the base asset. `lightingTint(minutesOfDay)` remains the global time-of-day overlay. Lamps, windows, and fireplaces are small local emissive accents only.
- Art must be authored as layered assets: base terrain, town structures, reusable props, case overlay, evidence marker, and fog mask.
- Suggested asset naming: `tile_*`, `struct_*`, `prop_*`, `obj_*`, `overlay_*`, `fx_*`, `fog_*`, `loc_*`. Existing case/object/location IDs remain authoritative and are referenced in metadata.

## Location bible

Canonical coordinates are tile coordinates on the 64x48 grid, origin `(0,0)` at the north-west. Bounding boxes are `x,y,w,h` in tiles and are recommendations, not current runtime coordinates.

| Location ID | Cases | Module / footprint | Neighbours | Mode | Evidence / overlay needs | Fog default |
|---|---|---|---|---|---|---|
| `loc_village_square` | 001–006 | open plaza `18,14,28,16` | fountain, cafe, bookshop, clinic, pub, houses, alley | exterior | benches, lamps, sightlines, NPC paths | revealed anchor |
| `loc_fountain` | 001–005 | fountain zone `29,19,10,9` inside square | square, Elias bench | exterior hotspot | coping gap, stone, muddy bed, water | reveal with square |
| `loc_hobbs_cafe` | 001–003,005 | cafe `18,7,11,8`; kitchen module `20,12,5,5` | square, alley, Clara flat | cutaway | counter/till, tables, kitchen door | case-reveal |
| `loc_cafe_kitchen` | 001 | kitchen `20,12,5,5` | cafe, storage | interior | sink, coat rack, mop bucket, till weight | case-reveal |
| `loc_cafe_storage` | 001 | storage `25,12,5,5` | kitchen, alley | interior | crates, rear door, ledger page, body/evidence anchor | case-reveal |
| `loc_rear_alley` | 001,002,005 | service lane `22,5,20,4` | square, cafe, bookshop | exterior | doors, bins, glass, ash/fire, footprints | case-reveal |
| `loc_bookshop` | 001,002,005,006 | shop `10,9,10,8` | square, alley, back room | cutaway | shelves, counter, stock table, rear door | case-reveal |
| `loc_bookshop_back` | 002 | back room `10,13,10,6` | bookshop, alley | interior | desk, safe, letter opener, broken window | case-reveal |
| `loc_clinic` | 001–006 | clinic `39,15,9,8` | square, dispensary | cutaway | reception, beds, notes, window sightline | case-reveal |
| `loc_clinic_dispensary` | 003 | dispensary `45,16,6,6` | clinic | interior | shelves, cabinet, sink, altered log | case-reveal |
| `loc_marcus_house` | 001,006 | house `28,5,11,8` | square, study | cutaway | sitting room, fireplace, mug, armchair | case-reveal |
| `loc_marcus_study` | 006 | study `31,7,8,6` | Marcus house, square path | interior | desk, books, will, certificate, fireplace | case-reveal |
| `loc_owen_house` | 001–005 | house/yard `47,13,11,10` | square, outer road | cutaway/exterior | gate, timber, boots, belt, yard log | case-reveal |
| `loc_clara_flat` | 001,003,005 | flat `19,3,7,5` above cafe | cafe | interior | bed, table, phone, documents | case-reveal |
| `loc_priya_flat` | 001,002,004,006 | flat `6,29,7,5` | square via residential path | interior | books, scarf, letters | case-reveal |
| `loc_nadia_flat` | 001 | flat `40,10,6,5` above clinic | clinic, square sightline | interior | window, notebook, lamp | case-reveal |
| `loc_elias_house` | 001,004 | cottage `24,31,8,7` | square, fountain sightline | cutaway | bedroom window, bench connection | case-reveal |
| `loc_elias_bench` | 003 | bench zone `31,22,4,2` | fountain, square | exterior sub-zone | notebook, pill organiser, appointment card | reveal with fountain |
| `loc_ben_flat` | 004 | flat `5,24,7,5` | square via west path | interior | phone, letters, clipping, jacket | case-reveal |
| `loc_pub` | 004 | pub `9,6,11,10` | square, west road | cutaway | bar, stools, ledger, lighter, receipt | case-reveal |
| `loc_ruth_cottage` | 006 | cottage/garden `48,29,11,9` | square, east path | cutaway/exterior | fireplace, foxglove garden, key, vial | case-reveal |
| `loc_solicitors_office` | 006 | office `42,37,9,6` | square, south road | cutaway | desk, files, appointment/letter | case-reveal |

### Day/night and case layer policy

Every location uses the same daylight base. The runtime tint supplies day/night. Per-case overlays can change doors, object placement, damage, fire/ash, broken glass, fountain coping, and evidence marker state. No overlay may contain a hidden killer silhouette or unearned clue.

## Reusable tile, structure, and prop catalog

| Asset ID | Category / grid | Reuse | Placement | Production | Notes / licence |
|---|---|---|---|---|---|
| `tile_grass`, `tile_mud`, `tile_cobble`, `tile_path` | terrain, 1x1 | reusable | town and expansion | hand-authored or generated then cleaned | bespoke; no external licence |
| `tile_floor_wood`, `tile_floor_stone`, `tile_wall_exterior`, `tile_wall_interior` | interior, 1x1 | reusable | all cutaways | hand-authored | keep contrast low enough for props |
| `tile_water`, `tile_water_edge` | fountain, 1x1 | reusable/animated | fountain | hand-authored; 2–4 frame shimmer | no baked night colour |
| `struct_door`, `struct_window`, `struct_fence`, `struct_hedge` | structure, 1x2 to 2x2 | reusable | building edges, yards | hand-authored | case overlays may toggle open/broken |
| `struct_tree`, `struct_flowerbed`, `struct_garden_plot` | environment, 2x2 to 4x3 | reusable | square, yards, Ruth garden | hand-authored | flowerbeds support mud/bootprint overlay |
| `prop_lamp`, `prop_bench`, `prop_fountain_coping` | civic, 1x1 to 5x5 | reusable | square and paths | hand-authored | local light is subtle emissive layer |
| `prop_cafe_counter`, `prop_till`, `prop_mop_bucket`, `prop_coat_rack`, `prop_crate`, `prop_bin` | cafe/service, 1x1–5x2 | reusable | cafe, kitchen, storage, alley | hand-authored | anchor IDs separately from clue IDs |
| `prop_ledger`, `prop_desk`, `prop_letter_opener`, `prop_bookshop_shelf`, `prop_safe`, `prop_broken_window` | shop/office, 1x1–4x3 | reusable + damaged window variant | bookshop/back room | hand-authored | broken window is overlay-capable |
| `prop_clinic_bed`, `prop_dispensary_shelf`, `prop_medicine_cabinet`, `prop_pill_organiser` | clinic, 1x1–3x2 | reusable | clinic/dispensary | hand-authored | medicine labels remain generic at overview scale |
| `prop_pub_bar`, `prop_pub_stool`, `prop_pub_ledger`, `prop_lighter` | pub, 1x1–6x3 | reusable | pub | hand-authored | lighter can be evidence-visible only after discovery |
| `prop_fireplace`, `prop_armchair`, `prop_cocoa_mug`, `prop_books`, `prop_garden_plant`, `prop_foxglove` | home/garden, 1x1–4x3 | reusable | Marcus/Ruth/house modules | hand-authored | fireplace ember is a local light, not global tint |
| `prop_letters`, `prop_documents`, `prop_phone`, `prop_key`, `prop_belt`, `prop_boots` | evidence props, 1x1–2x1 | reusable semantic props | case-specific anchors | hand-authored | state controlled by clue/object logic |
| `overlay_fire_damage`, `overlay_ash`, `overlay_muddy_footprint`, `overlay_missing_coping`, `overlay_broken_glass` | case overlay, 1x1–6x4 | case-specific/reusable templates | alley, fountain, bookshop | hand-authored | no clue text embedded in art |
| `fx_fog_mask`, `fx_evidence_marker`, `fx_unknown_figure`, `fx_sound_ripple` | UI/FX, variable | reusable | all maps | hand-authored | player-safe projection only |

## Semantic object mapping

The object mapping in `town_asset_audit.md` is canonical for this pass. The rule is: existing `obj_*` IDs drive state; a semantic asset ID drives appearance; one semantic asset may be reused by multiple case objects; case overlays express damage or moved/found state.

Examples: `obj_till_weight` uses the reusable brass-weight prop; `obj_broken_window_glass` uses `prop_broken_window` plus `overlay_broken_glass`; `obj_fountain_stone` uses `prop_fountain_coping` plus `overlay_missing_coping`; `obj_foxglove_garden` uses `prop_foxglove` with a harvested-state variant.

## Fog of war

The canonical town is always the underlying geometry. Each case supplies a reveal set of location IDs and optional sub-zone IDs. Unrevealed areas render as a neutral obscuring mask, not dark narrative art. Object/evidence markers are independently gated by the existing clue discovery state. Truth replay remains a separate post-accusation projection. Background NPCs may exist in revealed public zones but should use low-salience labels or no labels at overview scale.

## External assets and attribution

Preferred production is bespoke hand-authored or generated-and-cleaned assets in this style. No external asset is selected in this pass. Any future external asset must record creator, source URL, licence, modification status, and redistribution requirements in an asset manifest before inclusion.
