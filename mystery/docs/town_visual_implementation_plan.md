# Town and Investigation Visual Implementation Plan

Status: current implementation summary and remaining visual-system roadmap.

Read both authoritative contracts before producing art:

- `docs/town_asset_bible.md` — overhead Map Replay/Rewind world.
- `docs/scene_asset_bible.md` — cinematic Places and forensic investigation scenes.

The two systems share location identity and evidence safety, but they do not share a camera or asset
resolution. The map is an elevated painted world; Places uses dedicated cinematic HD frames.

## Implemented

- 6144×4608, 192×144 canonical world with a 3×3 HD mosaic.
- Neutral `current_village_v2_neutral` runtime tile family.
- Geometry-matched B2 exterior/cutaway swap at scale 3.2.
- Saved canonical location bounds in `town_layout.json`.
- Case-aware map selection for Cases 001–007 and 010.
- Canonical-overworld consumers for Cases 002 and 004.
- Authored case maps for the other shipped cases.
- Location function metadata through `LOCATION_FUNCTION_TAGS`.
- Discovery-gated `visual.object_visuals`.
- Case object-anchor blocks for Cases 001–007.
- Time-gated local light overlays.
- Dedicated HD Places art resolved by `sceneArt.ts`.
- Interactive 2.5D Places components for Hobbs Cafe, Cafe Kitchen, and Cafe Storage Room.
- Cafe Storage Room forensic vertical slice with separate views, state-paired drawer artwork,
  tool-specific results, a false lead, interpretation, and clue persistence.

## Anti-regression gate

Before accepting any new environment or location artwork, verify:

- no pixel-art, RPG sprite, chibi, cartoon, or low-resolution building-stamp treatment;
- no legacy character sheet or map glyph used as an environment reference;
- no top-down map crop presented as a final cinematic Places scene;
- no eye-level cinematic frame inserted into the overhead map mosaic;
- no metropolitan or modern institutional details that contradict the established village;
- no hidden clue, culprit, readable accusation, or discovery marker baked into base art;
- no global time-of-day grade baked into a neutral canonical map tile;
- no scene-state change that moves the camera between matched before/after frames.

## Phase 1 — synchronize contracts and manifests

- Keep `town_layout.json`, `town_map.py`, `building_library.json`, and
  `town_canonical_v1_manifest.json` synchronized.
- Keep the production scene selection in `sceneArt.ts` synchronized with
  `scene_asset_bible.md`.
- Treat 32px as map geometry only.
- Record accepted reference images explicitly so prompts cannot drift away from the locked lifelike style.

## Phase 2 — map evidence presentation

- Replace temporary evidence glyphs with high-resolution painted overlays or restrained UI markers
  keyed by `semantic_asset_id`.
- Preserve discovery gating and safe projection logic.
- Add selected-object UI and map inspection only where it does not reveal undiscovered evidence.
- Keep ambient animation sheets limited to subtle effects below agents/evidence in visual priority.

## Phase 3 — map layout completion

`town_layout.json` currently has canonical bounds and lights but no saved building, prop, overlay, or
ambient placements. Add those only through the editor or validated layout changes:

- reusable high-resolution building placements;
- environmental prop placements;
- case damage/state overlays;
- ambient effect placements;
- fog/reveal masks where required.

Do not repopulate the town from obsolete 64×48 recommendation tables.

## Phase 4 — Places forensic rollout

Use the Cafe Storage Room as the quality and interaction reference. For each new scene:

1. confirm the canonical location identity and adjoining routes;
2. approve one cinematic wide frame;
3. identify a small number of meaningful investigation surfaces;
4. generate dedicated close views and matched state pairs;
5. assign different tools to different forensic questions;
6. include eliminations and false leads where the case supports them;
7. require interpretation before recording non-trivial conclusions;
8. connect the result to existing clue discovery;
9. verify window/door views remain inside the established village;
10. test desktop and narrow layouts.

Do not mechanically give every scene the same three tools or the same clue sequence.

## Phase 5 — remaining scene quality pass

Review every `sceneArt.ts` path against `scene_asset_bible.md`, prioritising:

- low-resolution production building interiors still used as Places fallbacks;
- reused images that make distinct locations appear identical;
- exterior views that suggest a city rather than the village;
- modern/institutional props not required by case data;
- inconsistent lighting, lens, or camera height;
- scenes without authored close views where forensic interaction is important.

## Phase 6 — time model hardening

The model stores `HH:MM` and infers a single overnight rollover. Before supporting multi-day
visual replay:

1. derive absolute minutes/day offset in backend projection;
2. retain authored `HH:MM` for display;
3. pass absolute simulation minutes to lighting;
4. apply modulo 1440 only for tint lookup;
5. test event sorting and lighting over multiple rollovers.

## Validation

For map changes:

- validate `town_layout.json` and all modified manifests;
- run backend tests;
- run frontend tests, type-check, and production build;
- inspect Map Replay, Rewind, map crops, transitions, zoom swap, evidence gating, and lighting.

For Places changes:

- inspect the wide scene and every close/state frame;
- exercise correct and incorrect tools;
- verify false leads do not create clues;
- verify the correct conclusion persists through the discovery API;
- confirm responsive layout and image loading;
- compare village continuity through every visible window and door.

## Explicit non-goals

- no conversion of primary environment art to pixel art or tile-game imagery;
- no full tile-game engine rewrite;
- no case-data renames for visual convenience;
- no evidence visibility derived from what happens to be painted;
- no single camera rule forced across both map and Places systems.
