# Location Art Brief — Interiors & Exteriors

Status: art-direction brief for illustration, derived from case data across `case_001`–`case_006`,
`backend/app/town_map.py` (`LOCATION_FUNCTION_TAGS`), and `backend/app/data/town/building_library.json`.
This is the descriptive companion to `docs/town_asset_bible.md` (style/technical contract) and
`docs/town_asset_audit.md` (data audit) — read those first for the rules; read this for what to
actually paint at each location. **This document is production art direction, not case truth.**
It never assigns guilt, and any "evidence anchor" note below is a paintable prop slot only —
whether a marker ever renders on it is decided at runtime by the discovery/fog system, not by art.

## How to use this brief

Each location gets:
- **What to paint** — exterior (roofed overworld view), interior (roofless cutaway), or both, per
  its `zoom_behavior` in `town_map.py`.
- **Footprint** — tile dimensions from `building_library.json` (32px tiles) as a size anchor.
- **Reserved file paths** — already wired into `building_library.json`; drop finished art straight in.
- A **prose brief** an illustrator can work from without opening the case files.
- **Case overlay notes** — case-specific damage/state variants layered on the same base art.

Where a named location (e.g. a specific villager's flat) shares a *building shell* with others
(e.g. "Two-Storey Flats"), the exterior is reused and only the interior dressing changes per
tenant — call this out explicitly so the artist doesn't repaint the shell four times.

## Style bible (condensed — see `town_asset_bible.md` for the full contract)

- **Genre**: cute, storybook-medieval top-down/isometric RPG village — think cosy pixel-art
  farming/adventure sim, not gritty or realistic. Reference render:
  `frontend/public/art/town/tiles_3x3_hd/town_overworld_B2_all_cases_external_hd.png`.
- **Construction**: whitewashed or pale stone lower walls, exposed dark timber framing accents,
  steep pitched roofs in terracotta clay tile or slate-blue tile (vary by building, not by case),
  small dormer windows, stone chimneys with a puff-friendly cap, round-arched or plank wooden
  doors on 2–3 stone steps.
- **Ground**: warm honey/tan cobblestone for the square and paths, soft green grass elsewhere,
  packed dirt for service areas (rear alley, yard, fishery).
- **Dressing**: wrought-iron lamp posts, wooden benches, low stone or picket fences, trimmed
  hedges, flowerbeds in warm reds/pinks/yellows/blues, mossy grey rockery clusters, pine and
  round deciduous trees, hand-painted wooden signage.
- **Lighting**: neutral warm daylight base only. No baked shadows implying a time of day — the
  runtime `lightingTint()` applies day/night globally. Fireplaces, lamps, and windows may carry a
  *small local* emissive glow, never a global mood.
- **Interiors**: roofless cutaway, readable from directly above/slightly isometric, modest ink-like
  outlines, floors in wood plank or flagstone, generous negative space so props stay legible at
  small scale. Furniture density similar to the case_004 fountain reference art, but painted at
  neutral daylight brightness, not midnight.
- **Grid**: 32px tile module; exterior building footprints and interior room layouts should both
  snap to it so placement and camera crops stay consistent.

## Building bundles (exterior + interior pairs)

### Hobbs Cafe — `cafe_small_v1`
**Location(s):** `loc_hobbs_cafe` (cases 001, 002, 003, 005) · **Zoom:** external ↔ internal ·
**Footprint:** 10×6 tiles · **Assets:** `buildings/cafe_small_v1_exterior.png` /
`_interior.png`

*Exterior* — a friendly single-storey village cafe fronting the square, pale stone with a
terracotta roof, a striped or scalloped awning over a wide shop window, an A-board or hanging
sign reading something cafe-shaped, a couple of outdoor bistro tables under the window, window
boxes with flowers. South-facing plank door onto a cobbled path (per `surrounding_rules.front:
path`), low hedges along the sides, a plain service path around the back leading to the alley.

*Interior* (rooms: `front_room`, `kitchen`, `storage`) — **front room**: a service counter with
till, a small glass display case, 3–4 café tables with mismatched chairs, a specials chalkboard,
warm wood floor. **kitchen** (private, staff-only — matches `loc_cafe_kitchen`): a working
kitchen behind the counter — stove, prep counter, a sink, a row of coat hooks by the back door,
a mop and bucket in the corner. **storage** (matches `loc_cafe_storage`): a cramped stockroom
behind the kitchen, stacked crates and shelving, a single rear door onto the alley — tight,
low-light, believable as a back-of-house dead end.

*Case overlay notes:* keep the till/counter and the mop bucket as clean, generic paintable props
(no blood, no staging) — state/marker rendering is handled entirely by the runtime, never baked
into the base art.

### Reed & Bell Bookshop — `bookshop_small_v1`
**Location(s):** `loc_bookshop` (001, 002, 005, 006) · **Zoom:** external ↔ internal ·
**Footprint:** 10×8 · **Assets:** `buildings/bookshop_small_v1_exterior.png` / `_interior.png`

*Exterior* — a narrow, tall-fronted shop with a bay window full of book spines, a painted wooden
sign board, stone/timber facade matching the square's palette, a modest recessed doorway. Hedge
trim to the sides, cobbled path to the front, service path to the rear alley door.

*Interior* (rooms: `shop_floor`, `back_room`, `stockroom`) — **shop floor**: tall bookshelves in
aisles, a service counter near the door, a reading nook, warm wood floor, dust-mote daylight
through the bay window. **back room** (matches `loc_bookshop_back`, private/staff): a cramped
office-cum-stockroom behind the counter — a writing desk, a small floor safe, stacked stock
boxes, one window, a rear door to the alley. **stockroom**: overflow shelving of boxed stock.

*Case overlay notes:* case 002 needs a **broken-window overlay** variant for the back room (a
cracked/shattered pane, consistent with `overlay_broken_glass` in the asset bible) — paint the
window as a separate swappable layer, not baked into the base interior.

### Village Clinic — `clinic_small_v1`
**Location(s):** `loc_clinic` (001–006) · **Zoom:** external ↔ internal · **Footprint:** 13×10 ·
**Assets:** `buildings/clinic_small_v1_exterior.png` / `_interior.png`

*Exterior* — a tidy public-service building, whitewashed stone, a small red-cross-free (avoid
real medical iconography — use a generic apothecary mortar-and-pestle or simple wellness sign
instead) shingle, a covered stoop, flower boxes (`sides: flowerbed`), a low rear fence. Reads as
calm and civic next to the cosier cafe/bookshop fronts.

*Interior* (rooms: `reception`, `exam_room`, `dispensary`) — **reception**: a waiting area with
a small bench/chairs, a reception desk with an appointment ledger, a noticeboard. **exam room**:
a treatment bed, a folding screen, a wall cabinet. **dispensary** (matches
`loc_clinic_dispensary`, locked/private): medicine shelving, a marked medication cabinet, a small
sink for preparing doses, a prescription log on a narrow desk — this room should read as
noticeably more restricted/back-of-house than reception (narrower, single door, no window to
the square).

*Case overlay notes:* case 003's dispensary log is an evidence-relevant prop — keep the log book
paintable as a plain, generic ledger (no visible text at native resolution).

### Marcus Bell's House — `house_large_study_v1`
**Location(s):** `loc_marcus_house` (001, 006) · **Zoom:** external ↔ internal ·
**Footprint:** 13×19 · **Assets:** `buildings/house_large_study_v1_exterior.png` / `_interior.png`

*Exterior* — the grandest private residence on the square: a two-storey, symmetrical **Georgian-
cottage** front (case 006 authors it explicitly as "a large Georgian house") — pale stone
facade, sash windows, a centred panelled door under a small portico, one or two chimneys, a
slightly larger footprint and more formal flowerbed border than neighbouring cottages to signal
status without looking out of genre. *(Note: case 001 describes this same building more plainly
as "on the edge of the square" — the richer case 006 description is treated as canonical for
exterior detail since it doesn't contradict, only adds detail.)*

*Interior* (rooms: `sitting_room`, `kitchen`, `bedroom`, `study`) — **sitting room**: a fireplace
with a fireside armchair (Marcus's habitual seat — keep the chair a plain, generic wingback, not
staged), a side table sized for a mug, a rug, warm domestic clutter. **kitchen**: modest,
homely, where "the cocoa was prepared" — stove, kettle, a couple of mugs on a shelf. **bedroom**:
simple, private, upstairs-coded. **study** (matches `loc_marcus_study`, private): book-lined
walls floor to ceiling, a writing desk with papers, a fireplace of its own (needs a **soot/ash
overlay** variant for case 006's burnt-document beat), a small family photograph on the desk or
mantel — restrained and gentleman's-study in tone, not cluttered.

### Owen Price's House & Yard — `house_yard_workshop_v1`
**Location(s):** `loc_owen_house` (001–005) · **Zoom:** external ↔ internal ·
**Footprint:** 15×13 · **Assets:** `buildings/house_yard_workshop_v1_exterior.png` /
`_interior.png`

*Exterior* — a working tradesman's plot: a plain stone cottage attached to a fenced timber yard
with stacked lumber, a lean-to workshop roof, a two-entrance layout (house door south, yard gate
east per `entrances`). Rougher and more utilitarian than the square's shopfronts — worn wood,
tool racks visible from outside, a small gate sign.

*Interior* (rooms: `house`, `workshop`, `timber_yard`, `gate`) — **house**: plain, lived-in,
boots by the door. **workshop**: a workbench, hand tools on a pegboard, sawdust texture, stacked
offcuts. **timber_yard**: open-air stacked timber, a delivery log clipboard, tarps. **gate**: the
square-facing threshold, worth a distinct painted marker since two case timelines hinge on who
was seen crossing it.

### The Mallet & Crown — `pub_small_v1`
**Location(s):** `loc_pub` (004) · **Zoom:** external ↔ internal · **Footprint:** 12×11 ·
**Assets:** `buildings/pub_small_v1_exterior.png` / `_interior.png`

*Exterior* — the village pub on the square's west side: dark exposed timber framing over cream
render, a hanging painted pub-sign board (mallet-and-crown motif, kept simple/heraldic — cute,
not literal), small leaded windows glowing warm at night, a stone chimney, a couple of outdoor
benches. Reads as the most "evening-lit" building since case 004 is a night case, but the base
art itself stays neutral daylight per the style contract — the warm glow is the runtime's local
window/lamp emissive layer, not a baked night palette.

*Interior* (rooms: `bar`, `public_room`, `back_room`) — **bar**: a long wooden bar with taps, a
row of stools, shelved bottles behind. **public_room**: mismatched tables, a fireplace, dartboard
or similar cosy-pub dressing. **back_room**: a small private room/office, a ledger on a desk — a
lighter or matchbox on the bar is a fine generic prop to include.

### Ben's Flat — flats shell (`flats_two_storey_v1`, attached-flat pattern)
**Location:** `loc_ben_flat` (004) · **Zoom:** internal only · **Footprint (shell):** 11×8 ·
**Assets:** interior only — see open question below re: exterior.

*Interior* (rooms drawn from `ground_flat`/`upper_flat`) — a small, slightly untidy bachelor
flat above a shop: a sofa, a low table with a phone and scattered post/newspaper, a jacket on a
hook by the door, a bed alcove. Keep it modest and lived-in rather than styled — case 004 treats
this as a private, slightly guarded space.

### Priya's Flat & Nadia's Flat — flats shell (`flats_two_storey_v1`, standalone pattern)
**Locations:** `loc_priya_flat` (001, 002, 004, 006), `loc_nadia_flat` (001) · **Zoom:** internal
only · **Footprint (shell):** 11×8 · **Assets:** `buildings/flats_two_storey_v1_exterior.png`
(shared) / distinct interior art per tenant.

*Exterior (shared shell)* — a plain two-storey block of flats tucked a street or two behind the
square: stone ground floor, rendered upper floor, a shared stair door, small paired windows,
modest and residential — deliberately less distinctive than the named shopfronts, since several
tenants share this shell.

*Priya's interior* — "more books than furniture, most of them borrowed from the shop": stacked
and shelved books everywhere, a small reading chair, a narrow bed, sparse furniture otherwise —
should read visually as a book-lover's small rented room.

*Nadia's interior* — "neat and tidy": a made bed, a tidy desk with a notebook and lamp, minimal
clutter, a window with a clear sightline toward the square (case 001 uses this sightline
narratively) — crisp and orderly in contrast to Priya's clutter.

### Clara's Flat — attached upper floor of Hobbs Cafe
**Location:** `loc_clara_flat` (001, 003, 005) · **Zoom:** internal only, `parent_location_id:
loc_hobbs_cafe` · **Assets:** interior only, painted as an upstairs cutaway layer of the cafe
building, not the standalone flats shell.

*Interior* — "neat to the point of silence": a small, spare upstairs room reached by a side
stair, one bed, a small table, minimal decoration, a shoebox tucked under the bed (case 001's
paperwork prop — paint as a plain, closed shoebox, not visibly labelled). Case 005 adds
documents relating to a property title on the table — same generic "papers on the table" prop
language applies.

> **Open question for the art lead:** `building_library.json`'s `location_bindings` maps
> `loc_clara_flat` to the standalone `flats_two_storey_v1` shell (as if it were its own placed
> building), but `town_map.py`'s canonical tags mark it `internal`-only with
> `parent_location_id: loc_hobbs_cafe` (i.e., it should nest inside the cafe cutaway as an upper
> floor). This brief follows the `town_map.py` reading since it matches the narrative ("above
> Hobbs Cafe... reached by a side stair") — please confirm before commissioning a second,
> separate exterior for Clara specifically.

### Elias's Cottage & Ruth's Cottage — `cottage_small_v1`
**Locations:** `loc_elias_house` (001, 004), `loc_ruth_cottage` (006) · **Zoom:** external ↔
internal · **Footprint:** 8×7 · **Assets:** `buildings/cottage_small_v1_exterior.png` /
`_interior.png` (shared shell, distinct interior dressing + Ruth's garden add-on)

*Exterior (shared shell)* — the smallest, cosiest private home type: a single-storey stone
cottage, low thatched-look or small-tile roof, one chimney, a compact garden footprint (`rear:
garden`), a single south-facing door. Elias's sits on the square's south side with his bedroom
window facing the fountain — worth a small painted window detail toward that sightline. Ruth's
sits on the square's far side with a garden extension.

*Elias's interior* (rooms: `living_room`, `bedroom`, `yard`) — quiet, retired-schoolteacher
modesty: a well-worn armchair, a small bookshelf, simple furniture, a bedroom with the
square/fountain-facing window called out above.

*Ruth's interior + garden* — a small cottage interior plus a distinct fenced garden with **a
large stand of foxglove (digitalis purpurea)** as the hero garden feature — paint it as an
attractive, ordinary cottage-garden flower bed (tall spikes, purple/pink bell flowers), not
ominous; a fireplace inside for warmth-coded domestic detail.

### Whittle & Cross Solicitors — `solicitors_office_small_v1`
**Location:** `loc_solicitors_office` (006) · **Zoom:** external ↔ internal ·
**Footprint:** 9×6 · **Assets:** `buildings/solicitors_office_small_v1_exterior.png` /
`_interior.png`

*Exterior* — a small, formal office building on the village's edge: dark timber signage with
gilt-look lettering plaque, a neat stone front, flower-boxed windows, more "civic/professional"
than domestic — think a miniature Georgian office frontage, restrained trim.

*Interior* (rooms: `reception`, `office`, `records_room`) — **reception**: a waiting chair or
two, a small desk. **office**: a solicitor's desk with document trays, a wall of box files,
a window. **records_room**: shelved deed boxes and files, more cramped and archival in feel.

### Riverside Fishery — `fishery_worksite_v1`
**Location:** `loc_fishery` (004) · **Zoom:** external only (worksite, no cutaway needed) ·
**Footprint:** 16×9 · **Assets:** `buildings/fishery_worksite_v1_exterior.png` /
`_interior.png` (interior slot reserved but likely unused — see open question)

*Exterior* — an open-air riverside worksite rather than a fully enclosed building: a simple
timber cleaning shed with an open front, a long catch table, nets and buckets, a wooden jetty
edge into the water, reeds along the bank. Keep it working-village rather than picturesque —
fish crates, a coil of rope, gulls optional.

> **Open question:** the library reserves an interior asset slot for the fishery, but its rooms
> (`cleaning_shed`, `catch_table`, `river_edge`) read as open-air sub-zones of one exterior scene
> rather than a roofless cutaway distinct from the exterior. Recommend treating this as
> exterior-only art (one asset covers all three sub-zones) unless the art lead wants a genuine
> separate interior framing for the cleaning shed.

## Outdoor landmarks & open zones (exterior only, no building shell)

| Location | Cases | Brief |
|---|---|---|
| `loc_village_square` | 001–006 | The town's central plaza — wide cobblestone, radiating paths to every shopfront, lamp posts, benches, sightlines to cafe/bookshop/clinic fronts. This is the "hub" shot; keep it the most detailed exterior scene since players return to it constantly. |
| `loc_fountain` | 001–005 | A worn stone fountain at the square's heart, "its rim worn smooth by generations of sitters" — round or square coping stones, gently animated water, a shallow basin. **Case 004 overlay:** a missing/loose coping stone on the east rim (`overlay_missing_coping`) — paint the coping as separable stone segments so one can be shown displaced. |
| `loc_elias_bench` | 003 | Elias's specific habitual bench within the square, facing the clinic and cafe — same bench prop as the square's generic benches, just called out as a fixed, named sub-zone (his usual spot, not a special design). |
| `loc_rear_alley` | 001, 002, 005 | A narrow packed-dirt service lane behind the cafe/bookshop: bins, stacked crates, a linen delivery bay, rear doors. Deliberately the least picturesque exterior in the village — narrow, shadowed by the flanking walls, service-only. **Case 005 overlay:** a scorched patch near the bins — soot-blackened crate stack and a section of wall (`overlay_fire_damage`/`overlay_ash`), fire fully out, no active flame in base art. |
| `loc_lake` | 004 | "Lover's Lake" — a serene, deep-water lake on the town's northern edge, reeds and lily pads along the shore, calm reflective water, a couple of overhanging trees. Romantic/peaceful mood, matches the reference art's lake corner. |
| `loc_woodland` | 004 | "Whispering Woodland" — dense woods bordering town, tall oak canopy, winding dirt paths, dappled light gaps, mossy rocks — should read as slightly enclosed/quieter than the open meadow. |
| `loc_meadow` | 004 | "Green Meadow" — an open sunny field of wildflowers and soft grass, the most open/bright exterior zone in the case, good strolling-path texture. |

## Reserved building type — not yet bound to a location

`house_small_v1` ("Small House", 11×9, rooms `sitting_room`/`kitchen`/`bedroom`) exists in
`building_library.json` with reserved asset paths but has no `location_bindings` entry yet — it's
a generic small-house shell for future/background use. Worth illustrating in the same pass since
it'll likely be needed for generated cases or background NPC housing, but it has no specific
narrative brief to work from — treat it as a plain, warm, unremarkable village house using the
same material language as the rest of the set.

## Cross-cutting notes for the artist

- **Reused shells, distinct dressing**: the flats shell and both cottages are deliberately reused
  across multiple named tenants — paint one strong exterior per shell type, then vary interiors
  only. Don't let the shared exterior read as "the same building" in a way that breaks immersion;
  minor trim/colour variation between placed instances is fine and expected (the map already
  supports rotation/tint per instance).
- **No case truth in base art**: props that carry evidence weight in some case (till weight,
  ledger pages, coats, letters, lighters, keys, vials, etc.) must be paintable as ordinary,
  unlabelled objects. Any damage/moved/discovered state is a swappable overlay layer per the
  asset bible's `overlay_*` convention — never bake a "this is the clue" look into the base prop.
- **Georgian house vs. cottage contrast**: Marcus's house is the one deliberately "grander"
  private residence in the set (Georgian symmetry, larger footprint); Elias's and Ruth's cottages
  and Owen's rougher yard-house should read as visibly humbler by comparison — this class
  contrast is worth preserving since it's implied by the case text.
- **Newsagent ground floor**: Ben's flat is narratively "above the newsagent," but there's no
  separate newsagent location in the data — if Ben's building gets its own exterior (see open
  question above), the ground floor should read as a small generic newsagent shopfront (papers
  rack, awning) with his flat as the floor above, rather than inventing a fifth flats shell.
