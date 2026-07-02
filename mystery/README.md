# No One Saw Everything — Murder Mystery Module

A fair-play murder mystery game set in a Smallville-style village, built from the
spec pack in `~/Downloads/smallville_murder_mystery_specs/`. The player arrives
after the murder, rewinds the morning, observes the village, interrogates sims,
collects contradictions, and builds a case on the board.

**Core principle:** the truth is generated and locked before play. Nothing the
player does can change who did it, how, or why — the API never leaks hidden
truth (killer identity, lie flags, hidden events) to the client.

## Status

Implements build-plan phases 0–6 (spec 13) — the full playable loop:
`observe → interview → note → challenge → accuse → judgement`.

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

Not yet built: procedural generation (phase 7), fairness validator as a live
service (phase 8 — the checks exist as tests), free-text LLM interrogation
(phase 9, pluggable provider planned).

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
frontend/src/
  views/          # Overview, Rewind, Places, Suspects (interview + challenge),
                  #   Board, Accuse (accusation form + reveal)
```

The interview engine's request/response contract matches spec 06/12, so the
free-text LLM layer can be swapped in behind `answer_question` without touching
the API or UI.
