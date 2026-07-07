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

### Case data (`backend/app/data/`)

Each `case_00N/` (and generated `gen_*/`) is a self-contained locked bundle: agents,
locations, events/timeline, clue graph, seeded memories, `challenges.json`, `solution.json`.
`case_001` is the hand-authored reference case (*The Storage Room Murder*). `templates/` holds
generation templates. `llm_settings.json` is gitignored.

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

## Specs & docs

The game is built from a spec pack (spec numbers are referenced throughout, e.g. spec 06 =
interview/challenge, spec 11 = data model, spec 12 = engine contract). `docs/` holds the
presentation spec and the playtest bug-bash checklist.
