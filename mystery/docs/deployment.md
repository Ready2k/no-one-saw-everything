# Deployment runbook

## One-command deploy (Docker Compose)

```bash
cd mystery
docker compose up --build
```

Frontend (nginx, serving the production build and proxying `/api` to the
backend) is at `http://localhost:8080`. The backend container is not
published to the host by default — the frontend container reaches it over
the compose network at `http://backend:8010`.

Investigations, telemetry, generated cases, and `llm_settings.json` all live
under `backend/app/data/` (see `case_store.py`, `session.py`, `telemetry.py`,
`llm/config.py`) and are persisted in the `mystery_data` named volume, so
`docker compose down && docker compose up` keeps every player's progress.
**Caveat:** a named volume is only seeded from the image on its *first* run.
If a later image rebuild ships new or updated case bundles, an existing
deployment's volume keeps its old copy — start a fresh volume (or `docker cp`
the new case directories into the running container) to pick up shipped-
content changes. See `PRODUCTION_TODO.md` for the follow-up (splitting
shipped case storage from generated/mutable storage so this stops being a
manual step).

**Single instance only.** The session store, rate limiters, and case cache
are in-process, in-memory singletons (`session.py`, `rate_limit.py`,
`case_store.py`). Do not run multiple backend replicas or multiple uvicorn
workers pointed at the same deployment — they would each hold a different,
diverging copy of every player's investigation. Scale vertically (more CPU/
memory to the one container) rather than horizontally unless the store layer
is replaced with something shared (Redis/Postgres) first.

## Manual deploy (no Docker)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8010   # no --reload

cd ../frontend
npm ci && npm run build
# Serve frontend/dist/ with any static file server, proxying /api/* to the
# backend (see frontend/nginx.conf for a working example config).
```

## Environment variables

Every variable the backend reads. All are optional; defaults are what you
get by setting nothing. None of these can be set from the frontend or by a
player — they are read from the process environment only, at the points
noted, so config changes need a container/process restart to take effect
unless marked "read live."

### LLM provider

Precedence: settings saved via the in-app LLM Settings modal / `PUT
/api/llm-settings` (persisted to `app/data/llm_settings.json`) override these
env vars. See `llm/config.py`.

| Variable | Default | Meaning |
|---|---|---|
| `MYSTERY_LLM_PROVIDER` | `fake` | `fake` (no network, deterministic templates), `auto` (probe for a reachable local OpenAI-compatible host), or `openai_compatible`. |
| `MYSTERY_LLM_BASE_URL` | unset | Base URL for `openai_compatible`. |
| `MYSTERY_LLM_API_KEY` | unset | API key for `openai_compatible`, sent to that host only. Never returned to the browser (see `_redact_saved_settings` in `main.py`). |
| `MYSTERY_LLM_MODEL` | unset | Model name for `openai_compatible`. |
| `MYSTERY_LLM_TIMEOUT_SECONDS` | `60` | Per-request timeout to the LLM host. The game always falls back to deterministic/authored text on any provider failure — this just bounds how long a player waits before that fallback fires. |
| `MYSTERY_LLM_DIALOGUE_ENABLED` | `false` | Rewrite interview/challenge answers through the LLM for flavour (sanitised; see `llm/dialogue_rewriter.py`). |
| `MYSTERY_LLM_BELIEFS_ENABLED` | `false` | Offline belief-state updates between player actions (spec 15 Phase C). Only effective when dialogue rewriting is also on. |

### Access control / dev surfaces

These gate surfaces that must not be reachable in a real deployment unless
you specifically want them. None has a client-facing toggle.

| Variable | Default | Meaning |
|---|---|---|
| `MYSTERY_PLAYTEST_MODE` | `false` | Unlocks `/api/session/log`, `/api/session/telemetry/durable`, `/api/session/playtest-summary`, `/api/session/playtest-export`. Read fresh on every request (flippable without a restart, in case that's useful for an ops toggle in front of the process — but there is still no way for a client request to set it). |
| `ENABLE_DEV_MAP_EDITOR` | `false` | Unlocks `GET/POST /api/dev/map-editor/layout`, which writes `app/data/town/town_layout.json` inside the container. Leave off in production; it's a content-authoring tool, not a player surface. |

### Session storage

| Variable | Default | Meaning |
|---|---|---|
| `MYSTERY_SESSION_PERSIST` | unset (persistence on) | Set to `0` to disable saving investigations to disk entirely (in-memory only for that process's lifetime). The test suite sets this implicitly (persistence is also auto-disabled whenever `PYTEST_CURRENT_TEST` is set). |

### CORS

| Variable | Default | Meaning |
|---|---|---|
| `MYSTERY_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated list of allowed browser origins. **The default is dev-only** — a deployment whose frontend is not proxied through the same origin as the backend (i.e. not using `frontend/nginx.conf`'s `/api/` proxy) must set this to its real frontend origin(s), or every request will be blocked by the browser's CORS check. |

### Abuse hardening

| Variable | Default | Meaning |
|---|---|---|
| `MYSTERY_MAX_REQUEST_BYTES` | `262144` (256 KiB) | Request body size cap for ordinary routes. |
| `MYSTERY_MAX_DEV_REQUEST_BYTES` | `8388608` (8 MiB) | Higher cap for `/api/dev/*` routes (the map editor's layout payload is a large JSON blob); still requires `ENABLE_DEV_MAP_EDITOR=true` to reach the route at all. |
| `MYSTERY_LLM_RATE_LIMIT_PER_MINUTE` | `20` | Per-player-token limit on LLM-backed routes: `/api/interview/free-text`, `/api/llm-settings/test[/saved]`, `/api/llm-settings/models[/saved]`, `/api/llm-settings/probe`. |
| `MYSTERY_GENERATE_RATE_LIMIT_PER_MINUTE` | `6` | Per-player-token limit on `POST /api/cases/generate` (up to 5 candidates per call, each validated and scored — real CPU/disk work regardless of LLM use). |

### Observability

| Variable | Default | Meaning |
|---|---|---|
| `MYSTERY_LOG_JSON` | `false` | Emit structured (one-line JSON) logs instead of plain text. Each line carries a `request_id` correlating it to the request that produced it (see `logging_config.py`, the `X-Request-Id` response header). |
| `MYSTERY_LOG_LEVEL` | `INFO` | Standard Python logging level name (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `MYSTERY_DEV_TELEMETRY_ENABLED` | `true` | Records gameplay telemetry (clue discoveries, interviews, challenges — see `telemetry.py`) to the session's in-memory log and a durable per-(player, case) file. Purely internal analytics; the endpoints that expose it are already gated by `MYSTERY_PLAYTEST_MODE` above, so disabling this only stops the *collection*, not an exposure. |

## Health check

`GET /api/config` returns 200 with no side effects and no auth requirement —
used as the compose healthcheck. It reports the live `playtest_mode` flag,
current LLM configuration summary, and nothing case-truth-shaped.

## What Docker verification did and did not cover

The Dockerfiles and `docker-compose.yml` were validated statically —
`docker compose config` parses and resolves correctly, every `COPY` source
exists, and `.dockerignore` files were added to both images so a local
`node_modules`/`.venv` on the host machine can't leak into (or clobber) the
container's own install step. **An actual `docker compose up --build` was
not run** — this environment has the `docker` CLI but no running daemon
(Docker Desktop/colima) available. Run it yourself before relying on this in
production.
