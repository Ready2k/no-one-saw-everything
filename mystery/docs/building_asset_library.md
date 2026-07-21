# Building Asset Library

The town layout now supports authored building place bundles. A bundle keeps the
visual and spatial parts of a place together:

- `exterior_asset`: roofed overworld view
- `interior_asset`: roofless close-up view
- `footprint`: occupied tile rectangle
- `entrances`: door locations and facing direction
- `rooms`: interior semantic regions for case authoring
- `surrounding_rules`: deterministic path, fence, hedge, flowerbed, or service-path dressing
- `affordances`: the actions that can naturally happen there

The first bundle definitions live in
`backend/app/data/town/building_library.json`. They are deliberately data-only;
case truth and clue visibility stay in the case system.

The same library includes filler bundles for background settlement dressing:
farmhouse, barn, boathouse, windmill, and market stall. These are marked
`filler: true` and `investigable: false`; they can populate A1/C1-style settlement
cells and show a cutaway when needed without creating accidental investigation
locations or case surfaces.

## Placement flow

The developer Map Studio exposes these bundles through the `Place buildings`
tool. Clicking the map creates a `building_instances` record in
`backend/app/data/town/town_layout.json` and writes the generated dressing into
the normal editable tile layers. That makes the result deterministic and still
allows an artist to hand-tune exceptional case locations afterwards.

The backend helper in `backend/app/place_library.py` is the canonical generator
for the same derived tiles. The frontend mirrors the small deterministic rule
set for immediate editor feedback; saved layouts remain validated against the
library asset ids and world bounds.

The image paths in the initial library are reserved slots for the authored
building art. Once a building is illustrated, its exterior and interior files
can be dropped into the referenced public-art paths without changing case data
or placement logic.
