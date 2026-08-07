# Investigation Scene Asset Bible

Status: authoritative art-direction and technical contract for player-facing Places scenes.

This document governs the large investigation images used by `frontend/src/sceneArt.ts` and
special interactive scene components. It is deliberately separate from `town_asset_bible.md`,
which governs the overhead Map Replay/Rewind world.

## Non-negotiable style lock

- Places scenes are **high-resolution cinematic environmental illustrations**, normally 16:9 and
  authored at 3840×2160 where practical.
- The camera is eye-level or a believable cinematic room angle. It is not a tilemap, sprite scene,
  dollhouse, pixel-art room, isometric game board, or top-down cutaway.
- Use realistic materials, scale, perspective, weather, wear, and practical lighting. The target is
  the established Hobbs Cafe investigation frame:
  `frontend/public/art/case_001/hobbs_cafe_investigation_v4.avif`.
- Preserve the identity of the established rural British village. Architecture seen through doors
  and windows must belong to this same small village: stone or limewashed walls, timber details,
  slate or clay roofs, narrow lanes, modest shopfronts, cottages, hedges, and the village square.
- Do not introduce metropolitan terraces, dense urban roofscapes, tower blocks, grand city
  institutions, contemporary laboratories, fluorescent institutional fittings, or unapproved
  modern furniture and radiators.
- The setting is a deliberately timeless rural British mystery village whose established artwork
  is the visual authority. Do not describe or prompt it simply as “medieval”; that wording causes
  fantasy and RPG drift. Georgian/Victorian vernacular details may appear where the case and
  established location support them.
- Never use legacy 32px character sheets, building stamps, map tiles, glyphs, or ambient animation
  sheets as visual references for a Places background or forensic close view.

## 2.5D interaction contract

Each investigable scene should provide depth through authored images and interface motion rather
than fake sprite enlargement:

1. A wide establishing frame with foreground, middle-ground, and background separation.
2. Subtle pointer/camera parallax that never distorts evidence positions.
3. Clearly authored examination surfaces reachable through hotspots and named view controls.
4. Dedicated close-view artwork for important surfaces; do not crop a low-resolution map stamp.
5. Matched state pairs where the player changes the scene, such as drawer closed/open or cabinet
   shut/open. Camera, lens, crop, and lighting must remain stable between the pair.
6. Tool-specific visual and logical responses. Raking light, UV, swabs, fingerprint treatment, and
   ordinary inspection must not all reveal the same result.
7. Interpretation steps for forensic conclusions where appropriate. A click alone should not turn
   every suspicious mark into evidence.
8. False leads and cleared surfaces may provide feedback without creating a case clue.

## Evidence safety

- Base scene artwork may contain ordinary props and ambiguous marks, but must not announce which
  object is evidence.
- Do not paint readable names, accusations, culprit silhouettes, clue labels, UI markers, or
  conclusions into the image.
- Discovery and clue recording remain controlled by case data and the existing API.
- A forensic close view must support the authored clue without visually revealing more than the
  clue description and current investigation stage allow.
- Tool effects should be interface overlays or matched authored variants, not irreversible edits to
  the canonical base frame.

## Continuity checklist

Before accepting a Places asset, compare it with:

- the existing scene for the same location, if one exists;
- `frontend/src/sceneArt.ts`;
- the relevant case location description and clue anchors;
- the established village exterior/map for window and doorway views;
- adjoining rooms, especially Hobbs Cafe → kitchen → storage → rear alley;
- recurring furnishings, doors, windows, wall finishes, floor materials, and lighting direction.

Reject an asset if it changes the apparent town, period, building footprint, adjoining route, or
social character of the location without an explicit case requirement.

### Recurring square and fountain

`frontend/public/art/case_005/village_square_dawn_hd.avif` is the current cinematic physical
reference for the recurring village square and fountain; Case 010 deliberately uses the identical
frame. Later cases may change time, weather, investigation distance, or clue-gated state, but must
preserve its fountain design, facades, bench, lampposts, paving, and street openings. The older
square/fountain tile-art images under Case 001, Case 002, `town/places_hd`, and Case 004 are
rejected legacy style references.

## Current interactive reference

The Cafe Storage Room is the reference vertical slice:

- wide frame: `frontend/public/art/case_001/storage_room_interactive_wide_v1.avif`
- floor trace: `frontend/public/art/case_001/storage_room_floor_trace_v1.avif`
- drawer states: `storage_room_drawer_closed_v1.avif` / `storage_room_drawer_open_v1.avif`
- false-lead stain: `storage_room_crate_stain_v1.avif`
- rear door: `storage_room_rear_door_v1.avif`
- interaction: `frontend/src/components/CafeStorageRoomScene.tsx`

This reference establishes the expected relationship between cinematic artwork, 2.5D navigation,
different forensic tools, interpretation, false leads, and discovery-gated clue persistence.

## File and version rules

The authoritative searchable catalogue is
`backend/app/data/town/place_art_registry.json`. Every authored case must have a clock range,
lighting phase, weather tag, coverage status, and explicit case-specific bindings there. Runtime
backend projection reads this registry directly. Use `python3 tools/audit_place_art_registry.py`
to list all sets, or add `--lighting dusk`, `--lighting dawn`, and similar filters when looking for
an existing treatment. A case may be labelled `complete` only when every authored location has an
explicit matching scene; validation tests enforce that rule.

- Use descriptive, location-specific, versioned filenames.
- Do not overwrite an accepted reference while exploring a new direction.
- Keep each state pair and its base scene in the same location folder.
- Record production selection in the registry and mirror it in `frontend/src/sceneArt.ts` for the
  browser bundle.
- Optimised delivery derivatives may be added later, but the project must retain a high-resolution
  production source.
