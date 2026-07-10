# Town Visual Implementation Plan

Status: implementation plan only. No runtime wiring is performed by the audit pass.

## Phase 0 — approval gate

Confirm the stable-ID mappings, 64x48 / 32px grid, fountain-centred layout, and case overlay policy in `town_asset_bible.md` and `canonical_town_layout.md`. Do not start full art production before this gate.

## Phase 1 — asset manifest and renderer contract

Add a visual-only manifest, ideally under `frontend/public/art/town/manifest.json`, containing:

- canonical map asset, dimensions, tile size, grid, origin;
- location bounds and sub-zones keyed by existing location IDs;
- reusable prop asset IDs and anchor points;
- case overlay asset IDs and state keys;
- source/licence metadata for every non-bespoke asset.

Extend the map response with canonical geometry and a case-aware asset/overlay description while preserving legacy `map_position`, `map_bounds`, `asset`, `image`, `width`, and `height` fields during migration.

Likely files: `backend/app/map_layout.py`, `backend/app/projections.py`, `backend/app/main.py`, `frontend/src/types.ts`, `frontend/src/map/mapAssets.ts`, `frontend/src/map/mapInfo.ts`.

## Phase 2 — neutral base map and reusable tiles

Create the daylight/soft-ambient town base: terrain, square, fountain, paths, alley, building cutaways, roofs removed/opened, and expansion margins. Keep local lamps/windows/fireplaces subtle. Verify the base at midnight, dawn, noon, dusk, and night with runtime tint applied.

The existing case-004 image remains a reference and fallback until the pilot has parity. Do not bake its midnight palette into the canonical base.

## Phase 3 — prop anchors and evidence-safe overlays

Implement a layer renderer or sprite compositor that places reusable props by semantic asset ID. Add anchors for object-linked and location-linked clues. Read visibility from the existing clue/discovery state; do not derive evidence visibility from art presence. Add overlays for fountain coping, broken window, fire/ash, mud/bootprint, and moved objects.

Keep hidden/private events under the existing `project_map_event` visibility rules. Evidence markers must never expose killer identity, hidden events, or undiscovered clues.

Likely files: `frontend/src/components/VisualMap.tsx`, new map-layer components, `frontend/src/map/mapProjection.ts`, `frontend/src/components/EventMarker.tsx`, and the relevant API projection types.

## Phase 4 — case-004 pilot

Use case 004 first because it has the clearest existing top-down reference and a compact visual footprint. Validate:

- square/fountain/pub/Elias/Owen sightlines;
- Ben flat documents and phone;
- fountain coping gap, flowerbed, muddy bootprint;
- runtime lighting at 00:00, dawn, noon, dusk, and 21:00;
- map replay, Places crops, Rewind crops, location transition, zoom, labels, and evidence inspection.

Case 004 should use the canonical base plus a midnight/case overlay, not a duplicated case-specific town image.

## Phase 5 — fallback rollout

Move cases 001, 002, 003, 005, and 006 to the canonical base only when their required modules/anchors exist. Until then, preserve the existing fallback behaviour. Return case-specific overlay lists without changing case logic. Add a migration table for legacy coordinates rather than rewriting case JSON.

## Phase 6 — time model hardening

The current model stores only `HH:MM` and infers one rollover using the active start time. Before multi-day visual replay is considered complete:

1. derive absolute minutes/day offset in backend projection from case start and event ordering;
2. expose a numeric simulation time to the frontend while retaining the display `HH:MM`;
3. pass absolute simulation minutes to lighting, applying modulo 1440 only for tint lookup;
4. update event sorting/filtering, Rewind, MapTimeline, and tests for case 006 overnight ordering;
5. add a multi-day fixture before supporting more than one rollover.

This is a recommended later change, not part of the audit-only implementation.

## Phase 7 — validation and visual QA

Run JSON validation, backend tests, frontend type-check/build, and the existing map replay tests. Exercise all six cases and confirm:

- the canonical town loads with all locations having usable geometry;
- old cases still use fallback until migrated;
- case-aware asset selection is correct in Places, Map Replay, Rewind, location transitions, and accusation truth replay;
- crops and zoom are derived from map metadata rather than hardcoded legacy dimensions;
- NPC labels are quiet at overview scale;
- fog masks do not leak hidden information;
- object/clue inspection still uses existing discovery logic;
- lighting is correct at midnight, dawn, noon, dusk, and night.

## Files likely to change later

Backend: `backend/app/map_layout.py`, `backend/app/main.py`, `backend/app/projections.py`, `backend/app/models.py` only if additive map metadata is needed, plus map/time tests.

Frontend: `frontend/src/types.ts`, `frontend/src/map/mapAssets.ts`, `frontend/src/map/mapInfo.ts`, `frontend/src/map/mapProjection.ts`, `frontend/src/components/VisualMap.tsx`, `MapCrop.tsx`, `LocationTransition.tsx`, `EventMarker.tsx`, `MapTimeline.tsx`, `Places.tsx`, `MapReplay.tsx`, `Rewind.tsx`, and styles.

Assets/docs: new `frontend/public/art/town/` manifest, tile/prop/overlay files, and attribution metadata. Existing `frontend/public/art/case_004/` files should remain intact as reference/fallback until the pilot is accepted.

## Non-goals for this pass

- no final raster art generation;
- no replacement of existing maps;
- no case-data renames or clue/event changes;
- no deduction, visibility, or discovery logic changes;
- no broad frontend/backend refactor;
- no external asset acquisition.
