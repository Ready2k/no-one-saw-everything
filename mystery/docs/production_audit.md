# Production Audit — No One Saw Everything

*Phase 0 gap report. Baseline at audit time: `game` branch @ af12ab3e, backend suite 348 passed / 0 failed.*

Every finding below is something the MVP gets away with today because there is one player,
one process, one machine, and a trusted operator. Ranked by production risk: what happens
when none of those four assumptions hold.

---

## CRITICAL — truth leaks and destructive surfaces

### C1. `GET /api/generated_cases/{case_id}` returns the entire raw case bundle, including the solution
`main.py:1355` returns `fetch_case(case_id)` — a full `CaseData` — with **no projection at
all**. That object contains `solution.json` (killer, motive, method, lie map), `case.killer_id`,
every hidden event's `truth_description`, every seeded memory with its lie flags, and the
interview packs with the killer's scripted deflections. It works for *any* case id, including
the currently active one. One `curl` solves any mystery before the first interview. The core
invariant of the codebase is broken by this endpoint.

- No no-leak test covers it (`test_case_library.py` only asserts a 200).
- The frontend never calls it (`api.ts` defines `generatedCases.get` but no view uses it),
  so it can be projected down to safe metadata or removed outright with no UI cost.

### C2. `DELETE /api/generated_cases/{case_id}` can delete hand-authored content and traverse paths
`case_store.delete_case_from_disk` does `shutil.rmtree(DATA_DIR / case_id)` with **no
`gen_` prefix check and no path sanitisation**. `DELETE /api/generated_cases/case_001`
destroys the shipped reference case. Worse, `case_id` is attacker-supplied path text:
`DATA_DIR / case_id` will happily resolve `..`-style segments outside the data directory.
The read path has the same shape (`load_case_from_disk` builds `DATA_DIR / case_id`
directly). Compare `session._session_path`, which *does* sanitise — the discipline exists
in the codebase but is not applied on the destructive route.

### C3. One global mutable session per case — every player is the same player
`session.py` keys sessions by `case_id` only; `main.py` routes all traffic to
`get_session(ACTIVE_CASE_ID)`. Two browsers investigating concurrently share one
notebook, one pressure map, one accusation. Player B's accusation unlocks
`/api/reveal` and `mode=truth` map replay **for player A before they've accused** —
the reveal gate itself is only sound single-player. This is the stated Phase 1 rebuild.

### C4. `ACTIVE_CASE_ID` is import-time module state
`main.py:50` hardcodes `case_001`; `generate`/`activate` mutate it via `global`. Every
restart silently reverts to case_001 (already bitten in practice — it's in project memory).
Compounding it: `case_store._ACTIVE_START_TIME` is another process-global set on activate,
and `minutes()` consults it for midnight wrapping — so any code path that touches a
*non-active* case (case library summaries, validator, generation while playing case_004's
22:00 window) computes times against the wrong case's clock.

### C5. `GET /api/llm-settings` returns the stored API key in plaintext
`main.py:107` returns `saved.model_dump()` — `SavedLLMSettings` includes `api_key`
(`llm/config.py:18`). Any client can read whatever key the operator saved, and
`data/llm_settings.json` stores it unencrypted. Must be redacted at the boundary
(write-only field) before any non-localhost deployment.

---

## HIGH — unguarded surfaces and concurrency unsafety

### H1. Playtest/dev endpoints are not actually gated
Docs and `/api/config` claim `MYSTERY_PLAYTEST_MODE` unlocks playtest surfaces, but
`/api/session/playtest-summary`, `/api/session/playtest-export`, and `/api/session/log`
have **no gate at all** — the env var only toggles a boolean the frontend reads. The
export is projected (no-leak tested), but it still ships full transcripts, telemetry, and
feedback to anyone who asks. The flag must be enforced server-side; "playtest mode must
be impossible to enable from the client" is currently true only because there's no toggle —
not because the server checks anything.

### H2. LLM settings endpoints are an SSRF/exfiltration surface
`/api/llm-settings/models`, `/test`, and `/probe` accept an arbitrary `base_url` and make
the **server** issue HTTP requests to it, returning response bodies/errors to the client.
Unauthenticated, this is a classic SSRF probe (internal network scanning, metadata
endpoints) plus a way to exfiltrate the saved API key by pointing `base_url` at a
listener and letting the server send `Authorization` headers to it. `PUT /api/llm-settings`
also lets any client swap the whole app to a hostile provider at runtime. These need to be
operator-only (env-gated or authenticated) in production.

### H3. Multi-worker / concurrent-request unsafety
- Sessions live in a process dict; running uvicorn with >1 worker gives each worker its own
  divergent copy, reconciled only by last-writer-wins JSON autosave (`main.py:65` middleware
  saves the *whole* session after every mutating request — also heavy write amplification).
- No file locking on session saves; two processes interleaving `tmp.write_text` +
  `tmp.replace` can lose whole updates (atomic per-file, not per-transaction).
- `GET /api/challenge/suggestions?reveal=true` **mutates state on a GET** (hint_count,
  save) — non-idempotent, cache/prefetch hostile, and had to hand-roll its own save
  because the middleware only watches write verbs.
- `lru_cache(maxsize=8)` on `load_case_from_disk` while 7+ shipped cases + generated cases
  exist: cache thrash, plus `activate_generated_case` mutates `metadata` on the cached
  object — cached truth objects are not actually immutable.
- `_GENERATED_CASES` grows unboundedly per generation; never evicted.

### H4. Free-text intent routing misclassifies relationship questions (observed defect)
Mechanism confirmed in `question_classifier.py`: the relationship rule (line 44) only
fires when the **victim** is mentioned ("him/her/them" or the victim's first name) and its
phrase list lacks common formulations ("get along", "think of", "on good terms"). A
question about a *suspect* ("How did you and Elias get along lately?") matches nothing,
falls through to reference resolution, where "Elias" matches the location "Elias Grant's
House" → rule 9 returns `location` intent → the player gets a real-estate description.
There is no labelled evaluation set; `test_free_text_interview_classifier.py` covers happy
paths only. Phase 2 item, test set + routing fix.

### H5. No authentication, authorization, rate limiting, or request size limits
Every endpoint is anonymous. LLM-backed routes (`free-text`, generation at up to 5
candidates a call) are invokable in a loop by anyone; `POST /api/cases/generate` does
CPU-heavy validation × N candidates and writes case bundles to disk on demand —
a trivial disk/CPU DoS. CORS is pinned to `localhost:5173` (breaks any real domain,
while doing nothing against non-browser clients).

---

## MEDIUM — durability, error handling, operability

### M1. Session saves are unversioned; failure mode is silent data loss
`Session.from_dict` has no schema version. An old/foreign save that fails to parse is
**silently discarded** and the case starts fresh (`_load_session` catches everything).
The Phase 1 requirement is the opposite: load cleanly or fail with a clear message. Partial
loads are worse: `from_dict` trusts field shapes individually, so a save that parses as
JSON but has a drifted field 500s at `get_session` time inside whatever endpoint touched
it first.

### M2. Telemetry dies with the session
The event log lives inside the session object: `reset` deletes it, restart-before-save
loses it, and the only export path is the ungated playtest endpoint. It also grows
unboundedly inside every autosaved JSON file (every save rewrites the whole log). Phase 5
wants an append-only store that survives resets and restarts.

### M3. Error-handling holes that 500 on bad input
- `delete_generated_case` catches `Exception` and returns `500 str(e)` (leaks paths).
- `GET /api/case` uses bare `next(...)` — a malformed case (victim id not in agents)
  is an unhandled `StopIteration`/500 rather than a diagnosable error.
- `pin_event`, `discover_clue` accept any well-formed id but `/api/suspicion` and
  `/api/session/markers` accept **arbitrary agent/element ids** with no existence check —
  junk accumulates in the save forever.
- `interview/{agent_id}` returns `[]` for nonexistent agents (should 404).
- `free-text` for an agent id that is a background NPC is not gated (structured `ask` is).
- Full route-by-route sweep is a Phase 2 item.

### M4. Case-loading inconsistencies
`REQUIRED_CASE_FILES` (case_store.py:27) demands `interviews.json` in `list_all_cases`,
but `load_case_from_disk` treats `challenges.json` as optional and everything else as
required — a case can be listable but unloadable and vice versa. `list_generated_cases`
in `main.py` (~90 lines) duplicates this logic a third way with its own `load_status`
taxonomy. One loader, one validity contract.

### M5. Dev map editor writes into the repo
`/api/dev/map-editor/layout` is env-gated (good) but writes `TOWN_LAYOUT_FILE` inside the
deployed package directory and keeps exactly one `.bak`. In a container this mutates the
image's filesystem. Fine as a dev tool; must be excluded or read-only in production builds
(Phase 5), and the frontend still ships the editor UI to all users.

### M6. Ops surface is bare
- `requirements.txt` is five unpinned `>=` ranges; no lockfile; no reproducible build.
- No Dockerfile/compose; `start.sh` is a dev-only script writing pidfiles and logs into
  the repo.
- Logging is default-format `logging` + whatever uvicorn does; no structured output, no
  request ids, no error reporting hook.
- `MYSTERY_DEV_TELEMETRY_ENABLED` defaults to **true** — dev telemetry on by default in
  what would ship.
- Not every `MYSTERY_*` var is documented in one place (README/CLAUDE.md cover most;
  `MYSTERY_SESSION_PERSIST` and `ENABLE_DEV_MAP_EDITOR` are code-only).

### M7. Validation-message redaction is name-only
`generate` redacts the killer's id/name from validator output, but warnings can carry
other truth phrasing (motive keywords, hidden-event times). Low immediate exposure
(operator-facing modal) but it crosses the API to the client. Safer: never send validator
message bodies to the client; send codes/counts.

### M8. LLM chaos modes are untested
`client.py` has timeouts and the sanitiser rejects leaks/JSON artifacts, and fallback is
design-guaranteed — but there are no tests for: provider hangs (timeout path), garbage
bytes, truth-leaking rewrite under adversarial casing/spacing, or a dead host mid-session.
Phase 3 chaos tests. Also `generate_open_ended_response` runs inline on the request
thread — a slow provider stalls that request for the full timeout with no circuit breaker.

---

## LOW — polish and hygiene

- `inspect()` imports `hashlib` locally though it's imported at module top (`main.py:455`).
- `api.ts` types the whole generated-cases surface as `any`; `types.ts` drift risk.
- `examine_body` body-region heuristics live in the route function (~70 lines in
  `main.py`) — engine logic in the routing layer.
- `next_note_id` collides after a `from_dict` of a save whose `notes_issued` predates
  manual note deletion (ids reused after delete+reload). Cosmetic today.
- Baseline `Agent.baseline` manners exist only for case_007; 001–006 fall back to
  generic tells (stated Phase 3 work).
- No E2E/browser tests at all; CI absent (Phase 4).
- Frontend accessibility partial (aria on composure meter exists; keyboard loop and
  reduced-motion unverified) — Phase 6.

---

## Phase mapping

| Finding | Phase |
|---|---|
| C3, C4, H3 (sessions, active case, concurrency, store) | 1 |
| C1, C2, C5, H1, H2 (leaks & unguarded surfaces) | 1–2 (C1/C2 are cheap, fix with session work; gate H1/H2 in 5 if not sooner) |
| H4, M3, M4 (classifier, error sweep, loader contract) | 2 |
| M7, M8, baselines, third acts | 3 |
| E2E, CI, load sanity | 4 |
| M2, M5, M6, H5 residue (rate limits, docker, logging, telemetry) | 5 |
| Accessibility, first-run, performance | 6 |

**Recommended deviation from strict phase order:** C1 and C2 are a two-line projection and
a prefix check respectively. They are the two worst findings in the report and should land
in the first code commit (Phase 1) rather than waiting for their "natural" phase.
