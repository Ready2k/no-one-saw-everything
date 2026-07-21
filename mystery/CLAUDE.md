# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**No One Saw Everything** — a fair-play murder mystery game. The player arrives after a
murder, rewinds the morning to observe a village of sims, interrogates them, collects
contradictions, and builds a case on a board. FastAPI backend + React/Vite frontend.

**The core invariant that shapes the whole codebase:** the truth (killer identity, motive,
method, lie flags, hidden events) is generated and locked *before* play, and the API must
**never** leak it to the client. Player-safe views are enforced at the API boundary in
`projections.py`; the truth is only revealed *after* an accusation via `/api/reveal`. Many
tests exist purely to guard this (`test_no_leak.py`, `test_llm_dialogue_no_leak.py`,
`test_free_text_interview_no_leak.py`, `test_isolation.py`). When touching projections,
interviews, challenges, or LLM rewrites, assume a no-leak test is watching — and if you add a
new player-facing surface, add one.

## Commands

Run both services from the project root:

```bash
./start.sh        # backend :8010, frontend :5173 — bootstraps venv + npm install if missing
./stop.sh         # kills pids in .pids/
```

Backend only (module is `app.main:app`, run from `backend/`):

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8010
```

Frontend only (Vite dev server proxies `/api` → `:8010`):

```bash
cd frontend
npm install
npm run dev        # dev server :5173
npm run build      # tsc -b && vite build
npm run preview
```

Tests (pytest doubles as the case-fairness validator):

```bash
cd backend
.venv/bin/python -m pytest tests/ -q                         # all
.venv/bin/python -m pytest tests/test_no_leak.py -q          # one file
.venv/bin/python -m pytest tests/test_golden_solve_path.py::test_name -q   # one test
```

Per CLAUDE.md workspace rules: after changing backend Python, restart uvicorn and confirm the
change is live; for any UI/visual change, verify in the running app, not just via tests.

## Backend architecture (`backend/app/`)

The design deliberately separates **immutable case truth**, **mutable player state**, and
**player-safe projections**, so an LLM can be swapped in behind the deterministic engines
without touching the API or leaking truth.

- `models.py` — Pydantic schemas (spec 11): case, agents, locations, events, clues, memories,
  notes, claims, challenges, solution, accusation.
- `case_store.py` — loads and caches the immutable case bundle from `data/<case_id>/`.
  (The README still calls this `store.py`; the file is `case_store.py`.)
- `session.py` — in-memory mutable player state, **one global session per case for the MVP**
  (discoveries, claims, notes, transcripts, pressure, challenges, accusation result, markers,
  tutorial progress, event log). Reset via `/api/session/reset`.
- `projections.py` — the truth firewall: strips hidden fields and builds player-safe views at
  the API boundary. Visibility levels: public / public-partial / private / hidden.
- `interview.py` — deterministic grounded Q&A. Answers derive from seeded memories + lie
  state; claim extraction and gated clue reveals.
- `challenge.py` — deterministic challenge resolution: confront a claim with discovered
  contradictory evidence → scripted outcomes, pressure tracking, contradiction notes. Rejects
  undiscovered evidence / mismatched claims / the victim.
- `judge.py` — deterministic accusation scoring (killer/motive/method/opportunity by
  keyword-concept match against `solution.json`) + the gated post-accusation truth reveal.
- Free-text interrogation (built, beyond what the README's "not yet built" note says):
  `free_text_api.py`, `question_classifier.py` / `question_intent_classifier`,
  `reference_resolver.py` — classify a typed question, resolve references, route to grounded
  answers without leaking.
- Procedural generation: `generator.py`, `mystery_architect.py`, plus `analyzer.py`,
  `validator.py`, `map_layout.py`, `telemetry.py`, `tutorial.py`.
- `main.py` — all FastAPI routes under `/api/*`. Note `ACTIVE_CASE_ID = "case_001"` is the
  default active case set at import time.

### LLM layer (`backend/app/llm/`)

LLM use is **optional and always has a deterministic fallback** — the engine computes the real
outcome first, then optionally asks an LLM only to rewrite the *flavor* text. Pipeline:

```
Deterministic Result → Optional LLM Rewrite → Sanitiser → Display Text
```

The sanitiser (`dialogue_rewriter.py`) rejects any rewrite that leaks role labels, hidden
facts outside the pre-computed "allowed facts", or JSON artifacts, and falls back to the
pre-authored text. `config.py` resolves provider/model/key with this precedence: saved
settings (`data/llm_settings.json`, editable via the in-app LLM Settings modal / `/api/llm-settings`)
override env vars. Providers: `fake` (default, no network), `auto` (probe for a reachable
OpenAI-compatible host), `openai_compatible`. Env vars: `MYSTERY_LLM_PROVIDER`,
`MYSTERY_LLM_BASE_URL`, `MYSTERY_LLM_API_KEY`, `MYSTERY_LLM_MODEL`, `MYSTERY_LLM_TIMEOUT_SECONDS`,
`MYSTERY_LLM_DIALOGUE_ENABLED`. Also `MYSTERY_PLAYTEST_MODE=true` unlocks playtest endpoints.
Case generation/assembly: `mystery_architect.py`, `case_assembler.py`, `discovery.py`,
`schemas.py`, prompts in `llm/prompts/`.

#### Generated-case timeline (why generated cases aren't case_001 reskins)

The deterministic generator (`generator.py`) fills the *one* template
(`data/templates/blackmail.json`, itself case_001's events with `{ROLE}` placeholders) by
string substitution only. On its own that makes every generated case replay case_001's exact
morning and routines — the events (Rewind) and each agent's `routine_summary` (Routine) were
never regenerated. `llm_assisted` mode fixes this with **Phase 5: Timeline** in
`mystery_architect.generate_llm_case` (schemas `BeatPlan`/`RoutinePlan`/`TimelinePlan`), whose
output is compiled by `timeline_compiler.compile_timeline` (called from `assemble_case`).

The compiler keeps a deliberate boundary: the **puzzle spine is kept, not regenerated** — the
murder, the body discovery, and every clue-bearing event stay exactly as the template produced
them, because their times are coherent with the clue text and the murder (e.g. a "thud heard at
the time of death" must not drift). Only the **ambient flavour layer** (public routine/movement
events carrying no clue) is dropped and replaced with the LLM's authored beats, and every
`routine_summary` is refreshed. Invariants are enforced in the compiler, not trusted to the LLM
(kept spine → validity inherited; new ambient beats reserve `(agent, minute)` slots so no agent
is ever bilocated; `hidden` is reserved for the murder). The timeline phase is **best-effort**
like `generate_character_identities`: any failure leaves `timeline=None` and the assembler keeps
the template events/routines — never a regression. `client.py`'s `FAKE_TIMELINE` lets the
default `fake` provider (and `tests/test_generated_timeline.py`) exercise the whole path offline.

### Case data (`backend/app/data/`)

Each `case_00N/` (and generated `gen_*/`) is a self-contained locked bundle: agents,
locations, events/timeline, clue graph, seeded memories, `challenges.json`, `solution.json`.
`case_001` is the hand-authored reference case (*The Storage Room Murder*). `templates/` holds
generation templates. `llm_settings.json` is gitignored.

#### Case invariants every case must satisfy (enforced by `validator.py`)

`validate_case()` is the fairness gate, and **every case — hand-authored or generated — must pass
it with zero errors**. Cases 002–006 once shipped invalid because nothing ran it. Beyond the
clue-graph/timeline checks it has always had, three invariants exist because they were each
violated in shipped content:

1. **`Agent.routine_summary` must never carry case truth.** It is player-visible
   (`projections.project_agent`, served by `GET /api/agents`) and is rendered on the Suspects
   screen *before a single clue is discovered*. Cases 004/005/006 shipped with routines that
   announced the killer's motive ("that night he went to the square after finding his father's
   papers"), stated an alibi was false ("she lied to protect him"), gave away case 006's identity
   twist ("dimly recalls Ruth's maiden name was Bell"), and even carried author notes ("his forged
   alibi will need to be dismantled"). A routine describes what someone does on an *ordinary* day —
   a habit, a preference, an opinion; never a plot point, a secret, or what happened on the night
   of the murder. Guarded by `validator.py` check 14, `tests/test_routine_summary_no_leak.py`, a
   `RoutinePlan` field validator in `llm/schemas.py`, and the timeline prompt in
   `llm/mystery_architect.py`.
2. **Every case needs a third act.** The killer must have at least one `contradiction_locked`
   challenge (the confession) and `solution.epilogues` must be non-empty. Both are engine-supported
   (`challenge.py`, `judge.py:109`) but were never authored, so in five of six cases the killer
   never broke and the reveal screen was blank. The three `templates/*.json` now carry both.
3. **Every red herring needs an `innocence_anchor`.** An anchor should read as information
   *withheld* (out of pride, confidentiality, embarrassment), never as a witness *retracting* a
   factual assertion — an innocent man holding a timed, signed docket does not first tell the
   detective he was alone.

Time-of-day matters: cases do not all happen in the morning (case_004 runs 22:00–23:45). The
timeline prompt derives the part of day from `sim_start_time`; keep clock phrases in dialogue
consistent with the case's actual hours.

#### Challenge rule matching

`challenge._find_rule` picks the **best** matching rule, not the first in file order: rules match
on *overlapping* evidence, so a one-clue `deflect` can otherwise shadow the multi-clue confession.
Ranking is: fully-supplied trigger first, then outcome severity, then overlap size, then file
order. Bringing more/better evidence must never yield a weaker response. See
`tests/test_challenge_rule_specificity.py`.

#### Authoring interview rules (they fail silently)

`interview._match_rule` **skips** a rule it cannot match, with no error and no log:

* an `evidence` rule needs a `topic_clue_id` (or `topic_object_id`) — without one it can *never*
  fire, no matter what the player asks;
* a `location` rule needs a `topic_location_id`;
* a `timeline` rule only matches a request that carries a `time_reference`.

There is **no `requires_clue_ids` field on `AnswerRule`** — gating is done by the *clue's*
`discoverability.required_prior_clue_ids` (`_prereqs_met` locks any rule that reveals a clue whose
prerequisites are undiscovered), and by `min_ask_count` for depth. Fourteen authored rules across
four cases were unreachable this way: valid data, passing every other check, invisible to every
player. Guarded by `tests/test_interview_rule_reachability.py`.

#### Testimony as evidence (`testimony.py`)

One villager's word can be used against another's — the mechanic the title promises. A claim
carries `about_agent_id` (whose whereabouts it settles; defaults to the speaker) and
`asserts_presence` (False = a *denial*: "she was never at that fountain"). `find_conflict` then
settles deterministically whether two statements can both be true:

* same person, same moment, **different places** → bilocation (or self-contradiction, if the same
  speaker said both);
* same person, same place, **opposite polarity** → denial.

It is deliberately conservative, and the tolerances are load-bearing: bilocation needs the two
statements to be within **5 minutes** (at 15, it called Clara being in the cafe at 07:40 and the
fountain at 07:50 a contradiction — that is a *walk*), while a denial spans 20, because a witness
watching a place is speaking about a stretch of time. **A detector that cries wolf is worse than
none, because the player stops believing it** — so testimony that does not conflict is rebuffed
honestly rather than fudged into a hit. `ChallengeRule` may also script reactions via
`evidence_claim_ids`. Guarded by `tests/test_testimony.py`.

When authoring claims: annotate any claim that *places a person* — a witness statement about
someone else is useless to the player unless `about_agent_id` says who it is about.

#### The verdict must not contradict the accusation

A correct accusation floors at score 45 (`judge.py`), and the 20–49 verdict band used to read
"Wrong suspect" — so naming the right killer on thin evidence told the player they were wrong.
`_verdict_band` now takes `killer_correct`.

#### Background NPCs

Ambient, non-suspect characters (`Agent.is_background = true`) wander the map for flavor via
ordinary public `movement`/`arrival`/`departure` events in `events.json`. They're excluded from
Suspects, the Board, accusation, and interview (`main.py`'s `board`/`accuse`/`ask` all gate on
`is_background`). Two rules when authoring or generating their routes:

1. **Never route a background NPC through the murder location, its private back-rooms, or any
   location that stages a scripted clue event during the murder window.** They'd become an
   unaccounted-for witness or a "why didn't they mention it" plot hole — keep their routine
   confined to a safe zone of locations the real mystery events never touch during the relevant
   time window.
2. `generator.py`'s deterministic generator reads `case_001/agents.json` directly as its 8-role
   character pool (`agent_pool = [a for a in base_agents if not a.get("is_background")]`) — any
   background NPC added to that file must stay excluded from that pool, or it'll get shuffled
   into a suspect/victim/killer role in every seeded/deterministic generation.

## Frontend architecture (`frontend/src/`)

React 18 + TypeScript + Vite. `api.ts` is the single API client; `types.ts` mirrors backend
schemas. `views/` are the game phases (Overview, Rewind, MapReplay, Places, Suspects for
interview+challenge, Board, Accuse + AccusationCeremony/Breakdown, Intro, plus
GenerateCaseModal / LlmSettingsModal / PlaytestPanel). `components/` are shared UI; `map/`
handles map projection/assets; `audio.ts` + Howler drive ambient/stinger audio
(`public/audio/`). The frontend only ever sees projected, truth-free data until `/api/reveal`.

### Canonical town map/art contract

The migrated town map is visual-only and must not become case truth. `backend/app/town_map.py`
owns the `town_canonical_v1` contract: a 6144x4608, 192x144-grid overworld assembled from a
3x3 mosaic of 2048x1536 HD tiles under `frontend/public/art/town/tiles_3x3_hd/`. All
hand-authored cases (001–007) are wired to `mode: "canonical_overworld"` via `CASE_MAPS` in
`town_map.py`; `legacy_fallback` (the old original artwork) only applies to a case with no
`CASE_MAPS` entry — so a new case must be registered there (visible locations, crop padding)
and added to the `case_ids` of its `LOCATION_FUNCTION_TAGS`, and should reuse canonical
`loc_*` IDs rather than inventing new ones that have no HD art.

The centre tile B2 has paired all-cases assets. Zoomed-out views use
`town_overworld_B2_all_cases_external_hd.png`; zoomed-in views swap B2 to
`town_overworld_B2_interior_hd.png` via `map.zoom_image_tiles.threshold` (currently `3.2`).
`frontend/src/map/mapAssets.ts` resolves the tile set using the current scale, and both
`VisualMap.tsx` and `MapCrop.tsx` pass their zoom/crop scale so close views reveal the
roofless interior while overview views keep roofs.

Location identity is carried by data, not labels painted into art. `LOCATION_FUNCTION_TAGS` in
`town_map.py` maps existing `loc_*` IDs to `display_name`, `function_tag`, `building_role`,
`case_ids`, optional `parent_location_id`, and `zoom_behavior`. The API includes those tags in
`visual.canonical_locations`; `frontend/src/types.ts` mirrors this additive metadata. Evidence
still follows the existing discovery gate: object visuals may know their semantic anchors, but
only `safe_to_render: true` / `marker_state: "active"` objects may appear.

## Specs & docs

The game is built from a spec pack (spec numbers are referenced throughout, e.g. spec 06 =
interview/challenge, spec 11 = data model, spec 12 = engine contract). `docs/` holds the
presentation spec and the playtest bug-bash checklist.

When authoring or generating a case, follow `docs/17_behavioural_authoring_guide.md` — the
writer's contract for the behavioural layer (calm baselines via `Agent.baseline`, pressure-band
escalations, relief beats, confession beats, portrait states). It is enforced by
`tests/test_behavioural_arcs.py`; Marcus in case_007 is the model suspect arc.
