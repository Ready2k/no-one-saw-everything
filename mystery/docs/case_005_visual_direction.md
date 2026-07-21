# Case 005 visual direction — The Rear Alley Fire

Case 005 is the first neo-noir art migration. Its visual language is rain-dark
English stone, damp blue morning light, warm practical lamps, physical working
materials, and clean investigation sightlines.

## Player-safe art rule

Location art establishes atmosphere and provides readable search zones. It must
not show undiscovered clues, a culprit identifier, a body, a weapon, or any
other hidden state. The existing clue/session projection remains the only
authority for evidence visibility.

## First location slice

| Location | Asset | Searchable visual zones |
| --- | --- | --- |
| Rear Alley | `rear_alley_fire_hd.png` | scorched crates, bins, service door, wet cobbles |
| Clara's Flat | `clara_flat_dawn_hd.png` | desk, coffee table, linen table, kitchen |
| Owen's House & Yard | `owen_yard_dawn_hd.png` | office door, workshop, timber stacks, truck |

Future Case 005 art should preserve this palette: midnight navy, charcoal,
damp timber, antique brass, and very restrained ember orange. Evidence markers
should stay UI-driven and use antique gold; contradiction states may use muted
burgundy. No environmental art should change the case's locked truth.

## Cast and overhead plates

Six case-scoped dossier portraits cover Clara, Owen, Ben, Nadia, Elias, and
Col. They establish age, role, and temperament only; no pose, garment, or
lighting choice encodes guilt. The village and rear-alley overhead plates are
briefing/reference art. They do not replace the coordinate-accurate canonical
map used by Replay, so event and evidence anchors stay reliable.

## Investigation interaction

The location search view has a visual field kit: hand lens, raking light, and
reference scale. These are visual aids, not alternate deduction paths. The
existing magnifier, zoom, pan, and server-authorized discovery flow remain the
only way a hidden clue becomes known. Five recovered Case 005 clues gain
forensic evidence plates in the found-evidence card only after the API returns
them as discovered.

The environmental clue hotspots for the new illustrations are authored in the
inspection endpoint rather than randomly seeded: documents occupy Clara's
desk, the letter/lighter sit in the scorched crate zone, the belt is near the
bins, and yard/back-lane clues use their matching physical zones. This changes
only visual placement; prerequisite gates and discovery authority are unchanged.
