# Town Map Asset Bible

Status: authoritative art-direction and runtime contract for Map Replay, Rewind, map crops, and
location transitions.

This document governs the overhead town map only. Large player-facing Places investigations follow
`docs/scene_asset_bible.md`. Never use the map camera, 32px coordinate grid, legacy character
markers, building stamps, or animation sheets as a style reference for a Places scene.

## Sources of truth

In descending order of authority:

1. `backend/app/data/town/town_layout.json` — canonical 192×144 world bounds, lights, object
   anchors, and case overrides saved by the map editor.
2. `backend/app/town_map.py` — runtime map selection, current image URLs, location function tags,
   visibility, overlays, and projection rules.
3. `backend/app/data/town/building_library.json` — reusable building bundles and production paths.
4. `frontend/src/map/mapAssets.ts` — scale-aware single-image and mosaic resolution.
5. `frontend/public/art/town/town_canonical_v1_manifest.json` — production metadata, which must
   mirror the sources above and must not override them.

Case, location, object, clue, event, and agent IDs remain authoritative. Artwork and manifests must
adapt to those IDs; case data must not be renamed to fit an image.

## Map art style lock

- Use one locked style: lifelike high-resolution rural British architectural rendering seen from a consistent elevated
  top-down/isometric map camera.
- Preserve the established landscape, building silhouettes, roads, water, square, and rural scale.
  The current runtime reference family is `current_village_v2_neutral`.
- Avoid visible pixel-art styling, hard outlines, chibi proportions, RPG tileset repetition,
  toy-like dollhouse rendering, and fantasy-medieval exaggeration.
- “32px tile” describes logical placement only. It does **not** permit 32px-style environmental
  artwork or make any low-resolution source an acceptable final map asset.
- Legacy character assets remain temporary compatibility markers. They are not an art reference for
  environments, buildings, props, evidence, portraits, or Places scenes.
- Ambient motion must use restrained high-resolution effects or native CSS/canvas treatments such as
  mist, water shimmer, smoke, birds, and lamp flicker. Sprite sheets are not part of the environment-art pipeline.
- The village is a deliberately timeless rural British mystery setting. Use established assets as
  period authority; do not prompt it merely as “medieval.”

## Camera, resolution, and coordinate contract

- Full world: 192×144 logical tiles at 32px per tile, rendered at 6144×4608.
- Mosaic: 3×3 cells, each 64×48 logical tiles and 2048×1536 pixels.
- Origin: north-west of the full 192×144 world; x increases east and y increases south.
- B2 is the centre cell, but canonical location bounds are full-world coordinates from
  `town_layout.json`, not old B2-local recommendations.
- Runtime exterior family:
  `frontend/public/art/town/tiles_3x3_hd/current_village_v2_neutral/`.
- B2 exterior:
  `town_overworld_B2_current_village_v2_neutral.avif`.
- B2 close/cutaway:
  `town_overworld_B2_current_village_v2_neutral_cutaway.avif`.
- The close view swaps at `zoom_image_tiles.threshold` 3.2 while preserving the same geometry.

## Map layers

Author and compose map art as:

1. base terrain and water;
2. roads, paths, bridges, boundaries, and vegetation;
3. exterior building forms;
4. geometry-matched cutaway/interior view where supported;
5. reusable environmental props;
6. case overlays such as damage, ash, mud, missing coping, or an opened route;
7. discovery-gated evidence/object presentation;
8. fog/reveal treatment;
9. code-driven global lighting and local light overlays.

Do not duplicate the whole town for an evidence change that can be represented by a small overlay.
Do not bake global dawn, day, dusk, or night grading into the neutral canonical base.

## Legacy markers and anti-regression rule

The runtime can still display legacy character markers and temporary evidence glyphs. These are
compatibility hooks only:

- legacy markers may identify moving agents on the overhead replay;
- temporary glyphs may mark evidence only after discovery;
- neither may be enlarged, recoloured, cropped, or reused as final environment art;
- final semantic evidence assets should be high-resolution transparent overlays or UI markers that
  visually belong to the painted map;
- Places scenes must always use dedicated cinematic artwork.

Any future prompt or brief that requests “pixel art,” “RPG,” “storybook,” or “cute” in
relation to primary environment/location art conflicts with this bible unless it explicitly refers
to a temporary agent marker.

## Canonical location bounds

These are the current saved full-world tile bounds from `town_layout.json`:

| Location ID | Bounds x,y,w,h | View |
|---|---:|---|
| `loc_village_square` | `88,52,22,13` | exterior |
| `loc_fountain` | `97,54,5,5` | exterior |
| `loc_marcus_house` | `101,36,21,14` | exterior |
| `loc_marcus_study` | `108,39,8,6` | interior |
| `loc_hobbs_cafe` | `99,67,17,20` | exterior |
| `loc_cafe_kitchen` | `100,72,8,7` | interior |
| `loc_cafe_storage` | `109,72,6,7` | interior |
| `loc_clinic` | `111,52,15,14` | exterior |
| `loc_clinic_dispensary` | `118,56,6,6` | interior |
| `loc_bookshop` | `72,54,16,16` | exterior |
| `loc_bookshop_back` | `73,62,7,7` | interior |
| `loc_rear_alley` | `86,50,40,2` | exterior |
| `loc_pub` | `83,71,15,18` | exterior |
| `loc_owen_house` | `118,68,21,18` | exterior |
| `loc_elias_house` | `99,92,17,13` | exterior |
| `loc_clara_flat` | `100,68,8,3` | interior |
| `loc_ben_flat` | `64,72,8,12` | interior |
| `loc_priya_flat` | `73,72,8,12` | interior |
| `loc_nadia_flat` | `128,54,12,12` | interior |
| `loc_ruth_cottage` | `126,35,18,17` | exterior |
| `loc_solicitors_office` | `86,36,14,14` | exterior |
| `loc_elias_bench` | `104,62,4,2` | exterior |
| `loc_fishery` | `146,47,45,29` | exterior |
| `loc_lake` | `0,52,62,51` | exterior |
| `loc_woodland` | `0,2,63,47` | exterior |
| `loc_meadow` | `119,102,67,42` | exterior |
| `loc_back_lane` | `110,87,31,4` | exterior |
| `loc_st_alder_church` | `67,36,18,15` | exterior |
| `loc_willow_farmhouse` | `46,108,22,19` | exterior |

Do not copy bounds from an older B2 manifest or design sketch into runtime data. Update this table
whenever the saved editor layout changes.

## Location metadata and case coverage

`LOCATION_FUNCTION_TAGS` in `backend/app/town_map.py` supplies `display_name`, `function_tag`,
`building_role`, `case_ids`, optional `parent_location_id`, and `zoom_behavior`. The API exposes
these through `visual.canonical_locations`.

Case coverage should be derived from the case location files rather than maintained as fragile prose
tables. Current shipped case folders are `case_001` through `case_007`, plus `case_010`. Expansion
locations for St Alder Church and Willow Farmhouse exist in the visual library but are not yet bound
to a shipped case.

## Semantic evidence and overlays

`visual.object_visuals` preserves each authoritative `object_id` and adds presentation metadata:
`semantic_asset_id`, `anchor`, `location_id`, state, marker state, render mode, safety flag, overlay
IDs, and linked clue IDs.

- `hidden`: outside the safe revealed set; never render.
- `visible`: location visible but evidence not discovered; marker suppressed and unsafe to render.
- `discovered`: linked clue discovered; marker or semantic overlay may render.

Object anchors now exist in `town_layout.json` for Cases 001–007. Case 004 contains nine
discovery-gated anchors. Case 010 shares the Case 001 authored visual geography but does not have a
separate editor override block.

No overlay may contain a hidden culprit, unearned clue, readable accusation, or knowledge the player
has not acquired.

## Reusable buildings and props

`building_library.json` is the source for building bundle paths. Current production building assets
live under `frontend/public/art/town/buildings/production/`; the older generated-exterior directory
is a design/archive source, not the default runtime path.

Building stamps are logical map modules. Their 32px-grid dimensions do not make their rendering
style authoritative for cinematic Places art. Tenant-specific interiors and special location
searches may use dedicated HD assets selected through `frontend/src/sceneArt.ts`.

Suggested semantic prefixes remain `tile_*`, `struct_*`, `prop_*`, `obj_*`, `overlay_*`, `fx_*`,
`fog_*`, and `loc_*`.

## Lighting and atmosphere

- The canonical map base remains neutral enough for `lightingTint(minutesOfDay)`.
- Streetlamp, window, clinic, pub, and fireplace glows are local, time-gated overlays.
- Case-authored maps may carry a controlled palette appropriate to the case, but must still avoid
  contradicting runtime lighting or hiding navigational information.
- Ambient animation sheets must be subtle, correctly scaled, and lower-salience than agents,
  evidence, labels, and routes.

## External assets and attribution

Preferred production is project-owned, generated-and-cleaned or commissioned art. Any external
asset must record creator, source URL, licence, modification status, and redistribution terms in an
asset manifest before inclusion.
