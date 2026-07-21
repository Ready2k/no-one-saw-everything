# Behavioural Authoring Guide

How to write a case *for* the behavioural layer — baseline memory, pressure
bands, tells, the composure meter, portrait swaps, and the notebook — rather
than merely inheriting it. The engine spec is `16_behavioural_tells_spec.md`;
this is the writer's contract. It is enforced by
`tests/test_behavioural_arcs.py`: a case that violates it fails CI.

The one rule above all others: **behaviour never says "lying."** Every tell,
habit, and deviation describes visible behaviour that an innocent under strain
could also show. The player connects behaviour to evidence; the game never does
it for them.

## The pressure bands

Cumulative per-suspect pressure (0–1) drives everything. All thresholds are
shared between backend (`behavioural_tells.pressure_band`) and frontend
(`demeanour.ts`, `Portrait.tsx`):

| band | pressure | meter label | portrait |
|------|----------|-------------|----------|
| 0 | < 0.10 | Composed | calm |
| 1 | 0.10 – 0.35 | Guarded | calm (defensive from 0.30) |
| 2 | 0.35 – 0.60 | Rattled | defensive |
| 3 | 0.60 – 0.85 | Cornered | cracking (from 0.70) |
| 4 | ≥ 0.85 | Breaking | cracking |

Author `pressure_delta` values against these lines. The smallest delta that
should register with the player is **0.10** (one landed deflect = Guarded); a
partial admission is worth **0.20–0.25**; a confession (`contradiction_locked`)
is **0.40**. A related-but-wrong challenge nudges **0.05** and deliberately
stays under every threshold.

## 1. Calm baseline opportunities

The game quietly remembers how each suspect behaves when calm — their *manner* —
from their **first answer given under 0.35 pressure**. Later reads say
"different from earlier" against it.

What this asks of the case data:

- **Every living principal needs an interview pack** (`interviews.json`), so
  there is something calm to answer. (Enforced.)
- **Author the manner** with `baseline` on the agent in `agents.json`:

  ```json
  "baseline": {
    "habit_category": "voice",
    "habit_text": "his voice runs level and unhurried, like a man reading minutes he wrote himself",
    "deviation_cue": "The level voice from earlier has gone exact — times, quantities, the order of events — precision standing in where ease used to be."
  }
  ```

  `habit_text` completes "at ease, {habit_text}" — present tense, lowercase
  start. `deviation_cue` is a full sentence: the "different from earlier" tell.
  Unauthored agents get a seeded stock manner; that is a fallback, not a goal —
  **give every principal an authored one, and make them distinct**: one
  over-explains, one freezes, one goes flat, one becomes too precise. Two agents
  may share a `habit_category`; they must never share a manner. (Enforced for
  case_007.)
- The baseline is chosen by character, never by guilt. The killer's calm manner
  must be as ordinary as anyone's, and the deviation cue must read equally true
  of an innocent under strain.

## 2. Pressure-band escalations

The first answer after a suspect *enters a new band* carries their deviation cue
as a tell — once per band, so it stays news. Design the killer's challenge tree
so the bands are actually reachable:

- **The killer's positive deltas must sum to ≥ 0.7** so the cracking portrait is
  earnable, and the route should pass through the middle bands rather than jump
  (deflects at 0.10–0.15, a partial admission near the middle, the confession at
  the top). (Enforced: sum ≥ 0.7 + a `contradiction_locked` rule.)
- Model arc — Marcus, case_007: alibi lie at 0 → deflects (0.10, 0.15) →
  partial admission 0.25 → 0.50 → deflects on the fallback story (0.12, 0.12) →
  0.74 → confession 0.40 → 1.0. Every band gets a beat; the fallback story
  ("kitchen, alone") gives the middle bands their own claim to attack.

## 3. Relief beats (`reveal_innocent_secret`)

Innocents need somewhere for their arc to *go* that is not upward. A
`reveal_innocent_secret` rule with a small **negative** delta lets a challenged
innocent hand over what they were withholding and visibly relax — the meter
refills a little, and the player learns that pressure released is also an
answer. Keep the anchor as information *withheld* (pride, confidentiality,
embarrassment), never a retraction of fact (see CLAUDE.md invariant 3).

Every suspect the case invites the player to challenge must have a route that
goes somewhere: **positive deltas ≥ 0.35** (reaches Rattled) *or* a resolution
beat (`reveal_innocent_secret`, `reframe`, an admission, or any relief delta).
A challenge tree that only shrugs teaches the player to stop challenging.
(Enforced.)

## 4. Confession and partial-admission beats

- `partial_admission` is the hinge of a killer arc: it should **create the
  fallback claim** (`new_claims`) that the endgame attacks, and its delta should
  land the suspect in Rattled where the portrait and meter both move.
- `contradiction_locked` is the confession: reserve it for the killer, gate it
  with `required_prior_clue_ids` so it cannot fire before the middle of the arc,
  and give it the 0.40 delta so the break reads on every channel at once
  (portrait to cracking, meter toward Breaking, strong tell, stinger).

## 5. Notebook-pinnable behavioural clues

Noticeable/strong tells can be pinned to the suspect's notebook page with the
question they followed, and the Observe read pins whole. Write for that:

- A deviation cue should stand alone as a note — *"The stories have stopped.
  Every answer now is exactly as long as it has to be."* reads as a finding
  even out of context.
- Pair authored `emotional_shift` values with the moments worth pinning: the
  shifts colour the meter for a turn and cue the player that this answer was
  load-bearing.
- Portraits: every principal needs `calm`/`defensive`/`cracking` art (plus
  `deceased` for the victim) wired in `agents.json`, or the swap fails silently
  to calm. (Enforced.)

## Checklist for a new case

- [ ] Interview pack for every living principal
- [ ] Authored `baseline` for every principal, all manners distinct
- [ ] Killer: deltas sum ≥ 0.7, beats in every band, `partial_admission` that
      creates the fallback claim, gated `contradiction_locked` confession,
      non-empty epilogues
- [ ] Each challengeable innocent: a relief/reframe/admission beat or ≥ 0.35 route
- [ ] Red herrings carry an `innocence_anchor` (withheld, not retracted)
- [ ] Portrait art: calm/defensive/cracking for all principals, deceased for victim
- [ ] `pytest tests/test_behavioural_arcs.py` green
