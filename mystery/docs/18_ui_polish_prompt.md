# UI Polish Handoff Prompt

You are working in `/Users/jamescregeen/Code_Projects/generative_agents/mystery`.

The behavioural interview system is already implemented and verified. Your job is to do the next UI-focused pass so players naturally discover and use the system without turning it into a tutorial overlay.

## Current Behavioural System

Already implemented:

- Behavioural tells on ask/challenge responses.
- Pressure/composure meter with bands.
- Portrait state swaps: `calm`, `defensive`, `cracking`, `deceased`.
- Pressure/tell-driven mugshot animations.
- `POST /api/interview/observe`.
- One Observe read per fresh exchange.
- Considered read card in the interview UI.
- Notebook pinning for tells and considered reads.
- Baseline observation memory:
  - calm answer captures an initial manner,
  - later pressure-band escalations can emit "different from earlier" comparison tells,
  - Observe cards show comparison chips such as `manner noted`, `same as earlier`, `changed from earlier`, and `nothing like earlier`.
- Authorable baselines via optional `Agent.baseline`.
- Case authoring guide in `docs/17_behavioural_authoring_guide.md`.

Recent validation reported by the previous session:

- Backend suite: 348 tests passing.
- Frontend typecheck/tests clean.
- No frontend changes were needed for the authoring pass.

## Goal

Make the behavioural system feel discoverable, readable, and useful in normal play.

Do not add a modal tutorial or explanatory wall of text. The UI should teach through placement, labels, tooltips, state, and one or two subtle first-use affordances.

## Desired UI Work

### 1. Subtle Observe Onboarding

Make the player understand that Observe is valuable before pressure rises.

Possible directions:

- Improve the Observe button label, tooltip, empty state, or disabled copy.
- Add a restrained first-time nudge near the interview controls when a suspect is calm and a fresh answer is available.
- Make calm Observe feel professionally useful, not like a wasted action.
- Preserve the existing rule: one Observe per fresh exchange.

Avoid:

- Tutorial modals.
- Long in-app explanations.
- Any wording that implies Observe detects lies.

### 2. Behavioural Readability Polish

The interview view should make the relationship between composure, portrait, tells, and considered read clear at a glance.

Check and improve:

- Visual priority of the composure meter.
- Placement and hierarchy of the Behavioural read panel.
- Placement and hierarchy of the Considered read card.
- Comparison chips for baseline memory.
- Reduced-motion behaviour.
- Mobile layout and text wrapping.

The player should quickly feel:

> Something changed. I should interpret it, not treat it as proof.

### 3. Notebook Behaviour Section

Pinned behavioural material should be grouped separately from hard evidence.

Implement a small `Behaviour` subsection on each suspect's notebook page/card for:

- pinned observable tells,
- pinned considered reads,
- baseline/deviation notes if they are currently pinned through the same flow.

Keep it concise. Behaviour notes are clues about manner, not evidence of guilt.

### 4. Active Case/Restart Clarity

Earlier playtesting found that backend restarts revert the active case to `case_001`, which can confuse work on `case_007`.

Either:

- make the current active case explicit in the UI where relevant,
- or improve the startup/restart path so the current case is persisted/restored,
- or document why this should remain a dev-only quirk and add a visible dev affordance.

Choose the smallest useful fix that fits the existing architecture.

### 5. Blind Playtest Checklist

Add a short markdown checklist for a new player or tester. It should verify:

- they discover Observe,
- they try observing while calm,
- they notice a later deviation,
- they avoid treating tells as proof,
- they pin at least one useful behavioural note,
- notebook grouping makes sense.

This can live in a new docs file or extend an existing playtest checklist.

## Implementation Notes

- Read the existing frontend before changing it:
  - `frontend/src/views/Suspects.tsx`
  - `frontend/src/styles.css`
  - `frontend/src/types.ts`
  - any notebook-related components/views.
- Follow existing design language. This is an investigative game UI, not a SaaS dashboard or marketing page.
- Use concise in-app copy. No large explanatory panels.
- Preserve fair-play language:
  - tells are observations,
  - deviations are changes,
  - neither means "lying" or "guilty".
- Keep animations respectful of `prefers-reduced-motion`.
- Do not change backend behaviour unless needed for active-case clarity or notebook grouping.
- Do not touch unrelated untracked work unless required.

## Verification Expectations

Run at least:

- frontend tests/typecheck/build, following the repo's existing scripts,
- focused backend tests if any backend or API contract changes are made.

Also do a quick browser pass:

- desktop interview view,
- mobile/narrow interview view,
- calm Observe state,
- already-observed disabled/refusal state,
- pressure escalation with comparison chip,
- pin to notebook,
- notebook behaviour grouping.

## Suggested Definition Of Done

- Observe is easier to discover without a tutorial modal.
- Calm Observe reads as a good detective move.
- Behavioural read and Considered read cards are visually clear and not noisy.
- Notebook separates behavioural notes from evidence.
- Active case/restart confusion is reduced or clearly surfaced.
- Blind playtest checklist exists.
- Tests/build pass.
