# Production readiness — summary

*No One Saw Everything, production-hardening pass. Baseline: `game` branch @ af12ab3e
(348 backend tests, single-player-only, no CI, no Docker). End state: 524 backend
tests, Playwright E2E, GitHub Actions CI, per-player sessions, Docker deploy.*

This document summarises what changed across all six phases, what was deliberately
deferred (see `PRODUCTION_TODO.md` for the full list with reasoning), and how to
actually deploy the result. It assumes you've read `CLAUDE.md`'s description of the
core invariant (truth never leaks before `/api/reveal`) — every phase below was held
to that bar, not just the ones that touch projections directly.

## Phase 0 — Audit

`docs/production_audit.md`. Full gap report, ranked CRITICAL/HIGH/MEDIUM/LOW. The
two worst findings — `GET /api/generated_cases/{id}` returning the entire raw case
bundle (solution, killer, lie flags) to any caller, and `DELETE` accepting any case
id including hand-authored ones and path-traversal attempts — were fixed in Phase 1
rather than waiting for a later phase, per the audit's own recommendation.

## Phase 1 — State & session architecture

The MVP's single global in-memory session (one investigation, shared by every
request) is gone. Sessions are now scoped by an opaque `X-Session-Id` browser
token; the frontend generates and persists one in `localStorage` automatically —
no player-visible change, but two browsers now get two notebooks, two pressure
tracks, two accusations. The reveal gate is verified sound per-player under real
concurrent load (`test_concurrent_sessions.py`).

- Per-player active-case selection, durable across restarts (`ACTIVE_CASE_ID`
  used to be a module import-time constant that silently reverted to `case_001`
  on every restart — a known, previously-memoried bug, now fixed).
- Saves are versioned (`schema_version`). A save from a newer server refuses to
  load with a clear message; a corrupt or unreadable save is quarantined
  (renamed aside, never deleted) and the case starts fresh — never a 500, never
  silent data loss.
- The MVP's flat, single-player save layout migrates automatically into the new
  per-player layout on first use; the first real browser token "adopts" whatever
  was played before tokens existed.
- Fixed both CRITICAL findings from Phase 0 (raw case leak, unsafe delete).

## Phase 2 — Correctness debt

- The reported free-text classifier bug — "How did you and Elias get along
  lately?" answered with a description of Elias's house instead of Elias — is
  fixed at the root cause (a location's name is never inferred from a person's
  bare name) and guarded by a 50-question labelled intent test set
  (`test_question_intent_set.py`) spanning every intent the classifier handles.
- `validate_case()` — the fairness gate — now runs as a test over all seven
  shipped cases, not just case_001. It always passed with zero errors; a few
  warnings (weak-conclusion clue counts, empty-rewind suspects) were also
  cleaned up in Phase 3.
- Swept every route for unhandled input: malformed times, unknown ids,
  background NPCs where they shouldn't be reachable, oversized inputs — all
  4xx with an in-world message, never a 500 (`test_error_handling.py`, a
  parametrized chaos test against every endpoint).

## Phase 3 — Content completeness

- Every living principal in cases 001–006 now has an authored calm-baseline
  manner per `docs/17_behavioural_authoring_guide.md` (case_007 was previously
  the only one; the distinctness test now runs over all seven cases).
- Fixed the "empty rewind" suspects in cases 003/004/006 (three characters who
  appeared in no public events at all) with ambient events that corroborate
  their existing authored alibis.
- New API-level sweep plays every case to accusation on both the win and loss
  path: a win must floor at score 45 with non-empty epilogues and a true
  timeline; a loss must read as a loss and reveal nothing.
- LLM chaos tests against a real HTTP transport (dead host, hanging provider vs.
  timeout, garbage/non-schema response bodies) prove the deterministic fallback
  always delivers the authored line. The sanitiser gained an
  invented-confession guard: ungrounded violence vocabulary ("I killed him") is
  rejected unless the grounded text being rewritten already contains it.

## Phase 4 — Test & CI hardening

- Playwright E2E golden path (`frontend/e2e/golden-path.spec.ts`) against the
  **production build**: rewind → pin → search a scene → interview → observe →
  challenge → board → accuse → reveal, with a no-leak DOM assertion after every
  step and a positive check that the guilt sentence appears only after reveal.
  Caught and fixed a real bug while writing it: the ceremony's Skip/Next
  controls sat under the cinematic vignette overlay in a broken stacking
  context, so the first "Skip Reveal" click of a session never registered.
- `.github/workflows/ci.yml`: backend (pytest — also the case-fairness suite),
  frontend (typecheck + vitest + build), E2E — as three jobs on every push/PR.
- `test_concurrent_sessions.py`: 20 simultaneous X-Session-Id sessions
  interviewing/noting/marking suspicion under real thread contention, plus a
  concurrent-accusation check that the reveal gate stays sealed per player.

## Phase 5 — Ops & security

- **Dev/playtest surfaces are now server-enforced, not just client-hidden.**
  `/api/session/log`, `/api/session/playtest-summary`,
  `/api/session/playtest-export`, and the new
  `/api/session/telemetry/durable` all 403 unless `MYSTERY_PLAYTEST_MODE=true`
  — previously only the frontend panel checked this, so the endpoints were
  reachable by anyone regardless of the flag.
- **The LLM settings API key is no longer returned to the browser.** `GET
  /api/llm-settings` used to hand back the saved provider key in plaintext on
  every load; it now returns `api_key_set` + a last-4 preview, and saving
  without retyping the key keeps the existing one (new `/models/saved` and
  `/test/saved` endpoints let the Settings panel re-verify a saved connection
  without the browser ever holding the real key).
- Basic SSRF defence: every endpoint that makes the server dial a
  client-supplied `base_url` (LLM model discovery, connection test) refuses
  cloud metadata addresses before making the request.
- Abuse hardening: an in-process per-player sliding-window rate limiter on
  LLM-backed routes and case generation; a request body size cap (256KB
  general, 8MB for the already-gated dev map editor); `max_length` constraints
  on free-text fields across the API.
- Telemetry now survives both `reset_session()` and process restarts via a
  separate append-only per-(player, case) log, independent of the in-memory,
  reset-scoped session log that hints/analytics still use.
- Structured JSON logging (`MYSTERY_LOG_JSON=true`) with a request id
  correlating every log line — including exception tracebacks — back to the
  request that produced it, plus an `X-Request-Id` response header. Caught and
  fixed a bug while adding it: the id was cleared from its context variable
  *before* the access-log line that was supposed to carry it.
- CORS origins are now environment-configurable (`MYSTERY_CORS_ORIGINS`)
  instead of hardcoded to `localhost:5173`, which silently broke any non-dev
  deployment.
- Dockerfiles for both services, `docker-compose.yml` for a one-command deploy,
  and `docs/deployment.md` documenting every `MYSTERY_*` environment variable.
  Validated statically (`docker compose config`, every `COPY` source path
  checked, `.dockerignore` added to both images) — **an actual `docker compose
  up --build` was not run**, since no Docker daemon was available in the
  environment this work was done in. Run it before trusting this in
  production; see `PRODUCTION_TODO.md`.

## Phase 6 — UX/product polish

- A universal `prefers-reduced-motion` rule (the WCAG-standard
  near-instant-single-cycle backstop) now covers every animation in the
  stylesheet. ~20 individually authored animations each had their own
  hand-placed override, and several — the notebook page-flip sequence, the
  challenge "VS" beat slams, toasts, the recording-dot blink — had none; that's
  exactly the failure mode a per-selector approach produces as a stylesheet
  grows, and why this is now a single rule instead of another one-off.
- The hidden-object magnifier search (evidence hunting in Places, body exams)
  had **no keyboard path at all** — finding a clue meant dragging a lens with
  the mouse. Each undiscovered clue now also has a real, focusable, generically
  labelled button at the same spot, inert to the mouse (so the existing drag
  interaction is completely unaffected) — verified live end-to-end: Tab reaches
  it, Enter discovers the clue, a real clue card appears.
- Every modal now closes on Escape (previously only the backdrop or an explicit
  Close button worked) and returns focus to its trigger; the accusation
  suspect dropdown gained real `listbox`/`option` ARIA. Both verified live.
- Fixed a real, unrelated bug found while touching that screen: the accusation
  question hardcoded "Who killed Marcus Bell?" regardless of which case was
  actually active.
- Main JS bundle: 519KB → 389KB gzipped (152KB → 116KB), by code-splitting the
  two dev-only routes (the ~5000-line canvas map editor, the ambient-town art
  preview) behind `React.lazy` — verified via build output.
- The 3×3 HD town mosaic (5-6MB *per tile*) was fetched in full for every small
  establishing-shot crop (location transitions, cinematics) even though a crop
  only ever shows 1-2 tiles' worth. Fixed by computing which tiles actually
  intersect the visible crop window; verified against every location in
  case_001's real map data (1-2 tiles fetched, never all 9, everywhere).

## What was deferred (see `PRODUCTION_TODO.md` for full detail + reasoning)

- Native `alert()`/`confirm()` dialogs across ~4 files — needs a shared themed
  dialog component, bigger than the rest of the Phase 6 accessibility work.
- Shipped case data and generated/mutable data share one directory
  (`app/data/`), so the Docker volume has to mount the whole thing — a rebuilt
  image with new shipped cases won't reach an existing deployment automatically.
- `docker compose up --build` was validated statically, not run end-to-end.
- A handful of low-severity items from the Phase 0 audit that were never
  reachable by a player (an unhandled `StopIteration` on corrupt case data that
  the fairness gate would already catch; `lru_cache` sizing on the case store).
- Distinct authored baselines for *generated* (`gen_*`) cases — they currently
  reuse the template's manners.

## Deploy runbook

Full detail, including every environment variable, lives in
`docs/deployment.md`. Short version:

```bash
cd mystery
docker compose up --build
```

Frontend at `http://localhost:8080` (nginx, proxying `/api` to the backend
container). Investigations/telemetry/generated cases persist in the
`mystery_data` named volume. **Run the backend as a single instance** — the
session store, rate limiters, and case cache are in-process singletons by
design (see `PRODUCTION_TODO.md`); multiple replicas or workers would each
hold a diverging copy of every player's investigation.

Manual (no Docker):

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8010   # no --reload

cd ../frontend && npm ci && npm run build
# serve frontend/dist/ with any static server, proxying /api/* to the backend
```

## Verifying this yourself

```bash
cd backend && .venv/bin/python -m pytest tests/ -q     # 524 passed
cd frontend && npm run typecheck && npm test && npm run build
npm run test:e2e                                        # 1 passed (golden path)
```

CI (`.github/workflows/ci.yml`) runs all of the above on every push and PR.
