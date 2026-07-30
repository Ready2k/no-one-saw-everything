# 14. Presentation & Engagement Specification

## Purpose

The deduction engine (specs 01–13) is locked and correct: truth is generated
and hidden fairly, and the interview/challenge/judge loop works. This spec
does not change any of that. It defines a **presentation layer** on top of
the existing data-driven UI — cinematic scenes, character art, sound, and
meta-progression — so the game feels like a detective story instead of an
admin dashboard.

**Hard constraint:** nothing in this spec may leak hidden truth (`killer_id`,
`solution_concepts`, hidden events, lie flags) to the client ahead of
schedule. All new scenes consume the same player-safe projections
(`projections.py`) that the existing UI uses. Cinematics are skins on top of
already-computed, already-gated data — they do not introduce new backend
logic for revealing facts.

## Current State (baseline)

- Frontend is React + Vite with **no animation or audio library** installed
  (`mystery/frontend/package.json` — only `react`/`react-dom`).
- Suspect `portrait` is a raw emoji string (`Agent.portrait` in
  `backend/app/models.py`), rendered directly as text.
- Navigation is flat tabs (`App.tsx`: Case / Rewind / Map Replay / Places /
  Suspects / Case Board / Accuse) — no scene transitions, no opening
  sequence, no dedicated reveal moment.
- The accusation reveal (`Accuse.tsx` `Reveal` component) is a text/data
  panel, not a staged moment.
- No score persistence across cases, no daily/shared case, no replay stats.

## Design Principles

1. **Scenes are views, not new truth sources.** Every scene renders data the
   API already returns (or a purely cosmetic asset lookup) — never a new
   endpoint that exposes hidden state early.
2. **Degrade gracefully.** Missing art assets fall back to the current
   emoji/text rendering. The game must remain fully playable with zero art
   assets present (CI/tests should not depend on binary assets existing).
3. **Skippable.** Every cinematic/scene has a skip control and respects a
   "reduced motion" toggle (ties into the existing accessibility goals in
   spec 10).
4. **Additive to the data model.** New fields are optional with safe
   defaults so existing case JSON (`case_001`) keeps working unmodified.

## Phase A — Portrait & Character Presence

### Deliverables

- Extend `Agent` (backend `models.py`) with optional structured portrait
  data, keeping `portrait: Optional[str]` as the emoji/legacy fallback:
  ```python
  class PortraitState(BaseModel):
      calm: Optional[str] = None       # asset path
      defensive: Optional[str] = None  # asset path
      cracking: Optional[str] = None   # asset path, pressure near breaking

  class Agent(BaseModel):
      ...
      portrait: Optional[str] = None
      portrait_art: Optional[PortraitState] = None
  ```
- Expose `portrait_art` on `AgentPublic` via `projections.py` (it is not
  hidden-truth, so no gating needed beyond what's already public).
- Frontend: a `<Portrait agent expressionState />` component that picks
  `cracking > defensive > calm > emoji fallback` based on the suspect's
  current `pressure` level (already tracked in `session.py`).
- Wire `Portrait` into `Suspects.tsx` interview/challenge views in place of
  the raw emoji.

### Acceptance

- With no `portrait_art` data present, every existing view renders exactly
  as it does today (emoji fallback) — no regression, no broken layout.
- With `portrait_art` present for a suspect, their expression visibly
  changes as `pressure` crosses configurable thresholds (reuse existing
  pressure values from `challenge.py`; no new backend scoring logic).

## Phase B — Body Discovery Opening Scene

### Deliverables

- New frontend route/state `intro` that plays **before** the `overview` tab
  is reachable on a fresh session (skippable, shown once per case via
  local/session storage).
- Scene shows, per the spec-10 "Body Discovery Screen": victim name/portrait,
  discovery time, discovery location (name + illustration or map crop),
  a short scene description string, and nearby witnesses — all sourced from
  existing `CaseOverview` / `AgentPublic` / `LocationPublic` data already
  returned by `api.caseOverview()`.
- Primary CTA: **Begin Investigation** → transitions into the current tabbed
  UI (`overview` tab).
- Add optional `scene_description` and `discovery_location_id` /
  `discovery_time` fields to the case data (`case.json` schema in
  `models.py`) with safe defaults derived from existing fields
  (e.g. fall back to the first murder-adjacent event's location/time) so
  `case_001` does not require a data migration to keep working.

### Acceptance

- On first load of a case, the player sees the discovery scene before any
  tab; on reload mid-session it is not shown again.
- Skipping the scene is always possible (button + `Esc`).
- No hidden-truth field is referenced anywhere in this scene's payload.

## Phase C — Location Establishing Shots

### Deliverables

- `LocationPublic` gains an optional `illustration` asset path (falls back
  to no-op / current map crop if absent).
- When a location is selected in `Rewind.tsx`, `Places.tsx`, or
  `MapReplay.tsx`, show a brief (≤600ms, skippable/instant on repeat visits)
  illustrated transition before the existing data panel renders.
- Cache "already seen" locations per session so the transition only plays
  once per location per session (avoid annoyance on repeated scrubbing).

### Acceptance

- First visit to a location shows the transition; subsequent visits in the
  same session do not.
- Feature has a settings toggle to disable entirely (reduced-motion mode).

## Phase D — Challenge "Contradiction" Beat

### Deliverables

- In the existing challenge flow (`challenge.py` result → `Suspects.tsx`),
  add a frontend-only staged reveal when a challenge resolves as
  `contradiction_locked` or produces a new contradiction note:
  1. Freeze current view.
  2. Render the two conflicting claims side by side (data already present
     in the challenge response — claim text + conflicting evidence text).
  3. Animate them colliding / snapping together with a sound cue.
  4. Reveal the deterministic outcome text (unchanged backend behavior).
- No backend change required — this consumes the existing
  `resolve_challenge` response shape.

### Acceptance

- Only triggers on outcomes that already represent a locked contradiction
  in the current engine (no new classification logic added).
- Fully skippable; disabling animations shows the existing plain result
  immediately.

## Phase E — Accusation Ceremony

### Deliverables

- Replace the current `Reveal` panel in `Accuse.tsx` with a staged
  sequence, still built entirely from the existing `AccusationResult`
  payload (killer identity, score breakdown, true timeline, missed clues,
  red herring explanations — all already returned post-accusation per
  `judge.py`):
  1. Dim/black frame, suspense beat (skippable).
  2. Reveal killer portrait + name.
  3. Animate the true timeline drawing over the map (reuse
     `VisualMap`/`MapTimeline` components with the now-unlocked event data).
  4. Reveal Detective Rating with an animated score count-up.
  5. Show missed-clue and red-herring explanation cards.
  6. Epilogue cards: one short "what happened next" line per named suspect
     (new optional `epilogue` string per agent in `solution.json`, empty =
     no card shown).

### Acceptance

- No new hidden fields are sent to the client before this screen; it only
  renders once `api.reveal()` has already returned (i.e., post-accusation,
  matching current gating in `judge.py`/`session.py`).
- Skip control jumps straight to the final static breakdown (today's UI),
  so the ceremony is purely additive, never a blocker to reading results.

## Phase F — Audio

### Deliverables

- Add a lightweight audio library (e.g. Howler.js) to
  `mystery/frontend/package.json`.
- Ambient loop during investigation tabs (village ambience), distinct
  stinger cues for: clue discovered, contradiction locked, pressure
  threshold crossed, accusation submitted, case solved/failed correctly.
- Global mute + volume control persisted in local storage; respects
  reduced-motion/audio-off preference from Phase A–E toggles.

### Acceptance

- Game is fully playable and silent-by-default-safe (no autoplay violates
  browser policy — audio only starts after a user gesture).
- All cues are cosmetic; no gameplay state depends on audio.

## Phase G — Meta-Progression & Retention

### Deliverables

- **Detective Rank**: persist accuracy/score across completed cases
  (local storage is sufficient for MVP; no auth system required). Simple
  tiering (e.g. Rookie/Detective/Ace) shown on a small profile header.
- **Case history log**: list of past cases with score, accused, and
  correctness — purely additive, reads from existing per-case
  `AccusationResult` data, stored client-side.
- **Shareable case-closed card**: client-side generated summary (accuracy %,
  time taken, whether the player fell for the red herring) as a
  downloadable image or copyable text block — no backend change.
- **Case-of-the-day hook** (stretch, depends on phase 7 procedural
  generation already in place): a deterministic daily seed passed to the
  existing generation pipeline so all players on the same day get the same
  generated case. Backend-only change: seed selection, no new truth-gating
  logic.

### Acceptance

- Rank/history persist across page reloads via local storage and reset
  cleanly per browser profile (no server-side user accounts required for
  MVP).
- Case-of-the-day (if built) produces the same case for all players given
  the same date, validated by re-running generation with the same seed and
  diffing `case.json`.

## Explicitly Out of Scope

- Any change to how truth is generated, locked, or gated (specs 02, 09, 11,
  12 remain the source of truth).
- Multiplayer, accounts, or server-side persistence of player progress.
- Full tilemap/sprite game-engine rewrite. Legacy character sheets may remain
  temporary overhead-map markers, but they are not a visual style reference
  for environments, buildings, props, portraits, or cinematic Places scenes.

## Suggested Build Order

1. Phase A (portraits) — highest visual return for lowest engineering cost,
   touches one field and one component.
2. Phase E (accusation ceremony) — the emotional payoff moment, currently
   the flattest screen in the app.
3. Phase B (body discovery intro) — first impression, already described in
   spec 10 but never built.
4. Phase F (audio) — cheap, compounds with A/B/D/E.
5. Phase D (challenge beat) — needs Phase A portraits to land well.
6. Phase C (location shots) — nice-to-have polish once core beats exist.
7. Phase G (meta-progression) — retention layer, best done once the moment-
   to-moment experience (A/B/D/E/F) is solid.

## Acceptance Criteria (spec-wide)

This spec is complete when:

- A developer/agent can implement any single phase independently without
  needing to touch `judge.py`, `interview.py`, or `challenge.py` truth logic.
- Every new visual/audio feature has a working fallback with zero new
  assets present.
- `mystery/backend` test suite (`pytest tests/ -q`) still passes unmodified,
  proving no hidden-truth leakage was introduced.
- The existing playtest checklist
  (`mystery/docs/playtest_bug_bash_checklist.md`) still passes end-to-end
  with presentation features enabled.
