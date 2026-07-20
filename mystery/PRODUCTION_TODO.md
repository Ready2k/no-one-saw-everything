# Production TODO — deferred defects and improvements

Items found during the production-hardening phases that were out of the active
phase's scope. Each entry says where it lives and why it was deferred.

## Correctness / design debt

- **`GET /api/challenge/suggestions?reveal=true` mutates state on a GET**
  (`hint_count`, its own save call). Should become a POST (`/api/challenge/hints`)
  with the GET left read-only. Deferred: changing the verb breaks the current
  frontend call site; needs a coordinated frontend+backend change.
- **`POST /api/discover_clue` is method-agnostic.** It now enforces the clue
  prerequisite graph (409 on unmet prereqs), but a prereq-free *interview*-method
  clue can still be claimed by guessing its id without ever interviewing. A
  stricter gate (only `inspect`-method clues whose location has been inspected, or
  body-exam clues) is desirable; deferred because several tests use the loose
  behaviour as setup shorthand and the frontend only calls it from legitimate
  hotspot flows.
- **Relationship questions about non-victim villagers** are routed to the
  open-ended LLM path (or its honest fallback). The grounded engine only knows
  relationship-with-the-victim; authoring `relationship_with_<agent>` answer packs
  would make these questions first-class.
- **Validator warnings in shipped cases** (all pass with zero errors):
  - case_002: conclusions `conc_priya_means` (1 supporting clue), `conc_method` (2) — expected 3+.
  - case_004: conclusion `conc_method` (1 supporting clue).
  - (case_003/004/006 empty-rewind suspects were fixed in Phase 3.)
- **`GET /api/case` uses bare `next()`** on victim/discoverer/location lookups —
  a malformed case bundle (not player input) would 500. Low priority: only
  reachable with corrupt case data that the fairness gate would already fail.

## Architecture / scale (single-process assumptions that remain)

- **One uvicorn worker is required.** Sessions live in a process dict with
  per-player locks; the JSON store is last-writer-wins across processes. Running
  multiple workers needs a shared store (SQLite/Redis) — documented in the deploy
  runbook.
- **`load_case_from_disk` is `lru_cache(maxsize=8)`** while 7 shipped + N
  generated cases exist; `_GENERATED_CASES` never evicts. Fine at current scale;
  revisit if generated-case volume grows.
- **`activate_generated_case` mutates `metadata` on the cached CaseData**
  (`activated_at`) — cached "immutable" truth objects are not deep-frozen.

## Content

- **Distinct authored baselines for generated (`gen_*`) cases** — the generator
  reuses the template's baseline manners; per-identity manners would need a
  generation phase.

## Ops (Phase 5 follow-ups)

- **Shipped case data and mutable/generated data share one directory**
  (`app/data/`: `case_001..007`, `templates/`, `sessions/`, `telemetry/`,
  `gen_*` generated cases, and `llm_settings.json` all live side by side).
  The Docker volume therefore has to mount the whole directory to persist
  investigations, which means a rebuilt image with new/updated shipped cases
  does not reach an existing deployment's volume (Docker only seeds an empty
  volume). Splitting shipped content into a read-only path baked into the
  image and mutable/generated content into a separate mounted path would fix
  this cleanly, but touches `case_store.py`'s `DATA_DIR` resolution broadly
  enough that it warranted its own pass rather than folding into ops
  hardening. See `docs/deployment.md`.
- **`docker compose up --build` was not run in this environment** (no Docker
  daemon available in the sandbox this work was done in — CLI present,
  nothing to talk to). The Dockerfiles/compose were validated statically
  (`docker compose config`, path/COPY-source checks, `.dockerignore` added to
  prevent host `node_modules`/`.venv` leaking into the images) but need a
  real build-and-run pass before being trusted for a production cutover.
