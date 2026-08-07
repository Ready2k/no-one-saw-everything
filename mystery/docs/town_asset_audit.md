# Town and Scene Asset Audit

Status: current audit as of 2026-07-30.

## Scope

Checked against:

- case folders `case_001`–`case_007` and `case_010`;
- `backend/app/data/town/town_layout.json`;
- `backend/app/town_map.py`;
- `backend/app/data/town/building_library.json`;
- `frontend/src/map/mapAssets.ts`;
- `frontend/src/sceneArt.ts`;
- specialist Places scene components;
- current town, building, and case-art directories;
- `town_canonical_v1_manifest.json` and building manifests.

## Authoritative findings

1. The visual system has two distinct outputs:
   - a high-resolution painterly-realistic overhead map;
   - high-resolution cinematic Places/forensic scenes.
2. The canonical world is 192×144 logical tiles at 32px, rendered at 6144×4608. A 64×48 grid is
   one mosaic cell, not the canonical coordinate space.
3. The runtime canonical tile family is `current_village_v2_neutral`.
4. Cases 002 and 004 use the canonical overworld. Other shipped cases use authored case maps; they
   do not share one blanket `the_ville` fallback.
5. Legacy character sheets and temporary evidence glyphs remain compatibility markers only.
   Primary environment and Places artwork must never regress to that style.
6. `town_layout.json` contains current bounds for 29 locations and object anchors for Cases 001–007.
7. Places uses authored scene images through `sceneArt.ts`; the Cafe Storage Room now has a
   dedicated 2.5D forensic interaction.
8. The building library’s current production paths exist, but many building stamps are only
   32px-grid map modules. They are not suitable as cinematic Places art.

## Current case inventory

| Case | Locations | Objects | Clues | Current map mode |
|---|---:|---:|---:|---|
| `case_001` | 16 | 6 | 22 | shared authored HD village |
| `case_002` | 10 | 7 | 18 | canonical overworld |
| `case_003` | 8 | 8 | 20 | authored afternoon map |
| `case_004` | 12 | 9 | 20 | canonical overworld |
| `case_005` | 10 | 9 | 25 | authored dawn/rear-alley map |
| `case_006` | 8 | 8 | 17 | authored night map |
| `case_007` | 16 | 7 | 21 | authored lantern-fair map |
| `case_010` | 16 | 6 | 22 | shared authored HD village |

Counts are snapshots. Runtime tools should read the case JSON rather than relying on this table.

## Current map assets

### Canonical overworld

- Runtime source: `current_village_v2_neutral`
- Full world: 6144×4608
- Mosaic: nine 2048×1536 cells
- B2 exterior and cutaway are geometry-matched
- Global lighting remains code-driven
- Local light overlays are time-gated

The rendered map is painterly-realistic at an elevated map camera. It should not be described as
pixel art, an RPG tileset, a sprite map, or the camera reference for Places.

### Authored case maps

Cases 001, 003, 005, 006, 007, and 010 currently use authored case-map families. Their locations
and palettes are defined in `CASE_MAPS`. These are valid current consumers, not unmigrated
`the_ville` placeholders.

## Current Places assets

`frontend/src/sceneArt.ts` maps recurring location IDs and selected cases to dedicated investigation
frames. Places art is independent from map tiles and building stamps.

Current quality reference:

- `hobbs_cafe_investigation_v4.avif`
- `cafe_kitchen_investigation_v4.avif`
- `storage_room_interactive_wide_v1.avif` and its close/state views

The accepted direction is cinematic eye-level HD with believable depth, material detail, and rural
British continuity. A map cutaway or 320×192 building stamp is not an acceptable substitute.

## Remaining visual risks

### Style regression

The repository legitimately contains:

- legacy agent character assets;
- legacy transparent ambient animation sheets;
- temporary semantic evidence glyphs;
- small building modules aligned to the logical map grid.

Those assets must be named and documented as narrow-purpose compatibility assets. New ambient
effects must use high-resolution effects or native CSS/canvas treatments. Compatibility assets must
not be used as a style reference or enlarged into primary environment art.

### Mixed Places quality

Some `sceneArt.ts` fallbacks still point to production building interiors rather than cinematic HD
scenes, notably Ruth’s Cottage and the solicitors’ office. These are functional but below the
current Places quality bar.

### Manifest drift

`town_canonical_v1_manifest.json` must mirror the saved full-world bounds and the runtime
`current_village_v2_neutral` tile family. Older remastered-master paths may remain as provenance or
archive references, but must not be labelled as the runtime selection.

### Clara’s Flat binding

`town_map.py` correctly treats Clara’s Flat as an internal child of Hobbs Cafe. The building library
also has a dedicated Clara interior variant, but its general `location_bindings` entry still points
to the standalone flats shell. Do not commission or select a separate city-flat exterior for Clara.

### Period and geography drift

The established art is a fictional rural British mystery village, not a generic fantasy-medieval
settlement and not a modern city. Window and door views need explicit continuity checks to prevent
urban terraces, institutional rooms, metropolitan skylines, and unsupported modern fixtures.

## Evidence safety

Object/evidence presentation remains derived from case state:

- hidden objects never render;
- visible-but-undiscovered objects suppress evidence markers;
- discovered objects may render a marker or semantic overlay;
- base artwork cannot encode culprit identity or an unearned conclusion.

Case 004 has nine discovery-gated object anchors. Cases 001–003 and 005–007 also have saved anchor
blocks. Case 010 shares Case 001’s authored geography but has no separate layout override.

## Current layout data

`town_layout.json` currently contains:

- 29 canonical location bounds;
- 11 canonical local lights;
- no canonical building instances;
- no canonical prop instances;
- no canonical ambient placements;
- case object-anchor blocks for Cases 001–007;
- no saved case-specific location overrides or overlay placements.

These empty placement collections are current valid state. Do not refill them from obsolete
recommendation tables.

## Recommended next work

1. Replace remaining low-resolution Places fallbacks with cinematic HD location art.
2. Continue the forensic interaction rollout one scene at a time.
3. Replace temporary map evidence glyphs with painted overlays or restrained high-resolution UI.
4. Keep map and Places acceptance checks separate.
5. Re-run this audit whenever `town_layout.json`, `CASE_MAPS`, or `sceneArt.ts` materially changes.
