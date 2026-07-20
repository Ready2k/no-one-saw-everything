# FastAPI backend, single uvicorn worker: the session/rate-limit/case stores
# are in-process, in-memory singletons (see session.py, rate_limit.py) —
# running >1 worker or replica splits that state, so this image is meant to
# run as exactly one container. Scale by giving it more resources, not more
# replicas, unless the store layer is swapped for something shared first.
#
# Build context is this directory (backend/): `docker build -f Dockerfile .`
FROM python:3.12-slim

WORKDIR /app

# Dependencies in their own layer so `docker build` doesn't re-resolve them
# every time application code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Case data, sessions, telemetry, and llm_settings.json all live under
# app/data/ (see case_store.py, session.py, telemetry.py, llm/config.py) —
# mount a volume there (docker-compose.yml does) to persist across container
# recreation, or every restart starts from the shipped case_001..007 only and
# discards every investigation.
VOLUME ["/app/app/data"]

RUN useradd --create-home --uid 1000 mystery && chown -R mystery:mystery /app
USER mystery

EXPOSE 8010

# No --reload (dev-only, watches the filesystem and reloads on change —
# wasted overhead and a footgun in production). MYSTERY_* env vars are read
# at request/call time throughout the app (see docs/deployment.md), so they
# can be set at `docker run`/compose time without rebuilding the image.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
