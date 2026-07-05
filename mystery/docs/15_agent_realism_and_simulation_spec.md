# 15. Agent Realism & Background Simulation Specification

## Purpose

Interviews currently feel authentic on a per-turn basis (real emotion in the
rewrite prompt, in-character improv for off-script questions, a diegetic
deflection instead of a broken-looking fallback) but each turn is still a
single, isolated LLM call — a suspect has no sense of what's happened
elsewhere in the case, no persistent voice beyond a 6-message window, and
zero awareness of other suspects. This spec explores what a "background
simulation" layer would add, scoped so it deepens the same single-call
pipeline rather than replacing it with an agent framework.

This document was written after evaluating whether to adopt a multi-agent
orchestration framework (e.g. Google ADK) with long-lived Ollama-backed
agents. **Recommendation: no**, for this project — see
[Framework Recommendation](#framework-recommendation) at the end. The phases
below get most of the same realism gains without one.

**Hard constraint (same as spec 14, applied to simulation state instead of
presentation):** the truth (`killer_id`, `solution.*`, hidden events, lie
flags) is generated and locked before play and must never leak. Nothing in
this spec may give the truth to an LLM as context, change how
`case_store.py`/`generator.py` lock a case, or let an agent's improvised
output become case-solving evidence. Every phase below is a *richer prompt
input* to the same `rewrite_interview_answer` /
`generate_open_ended_response` / sanitiser pipeline (`dialogue_rewriter.py`)
— none of them add a new place where hidden truth could leak, and none of
them change what the deterministic engines (`interview.py`, `challenge.py`,
`judge.py`) compute as ground truth.

## Current State (baseline)

- One LLM call per player action (`rewrite_interview_answer`,
  `rewrite_challenge_response`, `generate_open_ended_response`), each
  stateless from the model's point of view — all conversational memory is
  reconstructed and injected fresh every call via `recent_exchange` (last 6
  transcript messages for *this* agent only).
- Per-agent `pressure` (`session.py`) is the only piece of cross-turn state
  that feeds the prompt (`emotion` param, wired in this session).
- No agent is aware of: other suspects' interviews, challenges the player
  has run, clues discovered outside their own reveals, or the passage of
  session time.
- Measured local latency this session: ~9-20s per call against
  `gemma4:latest` on a local Ollama host. This is the binding constraint on
  anything that would add more calls per player action.
- No persistent "belief" or "memory" state per agent beyond the transcript
  and pressure float.

## Design Principles

1. **Simulation informs flavour, never facts.** Any new context fed into a
   prompt is world-state color (what's publicly known, how rattled someone
   is), never a new source of truth. `allowed_facts` continues to be built
   only from already-discovered clues and already-recorded claims, exactly
   as today.
2. **No cross-agent fact laundering.** One suspect's improvised answer
   (from `generate_open_ended_response`) must never become an "established
   fact" fed into another suspect's prompt as if it were real. If suspect A
   invents a hobby, suspect B can't later be asked to corroborate it as
   though it were in the case data.
3. **Deterministic gating stays authoritative.** Clue discoverability,
   challenge resolution, and accusation scoring remain 100% deterministic
   and untouched by any of this. Simulation state is read by prompts, never
   by `challenge.py`/`judge.py` logic.
4. **Respect the latency budget.** Given ~10-20s per call against a local
   model, any design that adds LLM hops to the player's synchronous request
   path is a regression, not an improvement. Prefer precomputed/batched
   state (updated between player actions, not during them) over live
   multi-agent chains.
5. **Every new surface gets a sanitiser and a no-leak test.** Consistent
   with the rest of this codebase — if a phase adds a new place text
   reaches the player, `_sanitise` runs on it and a dedicated test (in the
   style of `test_open_ended_no_leak.py`) proves it can't leak.

## Phase A — Cross-Suspect Awareness (Reactive World-State Digest)

The cheapest, highest-value step: let a suspect's answers reflect *public*
events elsewhere in the case, without any agent autonomy at all.

### Deliverables

- A `build_world_state_digest(case, session, agent_id) -> list[str]`
  helper (new, e.g. in `session.py` or a small new module) that produces a
  handful of short, factual, already-public lines such as:
  - "The detective has discovered `<N>` pieces of evidence so far."
  - "Ben Carter's alibi has been directly challenged and broken." (only if
    that challenge's outcome is already public via `ChallengeRecord`)
  - "Several suspects seem tense; the investigation is escalating." (a
    coarse aggregate of pressure across *other* agents — never a specific
    number for someone else, since a suspect wouldn't know another
    suspect's private stress level)
- Thread this digest into `rewrite_interview_answer` /
  `generate_open_ended_response` as a new `world_state` prompt field
  (new prompt lines in `interview_rewrite_user.txt`, `challenge_rewrite_user.txt`,
  `open_ended_user.txt`), clearly labeled as *atmosphere*, not fact:
  `"General mood in the village (for atmosphere only, do not treat as something you personally witnessed): {world_state}"`.
- No change to `allowed_facts`/`forbidden_facts` semantics — this is a
  separate, clearly-scoped prompt field so the sanitiser's existing checks
  keep working unmodified.

### Acceptance

- With zero discoveries/challenges, `world_state` is empty/neutral and
  behavior is identical to today.
- After a challenge breaks a claim, a *different* suspect's next answer can
  reference the general mood shifting, without stating the broken claim's
  content verbatim (still guarded by the existing `_sanitise` unsupported-
  fact and forbidden-fact checks, since the digest is on the allowed side
  of the prompt, not smuggled into `allowed_facts`).
- New no-leak test: mock a digest containing a specific other-suspect
  detail and assert the sanitiser still blocks it if the LLM parrots it
  back as a first-person claim.

## Phase B — Persistent Voice & Session Memory

### Deliverables

- A small authored `voice_card` per agent (case data, optional field on
  `Agent`, e.g. 1-2 sentences of speech mannerisms: "clips his sentences
  when defensive," "over-explains when nervous") included in every rewrite
  prompt's PERSONA block. Purely descriptive, authored ahead of time — no
  new generation risk.
- Replace the flat last-6-message `recent_exchange` window with a running,
  cheap **extractive** summary (not another LLM call — just keep the
  transcript's `deterministic_text` lines, which are already leak-safe by
  construction) for anything beyond the last 6, so a long interrogation
  doesn't "forget" its own opening.

### Acceptance

- Two interviews with identical questions but different `voice_card`s
  produce noticeably different phrasing (spot-checked, not automatable
  beyond a smoke test).
- A 15+ turn interview references something said in turn 2 correctly when
  asked a callback question late in the conversation.

## Phase C — Offline Belief-State Batch Updates (highest value, highest care)

This is the closest analog to "multi-agent," scoped to stay safe.

### Deliverables

- After specific session events (a challenge resolves, an accusation-
  relevant clue is discovered) — **not** on every player turn — run a
  single batch LLM call per *affected* agent (not all agents, not live
  during the player's request) that produces a small structured
  `AgentBeliefState`: `{worry_level: float, current_suspicion_target:
  Optional[agent_id], talking_points: list[str]}`. This runs
  asynchronously between player actions (e.g. fire-and-forget after the
  triggering endpoint returns, or lazily on the next interview request for
  that agent if not yet computed), never inline in the request the player
  is waiting on.
- `talking_points` are still just flavour fed into future prompts the same
  way as Phase A's digest — never `allowed_facts`, never read by
  `judge.py`.
- `current_suspicion_target` (if the agent now "suspects" a specific other
  suspect) is validated against solution-adjacent forbidden facts before
  being trusted — i.e. it goes through the same forbidden-fact check as
  any rewrite output, and if it happens to match hidden truth, the whole
  belief update is discarded and logged, not partially used.

### Acceptance

- Turning this feature off (config flag) restores exactly Phase A/B
  behavior — it's additive, not a replacement for the deterministic layer.
- A dedicated no-leak test asserts a belief update that resolves toward
  the actual killer is discarded rather than surfaced.
- Latency: belief updates never add to the player-facing request path —
  verified by timing an interview call before and after this phase lands.

## Explicitly Out of Scope — True Inter-Agent Simulation

Suspects independently exchanging information with each other (gossip that
changes what they'd say *before* the player asks), or claims that mutate
after case generation based on simulated agent-to-agent interaction, is
**not** a phase here. It would require redesigning the fairness contract
this whole codebase relies on — `solution.json` and the seeded claims are
locked at generation time and validated by `test_golden_solve_path.py`;
letting simulated agents alter claims post-generation risks an unsolvable
or self-contradicting case with no current test coverage for that failure
mode. If this is ever wanted, it deserves its own spec and its own
solvability-validation strategy, not an extension of this one.

## Framework Recommendation

Google ADK (or a similar multi-agent orchestration framework) is built for
agent **autonomy** — planning, tool use, agents deciding what to do next
and coordinating with each other. Nothing in Phases A-C needs that: each is
still exactly one `generate_json`/`generate_chat` call with a known request
shape, going through the same sanitiser this codebase already tests. Adding
an orchestration runtime would:

- Multiply latency per player action (already the binding constraint at
  ~10-20s/call against local Ollama) with agent-to-agent hops or planning
  loops that add no value here.
- Expand the leak surface past what `_sanitise` and the no-leak test suite
  are built to check — every new agent-to-agent message is a potential new
  leak path with no existing guard.
- Add a new heavyweight dependency and a new class of non-deterministic,
  hard-to-test emergent behavior, in a codebase whose fairness guarantee
  depends on the opposite: locked, deterministic truth with the LLM
  strictly downstream of it.

The one place a framework-shaped tool could genuinely help is Phase C's
batch belief-update step, if it grows into "update N agents' beliefs
reliably, in parallel, with retries" — at that point, a lightweight task
queue (e.g. a simple background worker) is the right scope, not a full
agent framework, and it should be evaluated narrowly as a batch-processing
tool, not adopted as the interview engine's runtime.
