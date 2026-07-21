# Town Asset Audit

Status: audit/design pass only. No final artwork or runtime map migration was performed.

## Scope and sources

Audited:

- `backend/app/data/case_001` through `case_006`: `case.json`, `locations.json`, `objects.json`, `clues.json`, `events.json`, and `agents.json`.
- `backend/app/models.py`, `backend/app/map_layout.py`, `backend/app/projections.py`, `backend/app/main.py`, `backend/app/case_store.py`, and the map replay tests.
- `frontend/src/map/lighting.ts`, `mapAssets.ts`, `mapInfo.ts`, `mapProjection.ts`, `VisualMap.tsx`, `MapCrop.tsx`, `LocationTransition.tsx`, `Places.tsx`, `MapReplay.tsx`, `Rewind.tsx`, and related types/API code.
- `frontend/public/art/case_004/fountain_midnight_map.png` and `fountain_closeup.png`.
- Existing reviewer files in `reviewers/`.

The working tree already contains user changes in case data, case-004 locations/art, map components, styles, and reviewer files. This pass leaves those changes untouched.

## Executive findings

1. The authoritative content is location/object/clue/event data, not artwork. No case data should be renamed to match proposed art IDs.
2. The current runtime is image-based: one `the_ville` fallback image (719x513) for most cases and a case-004 image (1448x1086) for case 004. There is no tilemap or semantic prop renderer yet.
3. `map_layout.py` is a visual fallback with coordinates in rendered image pixels. It is not a canonical town graph and contains borrowed/mismatched sectors.
4. Case 001 has authored coordinates on all 14 locations. Case 004 has authored coordinates on all 8 locations. Cases 002, 003, 005, and 006 have no authored coordinates and use the fallback layout.
5. The case-004 reference image is a strong style reference for cute, readable top-down cutaways, exposed rooms, fountain scale, and furniture density, but it is night-lit and must not become the daylight base.
6. Individual objects and clues do not currently render as object sprites or evidence hotspots. The map can render safe event markers, agents, and location bounds, but not clue-linked props.
7. Case 006 is `18:00` to `07:15`; current helpers add 1440 to times earlier than the active start, which handles one overnight rollover but does not represent explicit day offsets in API data or event records.

## Case-by-case inventory

| Case | Title | Locations | Objects | Clues | Time range / map state |
|---|---|---:|---:|---:|---|
| case_001 | The Storage Room Murder | 14 | 6 | 20 | 06:00–08:12; all locations authored on legacy 719x513 layout |
| case_002 | The Locked Bookshop | 9 | 7 | 14 | 11:30–13:15; all locations fallback |
| case_003 | The Clinic After Hours | 8 | 7 | 14 | 16:00–18:00; all locations fallback |
| case_004 | The Fountain at Midnight | 8 | 10 | 14 | 18:00–07:15 in case data; bespoke 1448x1086 night image; authored positions |
| case_005 | The Rear Alley Fire | 8 | 8 | 11 | 06:00–07:31; all locations fallback |
| case_006 | The Bell Estate | 8 | 8 | 17 | 18:00–07:15; all locations fallback; overnight ordering risk |

The clue count is the number of entries in each `clues.json` pack. An object count is the number of entries in `objects.json`; some clue text describes physical things without a corresponding object ID.

## Location inventory

Coordinates shown here are the existing visual coordinates where present. `fallback` means `map_layout.py` supplies a point or bounds at runtime. A location can be logically connected even if the visual layout does not show a corresponding walkable route.

| Location ID | Display names in data | Cases | Existing visual state | Required treatment |
|---|---|---|---|---|
| `loc_village_square` | Village Square | 001–006 | authored in 001/004; fallback otherwise | central exterior plaza, paths, fountain sightlines, benches |
| `loc_fountain` | Fountain / Village Fountain / Bench by the Fountain | 001–005 | authored in 001/004; fallback otherwise | distinct fountain sub-zone inside square; coping/evidence nodes |
| `loc_hobbs_cafe` | Hobbs Cafe | 001–003,005 | authored in 001; fallback otherwise; appears in case-004 art only as style context | roofless public cafe with counter, tables, till, kitchen door |
| `loc_cafe_kitchen` | Cafe Kitchen | 001 | authored in 001 | cutaway interior module with sink, hooks, mop bucket |
| `loc_cafe_storage` | Cafe Storage Room | 001 | authored in 001 | cramped cutaway room with crates and rear door |
| `loc_rear_alley` | Rear Alley | 001,002,005 | authored in 001; fallback otherwise | narrow exterior/service route behind cafe/bookshop, bins and fire-damage overlay |
| `loc_bookshop` | Reed & Bell Bookshop | 001,002,005,006 | authored in 001; fallback otherwise | roofless shop floor, shelves, counter, rear access |
| `loc_bookshop_back` | Bookshop Back Room | 002 | fallback | cutaway office/stockroom, desk, safe, window, rear door |
| `loc_clinic` | Village Clinic | 001–006 | authored in 001; fallback otherwise | public waiting room/treatment module, reception, visible upper flat context only if later authored |
| `loc_clinic_dispensary` | Clinic Dispensary | 003 | fallback | private cutaway room, shelves, cabinet, sink, log |
| `loc_marcus_house` | Marcus Bell’s House | 001,006 | authored in 001; fallback otherwise | cutaway house with sitting room/fireplace and study connection |
| `loc_marcus_study` | Marcus’s Study | 006 | fallback | book-lined study, desk, papers, fireplace |
| `loc_owen_house` | Owen Price’s House & Yard | 001–005 | authored in 001; fallback otherwise | house-plus-yard module, gate facing square, timber/storage area |
| `loc_clara_flat` | Flat above Hobbs Cafe | 001,003,005 | authored in 001; fallback otherwise | compact cutaway flat; bed/table/paperwork/phone |
| `loc_priya_flat` | Priya’s Flat | 001,002,004,006 | authored in 001 only; fallback otherwise | small book-heavy residential module |
| `loc_nadia_flat` | Nadia’s Flat | 001 | authored in 001 only | compact private flat; window sightline to square should be readable |
| `loc_elias_house` | Elias Grant’s House / Elias’s Cottage | 001,004 | authored in 001/004 | cottage with bedroom window and square-facing sightline |
| `loc_elias_bench` | Elias’s Bench | 003 | fallback | bench sub-zone near fountain, not a separate building |
| `loc_ben_flat` | Ben’s Flat | 004 | fallback | compact flat above newsagent; letters/phone/jacket inspection points |
| `loc_pub` | The Mallet & Crown | 004 | authored in 004 | cutaway pub with bar/stools/ledger; direct square connection |
| `loc_ruth_cottage` | Ruth’s Cottage | 006 | fallback | cottage plus fenced garden and foxglove bed |
| `loc_solicitors_office` | Whittle & Cross Solicitors | 006 | fallback | small public office with reception/desk/document storage |

## Authoritative object and prop inventory

No object currently has a dedicated semantic art asset or an object-specific map hotspot. `normal_location_id` and `final_location_id` are authoritative placement data. Recommended IDs below are semantic art IDs only; existing object IDs remain unchanged.

| Existing object ID | Narrative name | Case / location | Role | Visual state | Recommended asset ID |
|---|---|---|---|---|---|
| `obj_till_weight` | Brass till weight | 001 / cafe, kitchen | weapon/evidence | generic counter props only | `obj_till_weight` |
| `obj_ledger_page` | Torn ledger page | 001 / Marcus house → storage | evidence | missing dedicated prop | `obj_torn_ledger_page` |
| `obj_blue_coat` | Blue wool coat | 001 / kitchen | evidence | missing dedicated prop | `obj_blue_coat` |
| `obj_loan_ledger` | Marcus’s loan book | 001 / study | evidence | missing dedicated prop | `obj_loan_book` |
| `obj_partnership_letter` | Partnership letter | 001 / house → storage | evidence | missing dedicated prop | `obj_partnership_letter` |
| `obj_isabella_note` | Isabella’s handwritten note | 001 / bookshop → storage | evidence | missing dedicated prop | `obj_isabella_note` |
| `obj_letter_opener` | Victorian letter opener | 002 / back room | weapon/evidence | missing dedicated prop | `obj_letter_opener` |
| `obj_forged_document` | Forged partnership transfer | 002 / back room | evidence | missing dedicated prop | `obj_forged_document` |
| `obj_broken_window_glass` | Broken window pane | 002 / back room → alley | damaged evidence | no overlay; current image is generic | `obj_broken_window` |
| `obj_priya_scarf` | Priya’s green scarf | 002 / flat → bookshop | evidence | missing dedicated prop | `obj_priya_scarf` |
| `obj_solicitor_letter` | Solicitor’s letter | 002 / back room | evidence | missing dedicated prop | `obj_solicitor_letter` |
| `obj_owen_debt_folder` | Owen’s debt correspondence | 002 / back room | evidence | missing dedicated prop | `obj_owen_debt_folder` |
| `obj_stockroom_invoice` | Signed delivery invoice | 002 / bookshop | evidence | missing dedicated prop | `obj_delivery_invoice` |
| `obj_solicitor_appointment` | Solicitor appointment card | 003 / Elias bench | evidence | missing dedicated prop | `obj_appointment_card` |
| `obj_elias_notebook` | Elias’s notebook | 003 / Elias bench | evidence | missing dedicated prop | `obj_elias_notebook` |
| `obj_clinic_bequest_letter` | Original bequest letter | 003 / clinic | evidence | missing dedicated prop | `obj_bequest_letter` |
| `obj_dispensary_log` | Clinic dispensary log | 003 / dispensary | evidence | missing dedicated prop | `obj_dispensary_log` |
| `obj_pill_bottle` | Elias’s pill organiser | 003 / Elias bench | evidence | missing dedicated prop | `obj_pill_organiser` |
| `obj_nadia_notebook` | Nadia’s patient notes | 003 / clinic | evidence | missing dedicated prop | `obj_patient_notes` |
| `obj_clinic_delivery_manifest` | Clinic delivery manifest | 003 / clinic | evidence | missing dedicated prop | `obj_delivery_manifest` |
| `obj_blackmail_letters` | Bundle of blackmail letters | 004 / Ben flat | evidence | missing dedicated prop | `obj_blackmail_letters` |
| `obj_arson_clipping` | Newspaper clipping | 004 / Ben flat | evidence | missing dedicated prop | `obj_arson_clipping` |
| `obj_ben_phone` | Ben’s mobile phone | 004 / Ben flat | evidence | missing dedicated prop | `obj_phone` |
| `obj_owen_pub_receipt` | Owen’s pub receipt | 004 / pub | evidence | missing dedicated prop | `obj_pub_receipt` |
| `obj_fountain_stone` | Loose fountain coping stone | 004 / fountain | weapon/evidence | case image implies broken coping but not semantic hotspot | `obj_fountain_coping_stone` |
| `obj_mud_bootprint` | Bootprint in flower bed | 004 / fountain | evidence terrain mark | generic ground texture only | `obj_muddy_bootprint` |
| `obj_ben_jacket_mud` | Mud on Ben’s jacket cuff | 004 / Ben flat | evidence | missing dedicated prop | `obj_muddy_jacket` |
| `obj_fred_lighter` | Engraved brass lighter | 004 / pub | evidence | missing dedicated prop | `obj_pub_lighter` |
| `obj_pub_ledger` | Pub ledger | 004 / pub | evidence | missing dedicated prop | `obj_pub_ledger` |
| `obj_mortgage_deed` | Fraudulent mortgage deed | 005 / Clara flat | evidence | missing dedicated prop | `obj_mortgage_deed` |
| `obj_clara_note` | Clara’s committee note | 005 / Clara flat | evidence | missing dedicated prop | `obj_committee_note` |
| `obj_owen_belt` | Owen’s leather belt | 005 / yard → alley | weapon/evidence | missing dedicated prop | `obj_leather_belt` |
| `obj_burn_accelerant` | Lighter fluid / accelerant | 005 / rear alley | damaged evidence | needs fire overlay and ash prop | `obj_fire_accelerant` |
| `obj_col_log` | Col’s delivery log | 005 / Owen yard | evidence | missing dedicated prop | `obj_delivery_log` |
| `obj_owen_boot_mud` | Ash on Owen’s boots | 005 / Owen yard | evidence | missing dedicated prop | `obj_ashy_boots` |
| `obj_property_register` | Land Registry extract | 005 / Clara flat | evidence | missing dedicated prop | `obj_property_register` |
| `obj_cocoa_mug` | Marcus’s cocoa mug | 006 / Marcus house | evidence | missing dedicated prop | `obj_cocoa_mug` |
| `obj_digitalis_vial` | Empty digitalis vial | 006 / Ruth cottage | evidence | missing dedicated prop | `obj_digitalis_vial` |
| `obj_foxglove_garden` | Foxglove stand | 006 / Ruth garden | environment/evidence | needs garden plant variant | `obj_foxglove` |
| `obj_birth_certificate` | Ruth’s birth certificate | 006 / Marcus study | evidence | missing dedicated prop | `obj_birth_certificate` |
| `obj_revised_will` | Revised will draft | 006 / Marcus study | evidence | missing dedicated prop | `obj_revised_will` |
| `obj_burnt_document` | Burnt document | 006 / Marcus study fireplace | damaged evidence | needs fireplace ash state | `obj_burnt_document` |
| `obj_ruth_key` | Marcus’s spare key | 006 / Ruth cottage | evidence | missing dedicated prop | `obj_spare_key` |
| `obj_elias_memory` | “Bell girl” memory | 006 / square | non-physical interview clue | no prop; use dialogue/evidence UI only | `clue_memory_bell_girl` |

### Physical props mentioned without an object ID

These are required by narrative/clue text or location descriptions and need reusable art, but must not be added to case data as new authoritative object IDs in this pass: cafe counter, tables, sink, coat hooks/rack, mop bucket, crates, bins, rear doors, bookshop shelves, safe/loose back panel, desk, pen pot, clinic beds, reception desk, medicine cabinet, pill-preparation sink, pub bar/stools, fireplace, armchair, cocoa side table, books, garden plants, flowerbeds, fountain coping, benches, lamps, windows, doors, muddy footprints, ash, fire-scorched crates, fences, hedges, and laundry line.

## Clue/evidence visual representation

All 117 clues are represented in the deduction/data layer. None is currently guaranteed to have a dedicated visual node. Clues fall into four implementation groups:

| Group | Examples | Current visual state | Required future treatment |
|---|---|---|---|
| Object-linked evidence | till weight, letter opener, foxglove, cocoa mug | object ID exists but no prop renderer | attach hotspot to object anchor; visibility follows inspect/discovery logic |
| Location-linked evidence | rear alley, fountain, clinic dispensary | location/crop exists; no semantic hotspot | attach location anchor and optional terrain overlay |
| Witness/timeline evidence | “dull thud”, “two figures”, sightings | safe event markers can show ambiguity | preserve projection visibility; use sound/unknown-figure markers only |
| Document/memory evidence | threats, alibis, “Bell girl”, false alibi | text/interview UI only | keep text-only unless a physical source object is authoritative |

The most important missing visual nodes are the case-004 fountain coping gap, bootprint/flowerbed, Ben’s muddy jacket, the case-001 till weight/mop bucket, case-002 broken window, case-005 fire/ash/belt, and case-006 fireplace/foxglove/cocoa chain.

## Environmental inventory and reuse

Recurring environmental elements are the square, central fountain, benches, lamps, cobbled/muddy paths, flowerbeds, hedges, trees, fences, building footprints, doors, windows, cafe/bookshop/clinic fronts, residential cutaways, and the rear alley. Reusable tile families should cover grass, mud, cobblestone, paths, water, interior floors, walls, doors, windows, fences, hedges, trees, flowerbeds, lamps, benches, and night-light overlays. Case-specific overlays should cover broken window, missing fountain coping, fire/ash/scorch, moved objects, and evidence markers.

## Coordinates, rendering, and mismatch findings

- `backend/app/map_layout.py` describes its layout as 719x513 rendered pixels from the original `the_ville` map and uses a deterministic fallback ring for unknown location IDs.
- Authored location coordinates win over fallback coordinates. Locations without authored coordinates still receive a fallback point; some have no bounds.
- `frontend/src/map/mapAssets.ts` assumes a 140x100, 32px source tile grid and a 3x4, 32px character sheet. `VisualMap.tsx` sizes agents from that fixed grid, while the actual map API dimensions vary between 719x513 and 1448x1086.
- `MapCrop.tsx` uses a fixed `CROP_PAD = 1.8`; focused map zoom uses fixed scales and location bounds. A future tilemap should derive crop/agent sizing from map metadata, not hardcoded 140x100 assumptions.
- `Places`, `MapReplay`, `Rewind`, `Intro`, and location transitions call the cached `/api/map/replay` geometry. `LocationTransition` falls back to a crop when no illustration exists.
- `/api/map/replay` selects case 004 by case ID and all other cases use `the_ville`. This is the first case-aware selection point, but the new architecture should return a canonical town asset plus a case overlay/layer list.
- The case-004 image is a top-down cutaway with visible interiors, furniture, square, fountain, and paths. Its global palette is midnight/dark, with strong lamps and deep shadows; this conflicts with a neutral base and runtime lighting responsibility.
- The legacy fallback is a borrowed Smallville layout: bookshop, clinic, and residential locations are mapped to approximate sectors, and several authored locations share or reuse buildings. This is a visual mismatch, not a logic defect.

## Fallback locations

Unknown IDs use deterministic slots at approximately `(141,236)`, `(326,244)`, `(598,134)`, `(146,129)`, `(290,372)`, `(113,329)`, `(617,257)`, or `(488,95)`. These slots are safe for generated-case continuity but are not suitable as canonical town geography.

## Time model risk

`Event.time` is an `HH:MM` string. Backend and frontend `minutes()` functions compare it to the active simulation start and add 1440 when a time is earlier than that start. This handles case 006’s single overnight rollover for many comparisons, but the API still emits ambiguous clock strings and no explicit day index. Multiple days, event sorting, and lighting across more than one rollover are not represented. Recommended smallest safe extension for implementation: retain authored `HH:MM` for compatibility, add derived `absolute_minutes`/`day_offset` in projections, and make lighting receive absolute simulation minutes while deriving the tint from modulo 1440.

## Risks and assumptions

- Proposed semantic art IDs are mappings to existing IDs, not replacements.
- A visual hotspot must never reveal a hidden event, killer identity, undiscovered clue, or object state before the existing discovery gate allows it.
- The canonical map should initially be a visual layer; adjacency and access remain case data until a deliberate logic migration.
- Existing case-004 artwork and dirty working-tree changes are treated as user-owned and preserved.
- External art is not needed for the bespoke system; if used later, source URLs, author, licence, and modification status must be recorded beside the asset manifest.
