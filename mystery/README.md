# No One Saw Everything — Murder Mystery Module

A fair-play murder mystery game set in a Smallville-style village, built from the
spec pack in `~/Downloads/smallville_murder_mystery_specs/`. The player arrives
after the murder, rewinds the morning, observes the village, interrogates sims,
collects contradictions, and builds a case on the board.

**Core principle:** the truth is generated and locked before play. Nothing the
player does can change who did it, how, or why — the API never leaks hidden
truth (killer identity, lie flags, hidden events) to the client.

## Status

Implements build-plan phases 0–7C:
`observe → interview → note → challenge → accuse → judgement` plus `procedural generation` and `LLM dialogue rewrites`.

- **Locked case data model** (spec 11) — Pydantic schemas in `backend/app/models.py`
- **Hand-authored case** — *The Storage Room Murder* (blackmail template, spec 03)
  in `backend/app/data/case_001/`: 8 agents, 11 locations, 25 seeded memories,
  29-event timeline, 18-clue graph with conclusions
- **Rewind viewer** (spec 08) — time-range scrubbing, location/sim filters,
  visibility levels (public / public-partial / private placeholder / hidden),
  event pinning that discovers observation clues
- **Evidence inspection** — location searches with prerequisite-gated finds
- **Notes & case board** (spec 07) — manual/contradiction/theory notes,
  pin-to-suspect, player-owned suspicion levels, claims ledger
- **Structured interview engine** (spec 06, deterministic) — six question types,
  grounded hand-authored answers derived from seeded memories and lie state,
  claim extraction, clue reveals gated on prior discoveries
- **Challenge engine** (spec 06, phase 5, deterministic) — confront a claim with
  discovered contradictory evidence; scripted outcomes (deny / deflect / reframe
  / partial admission / reveal innocent secret / contradiction locked), pressure
  tracking, claim-status updates, auto contradiction notes, gated innocent-secret
  reveals, idempotent duplicate handling. Guardrails reject undiscovered evidence,
  missing/mismatched claims, and the victim.
- **Accusation judge** (phase 6, deterministic) — grades killer / motive / method
  / opportunity by keyword-concept matching against `solution.json`, scores
  evidence quality against the clue graph, flags undiscovered-evidence citations
  and reasoning gaps. The truth reveal (true timeline, key clues found/missed,
  red-herring explanations) is exposed **only after** an accusation.

The challenge and accusation engines share the spec-06/12 contract with the
interview engine, so an LLM resolver can be plugged in behind
`resolve_challenge` / `answer_question` / `judge_accusation` without touching the
API or the frontend.

- **Procedural Generation** (phase 7A, 7B) — LLM-assisted generation of new cases based on templates. Safe, deterministic fallback on generation failure.
- **LLM Surface Dialogue** (phase 7C) — The engine intercepts deterministic dialogue responses and uses an LLM to rewrite them for narrative flavor.

Not yet built: free-text LLM interrogation (phase 9).

## Run it

Backend (FastAPI, port 8010):

```bash
cd mystery/backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8010
```

Frontend (React + Vite, port 5173, proxies `/api` to 8010):

```bash
cd mystery/frontend
npm install
npm run dev
```

Tests (also act as the case fairness validator):

```bash
cd mystery/backend && .venv/bin/python -m pytest tests/ -q
```

## Architecture

```
backend/app/
  models.py       # spec-11 schemas: case, agents, events, clues, memories, notes,
                  #   challenges, solution, accusation
  store.py        # loads and caches the immutable case bundle
  session.py      # mutable player state: discoveries, claims, notes, transcripts,
                  #   pressure, challenges, accusation result
  projections.py  # player-safe views — strips hidden truth at the API boundary
  interview.py    # deterministic grounded Q&A (same contract a future LLM uses)
  challenge.py    # deterministic challenge resolution + player-safe projection
  judge.py        # deterministic accusation scoring + gated truth reveal
  main.py         # FastAPI endpoints
  data/case_001/  # the locked hand-authored case (+ challenges.json, solution.json)
  llm/            # LLM adapter interfaces, config, prompts, and dialogue rewriters
  mystery_architect.py  # LLM generation orchestration and fallback
frontend/src/
  views/          # Overview, Rewind, Places, Suspects (interview + challenge),
                  #   Board, Accuse (accusation form + reveal)
```

### Dialogue Rewrite Architecture (Phase 7C)

For interactions (interviews and challenges), the system maintains a strict separation of truth and flavor:

```
Deterministic Result → Optional LLM Rewrite → Sanitiser → Display Text
```

1. **Deterministic Result**: The engine determines the exact outcome (claims made, clues revealed, pressure delta) and selects a pre-authored fallback response.
2. **Optional Rewrite**: If enabled, the LLM uses the agent's persona and the exact "allowed facts" generated in Step 1 to write a richer, in-character response.
3. **Sanitiser**: The rewritten text is checked for leakage (role labels, hidden facts not in the allowed list, JSON artifacts).
4. **Display Text**: If safe, the UI displays the rewritten text. Internally, the deterministic text is preserved for audits, tests, and debugging.
