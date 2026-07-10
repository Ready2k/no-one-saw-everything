You are working on the mystery investigation game repository.

The developer map editor has now been used to create or refine the canonical town layout and case-specific layout overrides.

Treat the saved map editor output as the source of truth for visual placement.

Do not redesign the map layout.
Do not move buildings, locations, evidence anchors, or case overlays unless the saved layout data is invalid and you document why.
Do not rename existing case IDs, location IDs, object IDs, clue IDs, event IDs, or agent IDs.
Do not change clue discovery logic, event ordering, suspect logic, or deduction logic.
Preserve unrelated user changes in the repository.

Primary goal:

Update the artwork so the visible town map matches the saved canonical layout and case-specific overrides from the map editor.

The artwork must support the reusable cute top-down RPG visual system.

Inputs:

* Saved map editor layout JSON, likely:

  * `backend/app/data/town/town_layout.json`
* Existing visual docs:

  * `docs/town_asset_audit.md`
  * `docs/town_asset_bible.md`
  * `docs/canonical_town_layout.md`
  * `docs/town_visual_implementation_plan.md`
* Code-backed town contract:

  * `backend/app/town_map.py`
* Existing Case 004 reference art:

  * `frontend/public/art/case_004/`

Artwork requirements:

* True top-down orthographic / cutaway view.
* Roofless/opened buildings where interiors are visible.
* Rooms, furniture, paths, objects, and evidence areas must be readable from above.
* No side-on facades as the primary investigation map.
* Use the saved 64×48 grid and 32px tile contract.
* Use the saved location bounds and object/evidence anchors.
* Keep the fountain square as the visual centre.
* Keep a neutral daylight / soft ambient base.
* Do not bake global night, dusk, dawn, or midday lighting into the base artwork.
* Preserve the existing runtime lighting system using `lightingTint(minutesOfDay)`.
* Local lamps, windows, fireplaces, and similar light sources should be subtle accents only.

Layering requirements:

Produce or update art as layered assets where practical:

1. Base terrain
2. Roads and paths
3. Building shells / cutaway interiors
4. Reusable furniture and props
5. Case-specific overlays
6. Evidence/object visual markers
7. Fog-of-war mask
8. Runtime lighting overlay remains code-driven

The base canonical town must exist underneath.

Case-specific overlays may add or change:

* missing fountain coping
* muddy flowerbed / bootprints
* broken glass
* fire damage / ash
* open or locked doors
* moved objects
* evidence markers
* damaged object variants

Case overlays must not duplicate the entire town unless absolutely unavoidable.

Case 004 pilot:

Update Case 004 first.

Case 004 must use the saved editor layout for:

* `loc_village_square`
* `loc_fountain`
* `loc_pub`
* `loc_ben_flat`
* `loc_priya_flat`
* `loc_elias_house`
* `loc_owen_house`
* `loc_clinic`

Also update or prepare visual treatment for these Case 004 evidence/object anchors:

* `obj_fountain_stone`
* `obj_mud_bootprint`
* `obj_ben_jacket_mud`
* `obj_fred_lighter`
* `obj_pub_ledger`
* `obj_blackmail_letters`
* `obj_arson_clipping`
* `obj_ben_phone`
* `obj_owen_pub_receipt`

Evidence visibility must remain discovery-gated.

Do not reveal hidden clues, hidden events, killer identity, or undiscovered evidence through artwork.

Other cases:

Do not migrate all cases at once.

After Case 004 is working, prepare the art system so future cases can use the same canonical town and case overlay model.

Cases 001, 002, 003, 005, and 006 should keep their existing fallback behaviour unless explicitly selected for migration.

Validation:

Run:

* JSON validation
* backend tests
* frontend type-check
* frontend production build

Manually inspect:

* `/dev/map-editor`
* Case 004 Places view
* Case 004 Map Replay
* Case 004 Rewind
* Case 004 location crops
* Case 004 location transitions
* Case 004 evidence inspection
* fog-of-war, if active
* object/evidence marker visibility
* midnight lighting
* dawn lighting
* noon lighting
* dusk lighting
* night lighting

Final report must include:

* Saved layout file used
* Files inspected
* Files created
* Files modified
* Artwork generated or updated
* Temporary assets versus final assets
* How the art matches the saved map editor layout
* How object/evidence anchors were represented
* How hidden/discovered states are protected
* Validation commands run
* Validation results
* Known limitations
* Recommended next case to migrate
