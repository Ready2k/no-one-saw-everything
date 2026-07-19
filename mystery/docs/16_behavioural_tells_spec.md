# Behavioural Tells Spec

## Purpose

Make interviews feel like observation, not only text parsing. Players should be able to notice facial, vocal, and posture clues while questioning suspects, then decide whether those clues matter.

This system is not a lie detector. A tell means "something changed" or "this topic landed," not "this person is guilty." Innocent suspects can look rattled; guilty suspects can stay controlled.

## Existing Foundations

- `Agent` already has personality inputs: `honesty_baseline`, `memory_reliability`, `conflict_avoidance`, relationships, and `voice_card`.
- `AnswerRule` already carries hidden `truthfulness` plus public `emotional_shift`.
- `ChallengeRule` already carries `emotional_shift` and `pressure_delta`.
- `Session` already persists per-agent pressure.
- `Portrait` already switches between `calm`, `defensive`, and `cracking` using pressure thresholds.
- `ComposureMeter` already exposes pressure as a readable UI state.

## Design Goals

- Add readable behavioural observations to interview and challenge responses.
- Keep mystery truth fair: tells never expose hidden truth labels directly.
- Make tells useful but ambiguous: they help players choose what to challenge or revisit.
- Let personality change the signal. A composed liar should not behave like a nervous honest witness.
- Keep the first implementation deterministic and testable.

## Non-Goals

- No probabilistic guilt solver.
- No "is lying" banner.
- No requirement that every answer produces a tell.
- No LLM-only logic. LLM rewrites can flavour text, but tells must come from deterministic state.
- No new portrait state beyond the current `calm`, `defensive`, `cracking`, and `deceased` until the tell loop proves itself.

## Player Experience

During an interview, after an answer or challenge, the player may see a small "Behavioural read" panel:

- "Her eyes flick to the storeroom door before she answers."
- "He answers too quickly, then repeats the time unprompted."
- "Their hands go still when the ledger is mentioned."

The panel uses categories and intensity:

- `gaze`
- `voice`
- `hands`
- `posture`
- `timing`
- `overexplaining`

Intensity:

- `subtle`
- `noticeable`
- `strong`

## Fairness Rules

1. Tells are player-facing observations, not proof.
2. A false or mistaken answer is more likely to produce a tell, but true answers can also produce tells when the topic is emotional.
3. Confession and contradiction challenges may produce strong tells because the player has already earned them with evidence.
4. The exact hidden `truthfulness` value must not cross the API.
5. Generated tell text must describe visible behaviour only.

## MVP Implementation

- Add `ObservableTell` model.
- Add `observable_tells` to:
  - `AskResponse`
  - `ChallengeRecord`
  - `InterviewMessage`
- Generate tells in `interview.py` from:
  - answer truthfulness
  - `emotional_shift`
  - current pressure
  - agent honesty/conflict/personality fields
  - question type/topic
- Generate tells in `challenge.py` from:
  - challenge outcome
  - `emotional_shift`
  - pressure delta
  - new pressure
- Project tells through public API responses.
- Render tells in the Suspects interview view.
- Persist tells in session transcript messages.
- Add tests proving:
  - public ask responses include tells without truth labels
  - challenge responses include tells when pressure lands
  - stored transcript messages keep tells

## Future Phases

### Phase 2: Baselines — BUILT

Per-agent calm baseline is captured from the first unpressured answer
(`session.baselines`, engine in `behavioural_tells.baseline_habit`). The first
answer after a suspect enters a new pressure band carries one "different from
earlier" tell; Observe compares against the baseline every time. Writers can
author each principal's manner via `Agent.baseline` — see
`docs/17_behavioural_authoring_guide.md`.

### Phase 3: Observation Skill — BUILT

`POST /api/interview/observe`: one considered read per fresh exchange, built only
from player-visible signals. Guarded by `tests/test_observe.py`.

### Phase 4: Notebook Integration — BUILT

The considered read pins to the suspect's notebook page; noticeable/strong tells
in the transcript pin with the question they followed.

### Phase 5: Asset Payoff

Generate and wire `defensive` and `cracking` portraits for the main cast so behavioural text, composure, and facial art move together.

Main character portrait set:

- `ben`
- `clara`
- `col`
- `dr_haig`
- `elias`
- `fred`
- `isabella`
- `marcus`
- `nadia`
- `owen`
- `priya`
- `ruth`
- `solicitor`

### Phase 6: Motion Payoff

Use pressure and tells to animate the interview mugshot:

- defensive pressure: guarded breathing
- cracking pressure: slight tremor
- gaze tells: small glance/shift
- voice/timing tells: tightening pulse
- hands/posture tells: flinch
- overexplaining tells: restless movement

Animations must respect `prefers-reduced-motion`.

## Progress

- [x] Spec file created
- [x] Backend tell model added
- [x] Interview tells generated and projected
- [x] Challenge tells generated and projected
- [x] Transcript persistence updated
- [x] Frontend types updated
- [x] Interview UI renders tells
- [x] Tests added or updated
- [x] Focused backend tests pass
- [x] Frontend build passes
- [x] Full backend suite passes
- [x] Pressure/tell-driven mugshot animations added
- [x] Defensive portraits generated for main cast
- [x] Cracking portraits generated for main cast
- [x] Main case data wired to defensive/cracking portrait assets
- [x] Portrait contact sheet reviewed
