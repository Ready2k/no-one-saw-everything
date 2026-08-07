You are working on the mystery investigation game repository.

Before producing or changing artwork, classify the requested asset as exactly one of:

1. **MAP** — overhead Map Replay/Rewind world, crop, building module, overlay, or ambient effect.
2. **PLACES** — cinematic player-facing investigation scene, forensic close view, or scene state.

Do not mix the two contracts.

Read:

* `docs/town_asset_bible.md` for MAP work.
* `docs/scene_asset_bible.md` for PLACES work.
* `backend/app/data/town/town_layout.json` for saved map geometry.
* `backend/app/town_map.py` for runtime map selection.
* `frontend/src/sceneArt.ts` for current Places selections.

Preserve unrelated user changes.
Do not rename case, location, object, clue, event, or agent IDs.
Do not change clue discovery, event ordering, suspect logic, or deduction logic merely to fit art.
Do not redesign saved map geometry.

## Universal anti-regression rule

Primary environment/location artwork must not use pixel-art, RPG-sprite, chibi, cartoon, toy-like
dollhouse, or low-resolution building-stamp styling.

The repository contains legacy character sheets, temporary evidence glyphs, map-aligned building
modules, and transparent ambient animation spritesheets. Those are narrow-purpose compatibility
assets. Never use them as style references for a background, building painting, prop close-up,
portrait, or Places scene.

The established fictional rural British village is the visual authority. Do not prompt it simply as
“medieval”; that wording causes fantasy drift. Preserve its stone/limewash/timber construction,
slate or clay roofs, modest rural scale, lanes, square, cottages, shopfronts, hedges, and adjoining
routes. Do not introduce metropolitan terraces, dense city roofscapes, tower blocks, institutional
modern rooms, fluorescent fittings, unsupported laboratory props, or unrelated modern furniture.

For the recurring village square and fountain, preserve the physical geometry in
`frontend/public/art/case_005/village_square_dawn_hd.avif` (also used by Case 010). Other cases may
change time, weather, camera distance, and discovery-gated state, but not the fountain, facades,
bench, lampposts, paving, or street openings.

## MAP contract

Use this contract only for the overhead world.

### Geometry

* Full saved world: 192×144 logical tiles.
* Logical tile: 32px.
* Full render: 6144×4608.
* Mosaic: 3×3 cells.
* Each cell: 64×48 logical tiles, rendered at 2048×1536.
* Origin: north-west of the full world.
* Location bounds and object anchors come from `town_layout.json`.
* The 32px grid is coordinate geometry, not an environment rendering style.

### Current runtime family

* `/art/town/tiles_3x3_hd/current_village_v2_neutral/`
* B2 exterior: `town_overworld_B2_current_village_v2_neutral.avif`
* B2 cutaway: `town_overworld_B2_current_village_v2_neutral_cutaway.avif`
* Close-view threshold: 3.2

### Visual requirements

* Elevated top-down/isometric map camera.
* High-resolution painterly-realistic materials and coherent continuous geography.
* Exterior and cutaway variants must keep roads, boundaries, and building footprints aligned.
* Neutral daylight/soft ambient canonical base.
* Runtime `lightingTint(minutesOfDay)` remains responsible for global time of day.
* Local lamps, windows, fireplaces, mist, smoke, water, and birds are subtle overlays.
* No visible RPG tile repetition or hard sprite outlines.
* No side-on cinematic room frame inserted into the map.

### Layering

1. Base terrain and water
2. Roads, paths, bridges, boundaries, and vegetation
3. Building exteriors
4. Geometry-matched cutaway/interiors
5. Reusable map props
6. Case damage/state overlays
7. Discovery-gated evidence/object presentation
8. Fog/reveal treatment
9. Runtime lighting and ambient overlays

Case overlays must not duplicate the whole town when a small overlay is sufficient.
Artwork must not reveal hidden evidence, events, culprit identity, or deductions.

### Current map consumers

* Cases 002 and 004 use the canonical overworld.
* Cases 001 and 010 use the shared authored HD village.
* Cases 003, 005, 006, and 007 use authored case maps.

Do not state that Case 004 is the sole migrated case or that every other case uses `the_ville`.

## PLACES contract

Use this contract for location searching and forensic interaction.

### Visual requirements

* Cinematic eye-level or believable room-angle composition.
* High-resolution 16:9 environmental artwork, normally 3840×2160 where practical.
* Realistic perspective, materials, wear, weather, depth, and practical lighting.
* Match the accepted Hobbs Cafe reference:
  `frontend/public/art/case_001/hobbs_cafe_investigation_v4.avif`.
* Do not use a top-down map crop, cutaway, 32px building module, character sprite, or glyph.
* Keep every visible exterior consistent with the established village.

### 2.5D requirements

Where interaction is requested:

1. Produce a wide establishing frame with foreground/mid/background separation.
2. Reserve safe hotspot areas without painting UI labels.
3. Produce dedicated close views for meaningful surfaces.
4. Produce camera-locked state pairs for drawers, doors, cabinets, or moved objects.
5. Support tool-specific responses; tools must not all reveal the same clue.
6. Include cleared surfaces or false leads where supported.
7. Require interpretation for non-trivial forensic conclusions.
8. Persist only authored clues through the existing discovery API.

Current reference:

* `frontend/public/art/case_001/storage_room_interactive_wide_v1.avif`
* `frontend/public/art/case_001/storage_room_floor_trace_v1.avif`
* `frontend/public/art/case_001/storage_room_drawer_closed_v1.avif`
* `frontend/public/art/case_001/storage_room_drawer_open_v1.avif`
* `frontend/src/components/CafeStorageRoomScene.tsx`

## Validation

For MAP changes:

* validate changed JSON;
* run backend tests;
* run frontend tests, type-check, and production build;
* inspect `/dev/map-editor`;
* inspect Map Replay, Rewind, crops, transitions, zoom swap, evidence gating, and lighting.

For PLACES changes:

* inspect every wide, close, and state image;
* compare adjoining rooms and visible village exteriors;
* test correct and incorrect tools;
* verify false leads do not create clues;
* verify clue persistence;
* inspect desktop and narrow layouts;
* run frontend tests, type-check, and production build.

## Final report

Include:

* whether the work was MAP or PLACES;
* source-of-truth files used;
* reference artwork used;
* files created and modified;
* production assets versus temporary compatibility assets;
* how geometry or scene continuity was preserved;
* how discovery gating was protected;
* validation commands and results;
* known limitations.
