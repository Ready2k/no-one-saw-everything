We need redesign the game’s visual world around a reusable cute top-down RPG tile system.

Context:
- This is a mystery investigation game.
- The current artwork has drifted toward side-on/facade views.
- Investigation maps must remain true top-down cutaway maps so players can see rooms, furniture, paths, objects, and evidence areas.
- Cases currently exist as case_001 through case_006.
- Existing location IDs, object IDs, clues, events, and narratives are authoritative.
- Preserve unrelated user changes in the repository.

Objective:
Create a reusable town asset system that supports all existing cases and future cases.

Do not immediately generate a giant case-specific image. First audit and design the reusable world.

Phase 1 — Repository audit

Inspect:

- All case data under backend/app/data/case_001 through case_006
- locations.json
- objects.json
- clues.json
- events.json
- agents.json
- Existing map rendering and coordinate systems
- Existing frontend artwork and sprite conventions
- Existing reviewer files

Build a complete inventory of:

1. Every unique location ID and name.
2. Every unique object ID and physical prop described in narratives or clues.
3. Every recurring environmental element.
4. Every location used by each case.
5. Every object/clue that currently lacks visual representation.
6. Existing map coordinates, fallback locations, and visual mismatches.

Phase 2 — Asset bible

Create a documented asset bible, preferably at:

docs/town_asset_bible.md

For every location, define:

- Location ID
- Display name
- Cases using it
- Required room modules
- Required furniture and props
- Connections to neighbouring locations
- Suggested map coordinates
- Interior/exterior/cutaway status
- Night/day variants
- Evidence hotspots
- Fog-of-war visibility state

For every visual asset, define:

- Stable semantic asset ID
- Asset category
- Required dimensions/grid size
- Where it appears
- Which cases use it
- Whether it is reusable, case-specific, damaged, hidden, or animated
- Whether it should be generated, hand-authored, or sourced externally
- Licence/attribution requirements for external art

Use stable IDs such as:

loc_village_square
loc_fountain
loc_hobbs_cafe
loc_cafe_kitchen
loc_cafe_storage
obj_till_weight
obj_mop_bucket
obj_blue_coat

Do not invent replacements for existing IDs. Add new IDs only when the narratives clearly require them.

Phase 3 — Canonical town layout

Design one canonical top-down town layout around the known cases.

Start with:

- Village Square
- Village Fountain
- Hobbs Cafe
- Cafe Kitchen
- Cafe Storage Room
- Reed & Bell Bookshop
- Bookshop Back Room
- Village Clinic
- Clinic Dispensary
- Rear Alley
- The Mallet & Crown
- Marcus Bell’s House and Study
- Owen Price’s House and Yard
- Clara’s Flat
- Priya’s Flat
- Nadia’s Flat
- Elias’s Cottage/Bench
- Ben’s Flat
- Ruth’s Cottage and Garden
- Whittle & Cross Solicitors

Requirements:

- True top-down orthographic/cutaway presentation.
- Roofless or opened buildings where interiors are visible.
- No side-on facades as the primary investigation view.
- Use a consistent tile scale compatible with the existing map/sprite system.
- Leave unexplored expansion areas around the known town.
- Map all locations to stable coordinates.
- Make the fountain square the visual centre and navigation anchor.

Phase 4 — Reusable tile and prop system

Design the required tile families:

- Grass
- Mud
- Cobblestone
- Paths
- Interior floors
- Exterior/interior walls
- Doors
- Windows
- Fences
- Hedges
- Trees
- Flowerbeds
- Water
- Lamps
- Benches
- Fire-damaged terrain
- Night lighting variants

Design the required reusable props:

- Café counter
- Till
- Mop bucket
- Coat rack
- Crates
- Ledger
- Bookshop shelves
- Desk
- Letter opener
- Broken window
- Clinic beds
- Dispensary shelves
- Medicine cabinet
- Pill organiser
- Pub bar
- Pub stools
- Pub ledger
- Lighter
- Fireplace
- Cocoa mug
- Books
- Garden plants
- Foxglove
- Letters
- Documents
- Phone
- Key
- Belt
- Boots
- Fountain coping stone
- Muddy footprints

Phase 5 — Fog of war and case layers

Implement or design fog-of-war so that:

- The canonical town exists underneath.
- Unused areas can remain obscured.
- A case only reveals locations relevant to that investigation.
- Evidence remains controlled by the existing clue-discovery logic.
- Fog of war never leaks hidden killer identity, hidden events, or undiscovered evidence.
- Case-specific overlays can change lighting, damage, doors, object placement, and evidence markers without duplicating the town.

Phase 6 — Visual production

Only after the asset bible and layout are approved:

- Generate or create the reusable tile/prop assets.
- Keep all art in the cute top-down RPG style.
- Prefer coherent bespoke assets over unrelated stock images.
- External assets are allowed, but record their source and licence.
- Do not use side-on illustrations for investigation maps.
- Use close-up illustrations only for location transitions or evidence inspection where appropriate.
- Keep map art readable at overview scale and when zoomed.

Reference artwork:
- Use `/Users/jamescregeen/Code_Projects/generative_agents/mystery/frontend/public/art/case_004/`
  as a visual reference for the current cute RPG palette, pixel density, map readability,
  fountain treatment, furniture scale, and cutaway top-down composition.
- Treat this as a style/reference example only, not as the final universal town layout.
- Preserve the true top-down cutaway approach: interiors, rooms, furniture, paths,
  and investigation areas must be visible from above.
- Do not copy the current night-time lighting as the base tile appearance.

Time-of-day and lighting:
- Inspect and preserve the existing runtime lighting system in
  `frontend/src/map/lighting.ts` and `frontend/src/components/VisualMap.tsx`.
- Base map and tile artwork must use a neutral readable daylight/soft-ambient palette.
- Do not bake global night, dusk, dawn, or midday lighting into the base artwork.
- The runtime `lightingTint(minutesOfDay)` overlay must remain responsible for
  time-of-day changes.
- Keep local visual light sources—lamps, windows, fireplaces—subtle and readable,
  but do not use them to darken the entire map.
- Verify the result at midnight, dawn, noon, dusk, and night.

Multi-day timeline check:
- Audit whether the current event/time model represents dates or only
  minutes-since-midnight.
- If a case spans midnight or multiple days, do not silently treat later times
  as earlier times.
- Preserve or extend the lighting calculation so it receives an absolute
  simulation time or explicit day offset where required.
- Ensure event ordering and lighting remain correct across midnight.

Phase 7 — Implementation

Wire the canonical map and assets into the existing frontend/backend.

Requirements:

- Preserve all current case logic and clue behaviour.
- Preserve existing user changes.
- Keep existing sprite compatibility.
- Make map asset selection case-aware.
- Ensure Places, Map Replay, Rewind, and location transitions all use the correct case/map asset.
- Ensure map dimensions and crop calculations are not hardcoded to the old map.
- Ensure background NPC labels do not overwhelm the investigation map.
- Keep visual changes cosmetic and separate from deduction logic.

Validation:

- Run JSON validation.
- Run backend tests.
- Run frontend type-check/build.
- Test all six cases.
- Verify Case 004 first as the pilot.
- Verify that existing cases still use the canonical fallback map until their new layouts are ready.
- Visually inspect map replay, Places, location crops, zooming, fog of war, character labels, and evidence inspection.

Important workflow:

1. Start by producing the audit and asset bible.
2. Do not generate the full asset library until the layout and IDs are confirmed.
3. Use reasonable assumptions where possible.
4. Ask questions only when a decision would materially change the asset architecture.
5. Report all modified files and generated assets at the end.