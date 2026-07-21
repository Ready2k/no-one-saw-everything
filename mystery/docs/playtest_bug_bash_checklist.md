# Playtest Bug Bash Checklist

Use this checklist to perform a full manual end-to-end verification of the game in playtest mode.

## 1. Setup & Generation
- [ ] Enable playtest mode: `MYSTERY_PLAYTEST_MODE=true npm run dev`
- [ ] Verify the floating Playtest Panel is visible and collapsible on the UI.
- [ ] Generate a deterministic case (e.g. Blackmail).
- [ ] Generate an LLM-assisted case with fallback allowed (disable internet or use an invalid key to test fallback generation).
- [ ] Activate the case.

## 2. Investigation & Case Board
- [ ] Rewind the timeline to a specific event.
- [ ] Inspect a gated clue (ensure it reveals and updates the board).
- [ ] Ask a structured interview question.
- [ ] Ask a free-text interview question (verify dynamic placeholders).
- [ ] Ask a vague contradiction free-text question and confirm it maps to a vague/unknown intent safely.
- [ ] Execute an explicit challenge via the "Challenge" button on the suspect's claim.
- [ ] Create a manual note and link it to an agent.
- [ ] Toggle markers on suspect cards (e.g., Red Herring, Cleared, Prime Suspect).
- [ ] Check the Playtest Panel: ensure `telemetry_event_count` and `player_action_count` are accurately incrementing.

## 3. Pre-Reveal Export
- [ ] Click "Download Export" from the Playtest Panel.
- [ ] Open the JSON file. Verify `export_visibility` is `"pre_reveal"`.
- [ ] Verify NO HIDDEN TRUTHS exist (no `killer_id`, `solution_concepts`, or `hidden_murder` events).

## 4. Accusation & Reveal
- [ ] Submit an accusation.
- [ ] Verify the Accusation Reveal displays correctly (including Detective Rating and Cited Evidence).
- [ ] Fill out and submit the post-reveal Feedback Form.

## 5. Post-Reveal Export & Refresh
- [ ] Click "Download Export" from the Playtest Panel again.
- [ ] Verify `export_visibility` is `"post_reveal"`.
- [ ] Verify the `accusation_result` and `feedback` payloads are present in the JSON.
- [ ] Refresh the frontend in the browser and confirm session persistence (the reveal screen should still be visible).
