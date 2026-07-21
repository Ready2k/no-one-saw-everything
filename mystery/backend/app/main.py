"""FastAPI app for the murder mystery investigation API."""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from typing import Optional

from contextvars import ContextVar

from fastapi import FastAPI, HTTPException, Body, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json
import logging
import os

from .logging_config import configure_logging, request_id_var

configure_logging()
logger = logging.getLogger(__name__)

from . import challenge as challenge_engine
from . import interview as interview_engine
from . import judge as judge_engine
from .challenge import ChallengeError
from .models import (
    AccusationRequest,
    AskRequest,
    FreeTextAskRequest,
    ChallengeRequest,
    InspectRequest,
    Note,
    NoteCreate,
    ObservationRead,
    ObserveRequest,
    NoteUpdate,
    SuspicionUpdate,
    GenerateCaseRequest,
    Feedback,
)
from .projections import (
    project_agent,
    project_claim,
    project_clue,
    project_location,
    project_map_agent,
    project_map_location,
    truth_map_events,
    visible_events,
    visible_map_events,
    build_playtest_export,
)
from .rate_limit import RateLimiter
from .session import (
    DEFAULT_PLAYER_ID,
    SESSIONS_DIR,
    SessionLoadError,
    delete_investigation,
    get_active_case,
    get_session,
    has_saved_session,
    list_investigations,
    peek_session,
    reset_session,
    sanitize_player_id,
    save_session,
    set_active_case,
    _persist_enabled,
)
from .case_store import get_case as fetch_case
from .telemetry import log_telemetry_event

# Which case a request is playing is per-player state (X-Session-Id header), stored in
# the player's meta file. This module-level id is only the *default* for players who
# have never chosen a case (and for tokenless clients such as curl and the tests) —
# it is restored from disk at startup so a restart no longer silently reverts to case_001.
_ACTIVE_STATE_FILE = SESSIONS_DIR / "active_state.json"


def _restore_default_active_case() -> str:
    if _persist_enabled():
        try:
            case_id = json.loads(_ACTIVE_STATE_FILE.read_text()).get("active_case_id")
            if case_id:
                fetch_case(case_id)  # must still exist and load
                return case_id
        except Exception:
            logging.getLogger(__name__).warning(
                "Could not restore active case from %s; defaulting to case_001",
                _ACTIVE_STATE_FILE,
            )
    return "case_001"


ACTIVE_CASE_ID = _restore_default_active_case()

from .case_store import set_active_start_time

# The player id for the request being handled right now, set by middleware from the
# X-Session-Id header. A ContextVar so concurrent requests each see their own player.
_current_player: ContextVar[str] = ContextVar("mystery_player", default=DEFAULT_PLAYER_ID)


def current_player_id() -> str:
    return _current_player.get()


def _effective_case_id(player_id: str | None = None) -> str:
    """The case this player is playing: their own durable choice, else the process default."""
    pid = player_id if player_id is not None else current_player_id()
    chosen = get_active_case(pid)
    if chosen:
        try:
            fetch_case(chosen)
            return chosen
        except Exception:
            # Their chosen case has been deleted from disk; fall back rather than 500.
            logging.getLogger(__name__).warning(
                "Player %s's active case %s no longer loads; falling back", pid, chosen
            )
    return ACTIVE_CASE_ID


def _persist_default_active_case(case_id: str) -> None:
    if not _persist_enabled():
        return
    try:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _ACTIVE_STATE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"active_case_id": case_id}))
        tmp.replace(_ACTIVE_STATE_FILE)
    except Exception:
        logging.getLogger(__name__).exception("Could not persist active case")


def _activate_for_current_player(case_id: str) -> None:
    """Make case_id the current player's durable active case."""
    global ACTIVE_CASE_ID
    player_id = current_player_id()
    set_active_case(player_id, case_id)
    if player_id == DEFAULT_PLAYER_ID:
        # Tokenless clients share the process default; keep it durable too.
        ACTIVE_CASE_ID = case_id
        _persist_default_active_case(case_id)


app = FastAPI(title="No One Saw Everything", version="0.1.0")

# Comma-separated list of allowed origins; the dev-server pair remains the
# default so `./start.sh` keeps working unconfigured. A real deployment sets
# MYSTERY_CORS_ORIGINS to its actual frontend origin(s) — the hardcoded
# localhost-only default silently breaks any non-dev deployment otherwise.
_default_cors_origins = "http://localhost:5173,http://127.0.0.1:5173"
_cors_origins = [
    origin.strip()
    for origin in os.getenv("MYSTERY_CORS_ORIGINS", _default_cors_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_and_access_log(request: Request, call_next):
    """Every request gets a correlation id (reusing an inbound one from a
    reverse proxy if present) so its log lines — from any module, at any
    depth, including exception tracebacks — can be tied together, and a
    structured access line replaces relying on uvicorn's default format."""
    req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    token = request_id_var.set(req_id)
    started = time.monotonic()
    try:
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled exception for %s %s", request.method, request.url.path
            )
            raise
        elapsed_ms = int((time.monotonic() - started) * 1000)
        # Logged BEFORE the contextvar reset below — the whole point of
        # request_id_var is that this line (and everything logged deeper in
        # the call, e.g. "Session autosave failed") carries the same id.
        logger.info(
            "%s %s -> %s (%dms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        response.headers["X-Request-Id"] = req_id
        return response
    finally:
        request_id_var.reset(token)


@app.exception_handler(SessionLoadError)
async def session_load_error_handler(request: Request, exc: SessionLoadError):
    # A saved investigation that cannot be used is a 409 with a plain explanation,
    # never a 500: the player can restart the case (POST /api/cases/activate with
    # restart=true) or run a compatible server. Nothing is deleted on this path.
    return JSONResponse(status_code=409, content={"detail": str(exc)})


# ---------------------------------------------------------------------------
# Abuse hardening: request size limits + rate limiting on expensive routes
# ---------------------------------------------------------------------------

# Generous for anything a real player types (notes, free-text questions,
# accusation reasoning) or a case-generation recipe; the one outsized body this
# API legitimately accepts is the dev map editor's layout save, which is
# operator-gated (ENABLE_DEV_MAP_EDITOR) and gets its own higher limit.
_MAX_REQUEST_BYTES = int(os.getenv("MYSTERY_MAX_REQUEST_BYTES", str(256 * 1024)))
_MAX_DEV_REQUEST_BYTES = int(os.getenv("MYSTERY_MAX_DEV_REQUEST_BYTES", str(8 * 1024 * 1024)))


@app.middleware("http")
async def limit_request_body_size(request: Request, call_next):
    limit = (
        _MAX_DEV_REQUEST_BYTES
        if request.url.path.startswith("/api/dev/")
        else _MAX_REQUEST_BYTES
    )
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > limit:
                return JSONResponse(status_code=413, content={"detail": "Request body too large."})
        except ValueError:
            pass
    else:
        # No declared length (e.g. chunked transfer): read and cache the body
        # ourselves so we can enforce the cap; downstream handlers reuse the
        # cached body rather than re-reading the stream.
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > limit:
                return JSONResponse(status_code=413, content={"detail": "Request body too large."})
        request._body = body  # noqa: SLF001 — Starlette's own caching mechanism
    return await call_next(request)


# Per-player sliding-window limits. Single-process, in-memory — consistent
# with the session store's existing single-worker constraint (session.py).
# LLM-backed routes cost real provider latency/money; case generation does
# real CPU + disk work (up to 5 candidates, each validated and scored).
_llm_rate_limiter = RateLimiter(
    max_requests=int(os.getenv("MYSTERY_LLM_RATE_LIMIT_PER_MINUTE", "20")),
    window_seconds=60,
)
_generate_rate_limiter = RateLimiter(
    max_requests=int(os.getenv("MYSTERY_GENERATE_RATE_LIMIT_PER_MINUTE", "6")),
    window_seconds=60,
)


def _enforce_rate_limit(limiter: RateLimiter, key: str, what: str) -> None:
    if not limiter.allow(key):
        retry_after = int(limiter.retry_after_seconds(key)) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Too many {what} requests — wait {retry_after}s and try again.",
            headers={"Retry-After": str(retry_after)},
        )


@app.middleware("http")
async def request_context_and_autosave(request: Request, call_next):
    """Resolve the requesting player, then save their investigation after any write.

    An investigation is hours of work and used to live only in this process — restarting the
    backend threw away every clue, claim, note and transcript. Doing this in middleware rather
    than at each call site means a new mutating endpoint cannot forget to save.
    """
    player_id = sanitize_player_id(request.headers.get("x-session-id"))
    ctx_token = _current_player.set(player_id)
    try:
        # Time-of-day wrapping must follow the case this request is actually playing
        # (case_004 runs 22:00–23:45; case_001 mornings).
        try:
            set_active_start_time(
                fetch_case(_effective_case_id(player_id)).case.sim_start_time
            )
        except Exception:
            logging.getLogger(__name__).exception("Could not resolve case start time")
        response = await call_next(request)
        if request.method in ("POST", "PATCH", "PUT", "DELETE") and response.status_code < 400:
            try:
                # Re-resolve: the request itself may have switched the active case.
                # Only persist a session that is actually loaded — autosave must not
                # resurrect an investigation the request just deleted.
                sess = peek_session(_effective_case_id(player_id), player_id)
                if sess is not None:
                    save_session(sess)
            except Exception:
                logging.getLogger(__name__).exception("Session autosave failed")
        return response
    finally:
        _current_player.reset(ctx_token)


def _playtest_mode_enabled() -> bool:
    # Read fresh on every call (matches the dev-map-editor gate below) rather than
    # a module constant bound once at import: it must be flippable in tests, and a
    # deploy must never be able to "accidentally" carry a stale true across a
    # config reload. There is no client-facing way to set this — it is an
    # operator's environment variable, not a request the frontend can send.
    return os.getenv("MYSTERY_PLAYTEST_MODE", "false").lower() == "true"


def _require_playtest_mode() -> None:
    if not _playtest_mode_enabled():
        raise HTTPException(
            403,
            "Playtest tooling is disabled on this server. Set MYSTERY_PLAYTEST_MODE=true "
            "(operator-only; there is no in-app way to enable it) to use it.",
        )


@app.get("/api/config")
def get_config():
    from .llm.config import get_llm_config

    llm = get_llm_config()
    return {
        "playtest_mode": _playtest_mode_enabled(),
        "llm_dialogue_enabled": llm.dialogue_enabled,
        "llm_generation_available": llm.configured and llm.provider != "fake",
        "llm_model": llm.model if llm.provider != "fake" else None,
        "llm_detected_source": llm.detected_source,
    }


class LLMSettingsUpdate(BaseModel):
    provider: str  # "fake" | "auto" | "openai_compatible"
    base_url: Optional[str] = None
    # Omitted/blank means "keep whatever key is already saved" (see
    # update_llm_settings) — the client is never sent the real key back, so it
    # cannot resend it, and must not be forced to erase it just to change
    # another field like the model name.
    api_key: Optional[str] = None
    model: Optional[str] = None
    dialogue_enabled: bool = False
    beliefs_enabled: bool = False


def _redact_saved_settings(saved) -> Optional[dict]:
    """The saved API key must never cross the API — a GET here used to hand
    back the plaintext secret to any client that asked. Callers only need to
    know a key IS set (to render a masked placeholder) and its last 4 characters
    (so the operator can recognise which key without re-reading the full thing)."""
    if saved is None:
        return None
    data = saved.model_dump()
    key = data.pop("api_key", None)
    data["api_key_set"] = bool(key)
    data["api_key_last4"] = key[-4:] if key and len(key) >= 4 else None
    return data


@app.get("/api/llm-settings")
def get_llm_settings():
    """Returns the saved LLM settings (if any) plus the currently effective config,
    so the in-game Settings panel can show what will actually be used."""
    from .llm.config import get_llm_config, load_saved_settings

    saved = load_saved_settings()
    effective = get_llm_config()
    return {
        "saved": _redact_saved_settings(saved),
        "effective": {
            "provider": effective.provider,
            "base_url": effective.base_url,
            "model": effective.model,
            "configured": effective.configured,
            "fallback_reason": effective.fallback_reason,
            "detected_source": effective.detected_source,
            "dialogue_enabled": effective.dialogue_enabled,
            "beliefs_enabled": effective.beliefs_enabled,
        },
    }


# Cheap, high-value SSRF defence: these endpoints make the SERVER issue an HTTP
# request to a client-supplied host. Nobody's legitimate self-hosted LLM lives
# at a cloud metadata address, so refusing those costs no real functionality
# while closing off the most damaging class of target (credential theft from
# the node's own cloud identity).
_SSRF_BLOCKED_HOSTS = {
    "169.254.169.254",  # AWS/GCP/Azure/OCI instance metadata
    "metadata.google.internal",
    "metadata.goog",
    "fd00:ec2::254",  # AWS IMDS, IPv6
}


def _reject_ssrf_target(base_url: str) -> None:
    from urllib.parse import urlparse

    host = (urlparse(base_url).hostname or "").lower()
    if host in _SSRF_BLOCKED_HOSTS or host.startswith("169.254."):
        raise HTTPException(
            400, "That address isn't a valid LLM endpoint (cloud metadata addresses are blocked)."
        )


@app.put("/api/llm-settings")
def update_llm_settings(payload: LLMSettingsUpdate):
    from .llm.config import SavedLLMSettings, load_saved_settings, save_settings

    if payload.provider not in ("fake", "auto", "openai_compatible"):
        raise HTTPException(status_code=400, detail="Invalid provider")
    if payload.provider == "openai_compatible" and (not payload.base_url or not payload.model):
        raise HTTPException(
            status_code=400,
            detail="base_url and model are required for the openai_compatible provider",
        )
    if payload.base_url:
        _reject_ssrf_target(payload.base_url)

    update = payload.model_dump()
    if not update.get("api_key"):
        # Blank means unchanged, not "clear the key" — the client was never
        # given the real key back, so it has no way to resend it deliberately.
        existing = load_saved_settings()
        update["api_key"] = existing.api_key if existing else None

    save_settings(SavedLLMSettings(**update))

    from .llm import discovery
    discovery.reset_cache()

    return get_llm_settings()


class ModelDiscoveryRequest(BaseModel):
    base_url: str
    api_key: Optional[str] = None


@app.post("/api/llm-settings/models")
def discover_llm_models(payload: ModelDiscoveryRequest):
    """Auto-discovers models available at a user-supplied base_url, for the
    Custom (OpenAI-compatible) provider's Model dropdown."""
    from .llm.discovery import list_models_for_base_url

    _enforce_rate_limit(_llm_rate_limiter, current_player_id(), "LLM settings")
    if not payload.base_url.strip():
        raise HTTPException(status_code=400, detail="base_url is required")
    _reject_ssrf_target(payload.base_url)

    models, error = list_models_for_base_url(payload.base_url.strip(), payload.api_key)
    return {"models": models, "error": error}


@app.post("/api/llm-settings/models/saved")
def discover_llm_models_saved():
    """Same as /models, but against the settings already saved on the server.

    The Settings panel is never given the real api_key back (see
    _redact_saved_settings), so it cannot resend it to re-discover models for
    a connection the operator already saved — this runs the request
    server-side against the stored key instead."""
    from .llm.config import load_saved_settings
    from .llm.discovery import list_models_for_base_url

    _enforce_rate_limit(_llm_rate_limiter, current_player_id(), "LLM settings")
    saved = load_saved_settings()
    if saved is None or not saved.base_url:
        raise HTTPException(status_code=400, detail="No saved endpoint to query.")

    models, error = list_models_for_base_url(saved.base_url, saved.api_key)
    return {"models": models, "error": error}


class LlmTestRequest(BaseModel):
    base_url: str
    api_key: Optional[str] = None
    model: str


def _run_llm_test(base_url: str, api_key: Optional[str], model: str) -> dict:
# SECURITY NOTE: base_url is user-supplied and used to make HTTP requests.
# In a hosted/multi-user deployment, validate against an allowlist to prevent SSRF.
@app.post("/api/llm-settings/test")
def test_llm_settings(payload: LlmTestRequest):
    """Sends a real chat completion request to the given endpoint/model so the
    Settings panel can prove the LLM is actually generating a response, rather
    than just resolving a reachable model list."""
    from .llm.config import normalize_base_url
    from .llm.client import OpenAICompatibleLLMClient

    base_url = normalize_base_url(base_url.strip())
    nonce = uuid.uuid4().hex[:6]
    client = OpenAICompatibleLLMClient(base_url=base_url, api_key=api_key, model=model.strip())

    started = time.monotonic()
    try:
        reply = client.generate_chat(
            messages=[
                {
                    "role": "system",
                    "content": "You are confirming a live connection. Reply in one short sentence.",
                },
                {
                    "role": "user",
                    "content": f"Reply with the word 'pong' followed by this code: {nonce}",
                },
            ],
            schema=None,
            temperature=0.0,
            timeout_seconds=20,
            response_format_json=False,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {"ok": True, "reply": reply, "elapsed_ms": elapsed_ms, "nonce": nonce}


@app.post("/api/llm-settings/test")
def test_llm_settings(payload: LlmTestRequest):
    """Sends a real chat completion request to the given endpoint/model so the
    Settings panel can prove the LLM is actually generating a response, rather
    than just resolving a reachable model list."""
    _enforce_rate_limit(_llm_rate_limiter, current_player_id(), "LLM settings")
    if not payload.base_url.strip() or not payload.model.strip():
        raise HTTPException(status_code=400, detail="base_url and model are required")
    _reject_ssrf_target(payload.base_url)

    return _run_llm_test(payload.base_url, payload.api_key, payload.model)


@app.post("/api/llm-settings/test/saved")
def test_llm_settings_saved():
    """Same as /test, but against the settings already saved on the server —
    see discover_llm_models_saved for why this exists instead of resending
    the (never-returned) real api_key."""
    from .llm.config import load_saved_settings

    _enforce_rate_limit(_llm_rate_limiter, current_player_id(), "LLM settings")
    saved = load_saved_settings()
    if saved is None or not saved.base_url or not saved.model:
        raise HTTPException(status_code=400, detail="No saved endpoint to test.")

    return _run_llm_test(saved.base_url, saved.api_key, saved.model)


@app.post("/api/llm-settings/probe")
def probe_llm_settings():
    """Runs auto-detection now (bypassing the cache) so the Settings panel can
    show whether a local LLM host is currently reachable before the user saves
    provider='auto'."""
    from .llm.discovery import detect_llm

    _enforce_rate_limit(_llm_rate_limiter, current_player_id(), "LLM settings")
    detected = detect_llm(force=True)
    if detected is None:
        return {"found": False}
    return {
        "found": True,
        "host_id": detected.host_id,
        "endpoint": detected.endpoint,
        "model": detected.model,
        "source": detected.source,
    }


_HHMM_RE = re.compile(r"([01]?\d|2[0-3]):[0-5]\d")


def _validate_time_param(value: Optional[str], param_name: str) -> Optional[str]:
    """Times come off the wire and go straight into arithmetic; a malformed one
    must be a polite 400, not a ValueError deep in the projection layer."""
    if value is None:
        return None
    if not _HHMM_RE.fullmatch(value.strip()):
        raise HTTPException(
            400, f"'{value}' isn't a time the village clock understands — use HH:MM."
        )
    return value.strip()


def case_data():
    return fetch_case(_effective_case_id())


def session():
    return get_session(_effective_case_id(), current_player_id())


# ---------------------------------------------------------------------------
# Case overview & world
# ---------------------------------------------------------------------------

@app.get("/api/case")
def get_case():
    case = case_data().case
    victim = next(a for a in case_data().agents if a.agent_id == case.victim_id)
    discoverer = next(a for a in case_data().agents if a.agent_id == case.discovered_by)
    location = next(
        l for l in case_data().locations if l.location_id == case.discovery_location_id
    )
    return {
        "case_id": case.case_id,
        "title": case.title,
        "overview_text": case.overview_text,
        "victim": project_agent(victim),
        "discovery_time": case.discovery_time,
        "discovered_by": project_agent(discoverer),
        "discovery_location": project_location(location),
        "sim_start_time": case.sim_start_time,
        "murder_window": list(case.murder_window),
        "scene_description": case.scene_description,
    }


@app.get("/api/cases")
def get_cases():
    """Every case, annotated with whether an investigation is already under way in it, so the
    library can offer 'Resume' rather than silently restarting."""
    from .case_store import list_all_cases
    from .session import load_session_summary

    active = _effective_case_id()
    player = current_player_id()
    cases = list_all_cases()
    for c in cases:
        c["progress"] = load_session_summary(c["case_id"], player)
        c["is_active"] = c["case_id"] == active
    return cases


@app.get("/api/agents")
def get_agents():
    return [project_agent(a) for a in case_data().agents]


@app.get("/api/locations")
def get_locations():
    case = case_data()
    return [project_location(l, case.case.case_id) for l in case.locations]


# ---------------------------------------------------------------------------
# Rewind / observation
# ---------------------------------------------------------------------------

@app.get("/api/events")
def get_events(
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    location_id: Optional[str] = None,
    agent_id: Optional[str] = None,
):
    time_from = _validate_time_param(time_from, "time_from")
    time_to = _validate_time_param(time_to, "time_to")
    events = visible_events(case_data(), time_from, time_to, location_id, agent_id)
    for e in events:
        e["pinned"] = e["event_id"] in session().pinned_event_ids
    return events


@app.post("/api/events/{event_id}/pin")
def pin_event(event_id: str):
    case = case_data()
    sess = session()
    event = next((e for e in case.events if e.event_id == event_id), None)
    if event is None or event.visibility == "hidden":
        raise HTTPException(404, "No such event")
    sess.pinned_event_ids.add(event_id)

    # Pinning an observed event discovers its observation clues.
    newly = []
    for clue in case.clues:
        if (
            clue.discoverability.method == "observation"
            and event_id in clue.linked_event_ids
            and clue.clue_id not in sess.discovered_clue_ids
        ):
            sess.discovered_clue_ids.add(clue.clue_id)
            log_telemetry_event(sess, "clue_discovered", {"clue_id": clue.clue_id, "source": "observation"})
            newly.append(project_clue(clue))

    # Auto-create an event note so the pin shows up on the board.
    from .projections import project_event

    projected = project_event(event)
    note = Note(
        note_id=sess.next_note_id(),
        note_type="event",
        title=f"{event.time} — {projected['description'][:80]}",
        body=projected["description"],
        linked_event_ids=[event_id],
        linked_clue_ids=[c["clue_id"] for c in newly],
    )
    sess.notes[note.note_id] = note
    return {"pinned": True, "new_clues": newly, "note": note}


# ---------------------------------------------------------------------------
# Map replay (visual layer — projections only, never truth)
# ---------------------------------------------------------------------------

@app.get("/api/map/replay")
def map_replay(
    start: Optional[str] = None,
    end: Optional[str] = None,
    location_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    mode: str = "player",
):
    """Player-safe projected data for the visual map replay.

    mode=player (default) applies the same visibility rules as /api/events.
    mode=truth returns the true timeline and is only available after an
    accusation has been submitted (the reveal gate).
    """
    from .map_layout import MAP_ASSET, MAP_HEIGHT, MAP_IMAGE, MAP_WIDTH
    from .town_map import map_config, map_definition_for_case, map_payload

    start = _validate_time_param(start, "start")
    end = _validate_time_param(end, "end")
    case = case_data()
    sess = session()

    # Migrated cases use the reusable canonical HD map contract; unmigrated
    # cases preserve the legacy fallback art and coordinates.
    if map_config(case.case.case_id):
        map_definition = map_definition_for_case(case.case.case_id)
        map_asset = map_definition["asset"]
        map_image = map_definition["image"]
        map_width = map_definition["width"]
        map_height = map_definition["height"]
    else:
        map_asset = MAP_ASSET
        map_image = MAP_IMAGE
        map_width = MAP_WIDTH
        map_height = MAP_HEIGHT
        map_definition = {
            "definition_id": "legacy_the_ville",
            "asset": map_asset,
            "image": map_image,
            "width": map_width,
            "height": map_height,
            "tile_size": 32,
            "grid": {"cols": 140, "rows": 100},
            "origin": "north_west",
            "base_palette": "legacy",
            "lighting_overlay": "runtime_lightingTint",
        }

    if mode not in ("player", "truth"):
        raise HTTPException(400, "mode must be 'player' or 'truth'")
    if mode == "truth":
        if sess.accusation is None:
            raise HTTPException(403, "The truth is sealed until you make an accusation.")
        events = truth_map_events(case)
    else:
        events = visible_map_events(case, start, end, location_id, agent_id)
        for e in events:
            e["pinned"] = e["event_id"] in sess.pinned_event_ids

    return {
        "case_id": case.case.case_id,
        "mode": mode,
        "map": {
            "asset": map_asset,
            "image": map_image,
            "image_tiles": map_definition.get("image_tiles"),
            "zoom_image_tiles": map_definition.get("zoom_image_tiles"),
            "width": map_width,
            "height": map_height,
            "definition_id": map_definition["definition_id"],
            "tile_size": map_definition["tile_size"],
            "grid": map_definition["grid"],
            "origin": map_definition["origin"],
            "base_palette": map_definition["base_palette"],
            "lighting_overlay": map_definition["lighting_overlay"],
        },
        "visual": map_payload(case, sess.discovered_clue_ids),
        "time_range": {
            "start": case.case.sim_start_time,
            "end": case.case.discovery_time,
        },
        "locations": [project_map_location(l, case.case.case_id) for l in case.locations],
        "agents": [project_map_agent(a) for a in case.agents],
        "events": events,
    }


# ---------------------------------------------------------------------------
# Evidence inspection
# ---------------------------------------------------------------------------

# Case 005's generated location art has deliberate search zones.  These values
# are percentages within the individual illustration, and are presentation-only:
# they never make an undiscovered clue visible until the inspection endpoint has
# authorised it.  Body-specific findings remain in the autopsy flow instead.
CASE_005_ILLUSTRATION_HOTSPOTS: dict[tuple[str, str], tuple[float, float, float]] = {
    ("loc_clara_flat", "clue_mortgage_deed"): (47.0, 45.0, 7.0),
    ("loc_clara_flat", "clue_property_register"): (42.0, 48.0, 7.0),
    ("loc_clara_flat", "clue_clara_called_owen"): (17.0, 65.0, 6.5),
    ("loc_clara_flat", "clue_whitfield_is_nobody"): (45.0, 45.0, 6.5),
    ("loc_clara_flat", "clue_capacity_certificate"): (52.0, 48.0, 6.5),
    ("loc_rear_alley", "clue_clara_committee_note"): (43.0, 61.0, 7.0),
    ("loc_rear_alley", "clue_belt_weapon"): (81.0, 75.0, 7.5),
    ("loc_rear_alley", "clue_staged_fire"): (44.0, 60.0, 6.5),
    ("loc_owen_house", "clue_owen_ash_boots"): (35.0, 67.0, 7.0),
    ("loc_owen_house", "clue_col_carried_the_deed"): (17.0, 48.0, 6.5),
    ("loc_owen_house", "clue_col_cctv_arrival"): (85.0, 68.0, 7.5),
    ("loc_owen_house", "clue_belt_hook_gap"): (19.0, 42.0, 6.5),
    ("loc_owen_house", "clue_yard_books"): (18.0, 48.0, 6.5),
    ("loc_back_lane", "clue_back_lane"): (51.0, 72.0, 8.0),
    ("loc_hobbs_cafe", "clue_clara_second_page"): (56.0, 53.0, 7.0),
}

@app.post("/api/inspect")
def inspect(req: InspectRequest):
    if not req.location_id:
        raise HTTPException(400, "location_id required")
    case = case_data()
    sess = session()
    location = next((l for l in case.locations if l.location_id == req.location_id), None)
    if location is None:
        raise HTTPException(404, "No such location")

    sess.inspected_location_ids.add(req.location_id)
    log_telemetry_event(sess, "inspection_performed", {"location_id": req.location_id})
    hidden_clues, already, locked = [], [], 0
    for clue in case.clues:
        d = clue.discoverability
        if d.method != "inspect" or d.location_id != req.location_id:
            continue
        # Body-examination clues share the body's discovery location for
        # narrative context, but they belong to the dedicated visual autopsy
        # flow rather than the room magnifying-glass search.
        if "examine_body" in (d.reveal_on or []):
            continue
        if clue.clue_id in sess.discovered_clue_ids:
            already.append(project_clue(clue))
            continue
        if any(p not in sess.discovered_clue_ids for p in d.required_prior_clue_ids):
            locked += 1  # something is here, but the player lacks context
            continue
            
        x = d.x
        y = d.y
        radius = d.radius if d.radius is not None else 8.0
        authored_hotspot = CASE_005_ILLUSTRATION_HOTSPOTS.get((req.location_id, clue.clue_id)) \
            if case.case.case_id == "case_005" else None
        if authored_hotspot:
            x, y, radius = authored_hotspot
        if x is None or y is None:
            seed_str = f"{case.case.case_id}:{req.location_id}:{clue.clue_id}"
            digest = hashlib.md5(seed_str.encode("utf-8")).hexdigest()
            x = 10 + ((int(digest[0:4], 16) / 65535.0) * 80)
            y = 10 + ((int(digest[4:8], 16) / 65535.0) * 80)
            
        hidden_clues.append({
            "clue_id": clue.clue_id,
            "x": x,
            "y": y,
            "radius": radius,
            "discovery_text": d.discovery_text,
            "title": clue.title,
        })

    hint = None
    if locked:
        hint = "Something about this place feels off, but you can't put your finger on it yet."
    from .projections import project_map_location
    return {
        "location": project_map_location(location, case.case.case_id),
        "new_clues": [], # deprecated but kept for frontend compatibility if needed
        "hidden_clues": hidden_clues,
        "known_clues": already,
        "hint": hint,
    }


class DiscoverClueRequest(BaseModel):
    clue_id: str

@app.post("/api/discover_clue")
def discover_clue(req: DiscoverClueRequest):
    case = case_data()
    sess = session()
    clue = next((c for c in case.clues if c.clue_id == req.clue_id), None)
    if not clue:
        raise HTTPException(404, "No such clue")
    # The clue graph is the fairness contract: a gated clue cannot be claimed by
    # guessing its id before its prerequisite discoveries have been made.
    unmet = [
        p
        for p in clue.discoverability.required_prior_clue_ids
        if p not in sess.discovered_clue_ids
    ]
    if unmet and clue.clue_id not in sess.discovered_clue_ids:
        raise HTTPException(
            409, "Something about this doesn't add up yet — you're missing the context to see it."
        )
    if clue.clue_id not in sess.discovered_clue_ids:
        sess.discovered_clue_ids.add(clue.clue_id)
        log_telemetry_event(sess, "clue_discovered", {"clue_id": clue.clue_id, "source": "magnifying_glass"})
        # Spec 15 Phase C: fire-and-forget belief updates for the agents this
        # evidence points at; no-op unless the beliefs flag is on.
        from .llm.belief_updater import schedule_belief_updates
        schedule_belief_updates(
            case, sess, clue.linked_agent_ids,
            "The detective has turned up new evidence in the case.",
        )
    return project_clue(clue)


@app.get("/api/examine_body/{agent_id}")
def examine_body_endpoint(agent_id: str):
    case = case_data()
    sess = session()
    
    if agent_id != case.case.victim_id:
        raise HTTPException(400, "Only the victim can be examined this way")
        
    from .interview import is_body_examination_clue
    from .projections import project_clue
    
    hidden_clues = []
    already = []
    
    for clue in case.clues:
        if is_body_examination_clue(clue, case.case.victim_id, case.case.discovery_location_id):
            if clue.clue_id in sess.discovered_clue_ids:
                already.append(project_clue(clue))
            else:
                # Deterministic fallback placement
                d = clue.discoverability
                x = d.x
                y = d.y
                if x is None or y is None:
                    seed_str = f"{case.case.case_id}:{agent_id}:{clue.clue_id}"
                    digest = hashlib.md5(seed_str.encode("utf-8")).hexdigest()

                    title = (clue.title or "").lower()
                    # Only the part of the description that actually states where the
                    # clue was found is trustworthy for placement — later clauses are
                    # backstory/motive and can contain misleading body words (e.g. "say
                    # it to her face", "a note in his hand" meaning handwriting). Cases
                    # consistently phrase the finding as "<lead-in> in/on X's <place>:
                    # <details>", so cut at the first colon, else the first sentence.
                    full_desc = (clue.description or "")
                    if ":" in full_desc:
                        location_phrase = full_desc.split(":", 1)[0]
                    else:
                        location_phrase = full_desc.split(". ", 1)[0]
                    match_text = f"{title} {location_phrase}".lower()

                    def has_term(term: str) -> bool:
                        return re.search(rf"\b{re.escape(term)}\b", match_text) is not None

                    # Default x to center torso width (30 to 70)
                    x = 30 + ((int(digest[0:4], 16) / 65535.0) * 40)

                    if any(has_term(t) for t in ("pocket", "coat", "waist", "jacket")):
                        y = 50 + ((int(digest[4:8], 16) / 65535.0) * 15) # Waist/pocket area
                    elif any(has_term(t) for t in ("hand", "finger")):
                        y = 50 + ((int(digest[4:8], 16) / 65535.0) * 20) # Hand area
                        x = 20 if int(digest[8:12], 16) % 2 == 0 else 80 # Left or right hand
                    elif any(has_term(t) for t in ("head", "face", "neck", "eye", "mouth", "ear", "hair")):
                        y = 15 + ((int(digest[4:8], 16) / 65535.0) * 15) # Head area
                    elif any(has_term(t) for t in ("leg", "foot", "feet", "shoe", "trouser", "ankle", "boot")):
                        y = 75 + ((int(digest[4:8], 16) / 65535.0) * 20) # Legs area
                    elif clue.clue_type == "document":
                        y = 50 + ((int(digest[4:8], 16) / 65535.0) * 20) # Documents usually in pockets (waist)
                    else:
                        # Fallback to general torso/body
                        y = 35 + ((int(digest[4:8], 16) / 65535.0) * 40)

                hidden_clues.append({
                    "clue_id": clue.clue_id,
                    "x": x,
                    "y": y,
                    "radius": d.radius if d.radius is not None else 8.0,
                    "discovery_text": d.discovery_text,
                    "title": clue.title,
                })
                
    cause_of_death = case.case.cause_of_death_observed or "Unknown"
    if not case.case.cause_of_death_observed and case.case.method:
        if case.case.method in ["blunt_force", "stabbing", "poison", "strangulation", "gunshot"]:
            cause_of_death = case.case.method.replace('_', ' ').capitalize()
            
    return {
        "location": {
            "location_id": f"body_{agent_id}",
            "name": f"Victim's Body",
            "description": f"Cause of death appears to be: {cause_of_death}.",
            "map_bounds": { "x": 0, "y": 0, "width": 100, "height": 100 },
            "visibility_type": "public"
        },
        "hidden_clues": hidden_clues,
        "known_clues": already,
        "hint": None
    }


@app.get("/api/clues")
def get_clues():
    case = case_data()
    sess = session()
    return [project_clue(c) for c in case.clues if c.clue_id in sess.discovered_clue_ids]


# ---------------------------------------------------------------------------
# Interviews
# ---------------------------------------------------------------------------

@app.post("/api/interview/ask")
def ask(req: AskRequest):
    case = case_data()
    sess = session()
    if req.agent_id == case.case.victim_id:
        resp = interview_engine.examine_body(case, sess)
        return interview_engine.public_ask_response(resp)
    target_agent = next((a for a in case.agents if a.agent_id == req.agent_id), None)
    if target_agent is None:
        raise HTTPException(404, "No such agent")
    if target_agent.is_background:
        raise HTTPException(400, "This person isn't part of the investigation.")
    if req.question_type == "timeline" and not req.time_reference:
        raise HTTPException(400, "timeline questions need time_reference")
    if req.time_reference:
        req.time_reference = _validate_time_param(req.time_reference, "time_reference")
    if req.question_type == "evidence":
        if req.topic_clue_id and req.topic_clue_id not in sess.discovered_clue_ids:
            raise HTTPException(400, "You can only ask about evidence you have discovered.")
        if not req.topic_clue_id and not req.topic_object_id:
            raise HTTPException(400, "evidence questions need a topic")
    if req.question_type == "location" and not req.topic_location_id:
        raise HTTPException(400, "location questions need topic_location_id")

    resp = interview_engine.answer_question(case, sess, req)
    log_telemetry_event(sess, "interview_answered", {"agent_id": req.agent_id, "question_type": req.question_type})
    for clue in resp.revealed_clues:
        log_telemetry_event(sess, "clue_discovered", {"clue_id": clue.clue_id, "source": "interview"})
    return interview_engine.public_ask_response(resp)


@app.post("/api/interview/free-text")
def free_text_ask(req: FreeTextAskRequest):
    # Every free-text ask runs through the LLM client abstraction (intent
    # classification, and potentially the open-ended responder) even under the
    # default no-network 'fake' provider — rate-limit uniformly rather than
    # branching on which provider happens to be configured.
    _enforce_rate_limit(_llm_rate_limiter, current_player_id(), "free-text question")
    case = case_data()
    sess = session()
    target = next((a for a in case.agents if a.agent_id == req.agent_id), None)
    if target is None:
        raise HTTPException(404, "No such agent")
    if target.is_background:
        raise HTTPException(400, "This person isn't part of the investigation.")
    from app.free_text_api import handle_free_text
    resp = handle_free_text(req, case, sess)
    log_telemetry_event(sess, "free_text_question_asked", {"agent_id": req.agent_id})
    log_telemetry_event(sess, "interview_answered", {"agent_id": req.agent_id, "question_type": "free_text"})
    return resp


@app.get("/api/interview/{agent_id}")
def transcript(agent_id: str):
    case = case_data()
    if not any(a.agent_id == agent_id for a in case.agents):
        raise HTTPException(404, "No such agent")
    sess = session()
    t = sess.transcripts.get(agent_id)
    return t.messages if t else []


@app.post("/api/interview/observe")
def observe(req: ObserveRequest):
    """Spend an action studying the suspect for a sharper behavioural read.

    One read per fresh exchange (a new answer or a new challenge): observing is a
    choice with a cost, not a free lie-detector button. The read itself is built
    only from player-visible signals — see behavioural_tells.observe_read."""
    case = case_data()
    sess = session()
    agent = next((a for a in case.agents if a.agent_id == req.agent_id), None)
    if agent is None:
        raise HTTPException(404, "No such agent")
    if agent.is_background:
        raise HTTPException(400, "This person isn't part of the investigation.")
    if req.agent_id == case.case.victim_id:
        raise HTTPException(400, "The dead give nothing away. Examine the body instead.")

    first_name = agent.full_name.split(" ")[0]
    t = sess.transcripts.get(req.agent_id)
    message_count = len(t.messages) if t else 0
    challenge_count = sum(
        1 for c in sess.challenges.values() if c.target_agent_id == req.agent_id
    )
    if message_count == 0 and challenge_count == 0:
        raise HTTPException(
            409, f"Get {first_name} talking first — you can only read someone who is answering."
        )
    seen_messages, seen_challenges = sess.observed_progress.get(req.agent_id, [0, 0])
    if message_count == seen_messages and challenge_count == seen_challenges:
        raise HTTPException(
            409, f"You have already studied {first_name}. Ask something new, then watch again."
        )

    # Sharpen the tells from whatever the player just witnessed: the latest challenge
    # if one has landed since the last observe, otherwise the latest answer.
    last_tells = []
    if challenge_count > seen_challenges:
        agent_challenges = [
            c for c in sess.challenges.values() if c.target_agent_id == req.agent_id
        ]
        last_tells = agent_challenges[-1].observable_tells
    elif t is not None:
        last_agent_msg = next(
            (m for m in reversed(t.messages) if m.speaker == "agent"), None
        )
        if last_agent_msg is not None:
            last_tells = last_agent_msg.observable_tells

    from .behavioural_tells import observe_read

    text, category, intensity, baseline_state = observe_read(
        agent=agent,
        pressure=sess.pressure_for(req.agent_id),
        last_tells=last_tells,
        seed=f"{case.case.case_id}:{req.agent_id}:{message_count}:{challenge_count}",
        baseline=sess.baselines.get(req.agent_id),
        first_observe=not sess.observations.get(req.agent_id),
    )
    obs = ObservationRead(
        observation_id=sess.next_observation_id(),
        agent_id=req.agent_id,
        text=text,
        category=category,
        intensity=intensity,
        baseline_state=baseline_state,
    )
    sess.observations.setdefault(req.agent_id, []).append(obs)
    sess.observed_progress[req.agent_id] = [message_count, challenge_count]
    log_telemetry_event(sess, "observe_used", {"agent_id": req.agent_id})
    return obs


@app.get("/api/interview/{agent_id}/observations")
def observations(agent_id: str):
    case = case_data()
    if not any(a.agent_id == agent_id for a in case.agents):
        raise HTTPException(404, "No such agent")
    return session().observations.get(agent_id, [])


@app.get("/api/claims")
def claims(agent_id: Optional[str] = None):
    sess = session()
    out = [
        project_claim(c)
        for c in sess.claims.values()
        if agent_id is None or c.speaker_agent_id == agent_id
    ]
    return out


# ---------------------------------------------------------------------------
# Challenges
# ---------------------------------------------------------------------------

@app.get("/api/challenge/suggestions")
def challenge_suggestions(agent_id: Optional[str] = None, reveal: bool = False):
    """Contradictions the player is *holding* — but not, by default, which is which.

    This endpoint used to walk the authored challenge rules and hand the player the finished
    deduction: "this claim is contradicted by this clue → [Challenge]". Noticing that what a
    suspect just said cannot be true given what is in your pocket is the single most satisfying
    act in a detective game, and the UI was performing it on the player's behalf.

    Default (`reveal=False`) returns only a COUNT, so nobody gets stranded — the game will tell
    you that Clara has said two things you can disprove, and leave you to work out which two.
    `reveal=True` is an explicit, counted hint: it returns the pairings and is recorded on the
    session so the player knows they took it.
    """
    case = case_data()
    sess = session()
    clue_title = {c.clue_id: c.title for c in case.clues}
    seen: set[tuple[str, str]] = set()
    out = []
    for rule in case.challenge_rules:
        if rule.challenged_claim_id not in sess.claims:
            continue
        if agent_id and rule.target_agent_id != agent_id:
            continue
        if any(p not in sess.discovered_clue_ids for p in rule.required_prior_clue_ids):
            continue
        usable = [c for c in rule.evidence_clue_ids if c in sess.discovered_clue_ids]
        if not usable:
            continue
        for clue_id in usable:
            key = (rule.challenged_claim_id, clue_id)
            if key in seen:
                continue
            seen.add(key)
            claim = sess.claims[rule.challenged_claim_id]
            out.append(
                {
                    "target_agent_id": rule.target_agent_id,
                    "challenged_claim_id": rule.challenged_claim_id,
                    "claim_text": claim.claim_text,
                    "claim_status": claim.player_known_status,
                    "evidence_clue_id": clue_id,
                    "evidence_title": clue_title.get(clue_id, clue_id),
                }
            )

    # The nudge: how many of this suspect's statements you can disprove, and how many of their
    # statements you have heard at all. Enough to know there is something to find; not enough to
    # find it for you.
    contradicted_claims = {s["challenged_claim_id"] for s in out}
    payload = {
        "contradiction_count": len(contradicted_claims),
        "revealed": reveal,
        "hints_taken": sess.hint_count,
        "suggestions": [],
    }
    if not reveal:
        return payload

    # An explicit hint. Record it — the player should know they took it.
    sess.hint_count += 1
    # This is a GET that mutates state, so the autosave middleware (writes only) will not catch
    # it: persist here or the hint is forgotten on restart and comes back free.
    save_session(sess)
    for s in out:
        key = (s["challenged_claim_id"], s["evidence_clue_id"])
        if key not in sess.logged_suggestion_keys:
            sess.logged_suggestion_keys.add(key)
            log_telemetry_event(
                sess,
                "challenge_hint_revealed",
                {"target_agent_id": s["target_agent_id"], "challenged_claim_id": s["challenged_claim_id"]},
            )
    payload["suggestions"] = out
    payload["hints_taken"] = sess.hint_count
    return payload


@app.post("/api/challenge")
def challenge(req: ChallengeRequest):
    case = case_data()
    sess = session()
    try:
        record = challenge_engine.resolve_challenge(case, sess, req)
        log_telemetry_event(sess, "challenge_executed", {"target_agent_id": req.target_agent_id, "outcome": record.outcome})
        for clue_id in record.revealed_clue_ids:
            log_telemetry_event(sess, "clue_discovered", {"clue_id": clue_id, "source": "challenge"})
    except ChallengeError as e:
        raise HTTPException(e.status, e.detail)
    return challenge_engine.public_challenge(case, sess, record)


@app.get("/api/challenges")
def list_challenges():
    case = case_data()
    sess = session()
    return [
        challenge_engine.public_challenge(case, sess, r) for r in sess.challenges.values()
    ]


# ---------------------------------------------------------------------------
# Notes & case board
# ---------------------------------------------------------------------------

@app.get("/api/notes")
def get_notes():
    return list(session().notes.values())


@app.post("/api/notes")
def create_note(payload: NoteCreate):
    sess = session()
    note = Note(note_id=sess.next_note_id(), **payload.model_dump())
    sess.notes[note.note_id] = note
    log_telemetry_event(sess, "note_created", {"note_id": note.note_id})
    return note


@app.patch("/api/notes/{note_id}")
def update_note(note_id: str, payload: NoteUpdate):
    sess = session()
    note = sess.notes.get(note_id)
    if note is None:
        raise HTTPException(404, "No such note")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    sess.notes[note_id] = note.model_copy(update=updates)
    return sess.notes[note_id]


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: str):
    sess = session()
    if note_id not in sess.notes:
        raise HTTPException(404, "No such note")
    del sess.notes[note_id]
    return {"deleted": True}


@app.post("/api/suspicion")
def set_suspicion(payload: SuspicionUpdate):
    case = case_data()
    agent = next((a for a in case.agents if a.agent_id == payload.agent_id), None)
    if agent is None:
        raise HTTPException(404, "No such agent")
    if agent.is_victim or agent.is_background:
        raise HTTPException(400, "Suspicion belongs on the living members of the village.")
    sess = session()
    sess.suspicion[payload.agent_id] = payload.level
    log_telemetry_event(sess, "marker_updated", {"agent_id": payload.agent_id, "type": "suspicion", "level": payload.level})
    return {"agent_id": payload.agent_id, "level": payload.level}

from .models import MarkerUpdate
@app.post("/api/session/markers")
def update_markers(payload: MarkerUpdate):
    if not payload.element_id or len(payload.element_id) > 120:
        raise HTTPException(400, "That isn't a board element the markers can stick to.")
    sess = session()
    if payload.element_id not in sess.case_board_markers:
        sess.case_board_markers[payload.element_id] = []
    
    markers = sess.case_board_markers[payload.element_id]
    
    if payload.action == "add" and payload.marker not in markers:
        markers.append(payload.marker)
    elif payload.action == "remove" and payload.marker in markers:
        markers.remove(payload.marker)
    elif payload.action == "clear":
        markers.clear()
        
    log_telemetry_event(sess, "marker_updated", {"element_id": payload.element_id, "type": "case_board", "action": payload.action, "marker": payload.marker})
    return {"element_id": payload.element_id, "markers": markers}

@app.get("/api/session/log")
def get_telemetry_log():
    _require_playtest_mode()
    return session().event_log


@app.get("/api/session/telemetry/durable")
def get_durable_telemetry_log():
    """The full telemetry history for this (player, case) across every reset
    and restart — unlike /api/session/log (the current attempt's in-memory
    copy, cleared by reset_session), this reads the append-only log that
    survives both."""
    _require_playtest_mode()
    from .telemetry import read_durable_log

    return read_durable_log(current_player_id(), _effective_case_id())


@app.get("/api/session/hints")
def get_hints():
    from .analyzer import analyze_session
    from .tutorial import get_tutorial_hints
    case = case_data()
    sess = session()
    analyzer_hints = analyze_session(sess, case)
    tutorial_hints = get_tutorial_hints(sess, case)
    return {
        "readiness_hints": analyzer_hints,
        "tutorial_hints": tutorial_hints,
    }

@app.get("/api/session/playtest-summary")
def get_playtest_summary():
    _require_playtest_mode()
    from .llm.config import get_llm_config

    case = case_data()
    sess = session()

    player_action_types = {
        "clue_discovered", "inspection_performed", "interview_answered",
        "free_text_question_asked", "challenge_executed", "note_created",
        "marker_updated", "accusation_submitted", "feedback_submitted"
    }

    player_action_count = sum(1 for e in sess.event_log if e["type"] in player_action_types)
    telemetry_event_count = len(sess.event_log)

    free_text_questions = sum(1 for e in sess.event_log if e["type"] == "interview_answered" and e["data"].get("question_type") == "free_text")
    interviews = sum(1 for e in sess.event_log if e["type"] == "interview_answered") - free_text_questions

    return {
        "case_id": case.case.case_id,
        "case_title": case.case.title,
        "case_type": case.case.case_type,
        "mode": "llm_dialogue" if get_llm_config().dialogue_enabled else "deterministic",
        "telemetry_event_count": telemetry_event_count,
        "player_action_count": player_action_count,
        "discovered_clues": len(sess.discovered_clue_ids),
        "visible_clues": len(case.clues),
        "interviews": interviews,
        "free_text_questions": free_text_questions,
        "challenges_suggested": sum(1 for e in sess.event_log if e["type"] == "challenge_suggested"),
        "challenges_executed": len(sess.challenges),
        "notes_created": len(sess.notes),
        "markers_used": sum(len(v) for v in sess.case_board_markers.values()),
        "accusation_submitted": sess.accusation is not None,
        "score": sess.accusation.score if sess.accusation else None,
        "detective_rating": sess.accusation.detective_rating if sess.accusation else None,
    }

@app.get("/api/session/playtest-export")
def get_playtest_export():
    _require_playtest_mode()
    case = case_data()
    sess = session()
    return build_playtest_export(sess, case, include_reveal=sess.accusation is not None)

@app.post("/api/session/feedback")
def submit_feedback(payload: Feedback):
    sess = session()
    sess.feedback = payload
    log_telemetry_event(sess, "feedback_submitted")
    return {"status": "ok"}



@app.get("/api/board")
def board():
    from .analyzer import analyze_session
    case = case_data()
    sess = session()
    suspects = []
    for agent in case.agents:
        if agent.is_victim or agent.is_background:
            continue
        agent_claims = [
            project_claim(c) for c in sess.claims.values() if c.speaker_agent_id == agent.agent_id
        ]
        linked_clues = [
            project_clue(c)
            for c in case.clues
            if c.clue_id in sess.discovered_clue_ids and agent.agent_id in c.linked_agent_ids
        ]
        pinned_notes = [
            n for n in sess.notes.values() if n.pinned_to_agent_id == agent.agent_id
        ]
        suspects.append(
            {
                "agent": project_agent(agent),
                "suspicion": sess.suspicion.get(agent.agent_id, "unknown"),
                "pressure": round(sess.pressure_for(agent.agent_id), 3),
                "claims": agent_claims,
                "linked_clues": linked_clues,
                "pinned_notes": pinned_notes,
            }
        )
    return {
        "suspects": suspects,
        "contradiction_notes": [
            n for n in sess.notes.values() if n.note_type == "contradiction"
        ],
        "discovered_clue_count": len(sess.discovered_clue_ids),
        "total_discoverable_clues": len(case.clues),
        "readiness_hints": analyze_session(sess, case),
        "case_board_markers": sess.case_board_markers,
    }


# ---------------------------------------------------------------------------
# Accusation & reveal
# ---------------------------------------------------------------------------

@app.post("/api/accuse")
def accuse(req: AccusationRequest):
    case = case_data()
    sess = session()
    if not any(
        a.agent_id == req.accused_agent_id and not a.is_victim and not a.is_background
        for a in case.agents
    ):
        raise HTTPException(400, "You must accuse a living member of the village.")
    result = judge_engine.judge_accusation(case, sess, req)
    log_telemetry_event(sess, "accusation_submitted", {"accused_agent_id": req.accused_agent_id, "score": result.score})
    return result


@app.get("/api/reveal")
def reveal():
    """The truth is only available once an accusation has been submitted."""
    sess = session()
    if sess.accusation is None:
        raise HTTPException(403, "The truth is sealed until you make an accusation.")
    log_telemetry_event(sess, "reveal_viewed")
    return sess.accusation


@app.get("/api/status")
def status():
    sess = session()
    return {
        "discovered_clue_count": len(sess.discovered_clue_ids),
        "claim_count": len(sess.claims),
        "challenge_count": len(sess.challenges),
        "accused": sess.accusation is not None,
    }


@app.post("/api/session/reset")
def reset():
    reset_session(_effective_case_id(), current_player_id())
    return {"reset": True}


# ---------------------------------------------------------------------------
# Investigations (per-player saves)
# ---------------------------------------------------------------------------

@app.get("/api/session/investigations")
def get_investigations():
    """Every investigation the requesting player has, with progress summaries."""
    return {
        "active_case_id": _effective_case_id(),
        "investigations": list_investigations(current_player_id()),
    }


@app.delete("/api/session/investigations/{case_id}")
def delete_player_investigation(case_id: str):
    """Drop the requesting player's investigation of one case (the case itself stays)."""
    if not delete_investigation(case_id, current_player_id()):
        raise HTTPException(404, "You have no investigation of that case.")
    return {"deleted": True}


@app.post("/api/cases/generate")
def generate(req: GenerateCaseRequest):
    from .generator import generate_case, TEMPLATES_DIR
    from .validator import validate_case
    from .case_store import register_case

    # Up to 5 candidates, each generated, validated, and quality-scored — real
    # CPU and disk work regardless of whether an LLM is configured.
    _enforce_rate_limit(_generate_rate_limiter, current_player_id(), "case generation")

    # case_type names a template file and ends up inside the generated case id
    # (a future path component) — it must be a known template, nothing else.
    known_types = {p.stem for p in TEMPLATES_DIR.glob("*.json")}
    if req.case_type not in known_types:
        raise HTTPException(
            400,
            f"Unknown case type '{req.case_type[:40]}'. Available: {', '.join(sorted(known_types))}.",
        )

    has_creative = (
        (req.custom_theme and req.custom_theme.strip()) or 
        (req.tone and req.tone != "standard" and req.tone is not None) or 
        (req.llm_notes and req.llm_notes.strip())
    )
    if req.mode == "deterministic" and has_creative:
        raise HTTPException(
            status_code=400, 
            detail="Creative options (custom theme, non-standard tone, or LLM notes) require LLM-Assisted mode."
        )

    # Generate candidates (Best-of-N logic)
    candidate_count = req.candidate_count
    candidate_count = max(1, min(5, candidate_count))
    
    candidates = []
    candidate_scores = []
    
    for i in range(candidate_count):
        # Vary the seed deterministically
        cand_seed = req.seed + i
        cand_case, fallback_used, fallback_reason, repair_attempts = generate_case(
            req.case_type, req.difficulty, cand_seed, req.mode, req.fallback_allowed,
            num_suspects=req.num_suspects, num_locations=req.num_locations,
            custom_theme=req.custom_theme, tone=req.tone, llm_notes=req.llm_notes
        )
        
        val_result = validate_case(cand_case)
        is_valid = val_result["valid"]
        
        from .quality import score_case_quality
        report = score_case_quality(cand_case)
        
        candidates.append({
            "case": cand_case,
            "is_valid": is_valid,
            "report": report,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "repair_attempts": repair_attempts,
            "seed": cand_seed
        })
        
        candidate_scores.append({
            "seed": cand_seed,
            "overall_score": report.overall_score,
            "is_valid": is_valid
        })

    # Pick the best valid candidate
    valid_candidates = [c for c in candidates if c["is_valid"]]
    if valid_candidates:
        best_candidate = max(valid_candidates, key=lambda c: c["report"].overall_score)
    else:
        best_candidate = candidates[0]
        
    new_case = best_candidate["case"]
    fallback_used = best_candidate["fallback_used"]
    fallback_reason = best_candidate["fallback_reason"]
    repair_attempts = best_candidate["repair_attempts"]
    selected_seed = best_candidate["seed"]
    report = best_candidate["report"]
    
    # Store candidate info in selected case metadata
    if new_case.metadata:
        new_case.metadata["quality_report"] = report.model_dump()
        new_case.metadata["candidate_scores"] = candidate_scores
        new_case.metadata["selected_seed"] = selected_seed
        new_case.metadata["best_of_n_used"] = (candidate_count > 1)

    # Re-validate selected case to confirm final validity check
    val_result = validate_case(new_case)
    if val_result["valid"]:
        from .case_store import save_case_to_disk
        register_case(new_case)
        save_case_to_disk(new_case)

    # Activate session if requested and valid
    active_session_id = None
    if req.activate and val_result["valid"]:
        new_case_id = new_case.case.case_id
        _activate_for_current_player(new_case_id)
        set_active_start_time(new_case.case.sim_start_time)
        # A fresh activation always means a fresh investigation — otherwise
        # re-generating the same (type, seed) resurrects a stale session.
        reset_session(new_case_id, current_player_id())
        active_session_id = new_case_id

    # Validation messages are developer-oriented and can reference the hidden
    # killer; redact identity before they cross the API.
    killer_id = new_case.case.killer_id
    killer_name = next(
        (a.full_name for a in new_case.agents if a.agent_id == killer_id), killer_id
    )

    def _redact(msgs: list[str]) -> list[str]:
        return [
            m.replace(killer_id, "[the killer]").replace(killer_name, "[the killer]")
            for m in msgs
        ]

    return {
        "case_id": new_case.case.case_id,
        "case_type": new_case.case.case_type,
        "title": new_case.case.title,
        "mode": req.mode,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "repair_attempts": repair_attempts,
        "validation": {
            "valid": val_result["valid"],
            "score": val_result["score"],
            "warnings": _redact(val_result["warnings"]),
            "errors": _redact(val_result["errors"]),
        },
        "active_session_id": active_session_id,
        "generation_metadata": new_case.metadata
    }


class ActivateCaseRequest(BaseModel):
    case_id: str
    # Default: pick the investigation back up where it was left. Pass restart=True to bin it and
    # start the case again from nothing.
    restart: bool = False


@app.post("/api/cases/activate")
def activate_case(req: ActivateCaseRequest):
    from .case_store import _GENERATED_CASES, load_case_from_disk

    # Validate case exists in store
    if req.case_id not in _GENERATED_CASES:
        try:
            load_case_from_disk(req.case_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Case not found")

    _activate_for_current_player(req.case_id)
    set_active_start_time(fetch_case(req.case_id).case.sim_start_time)

    # Opening a case RESUMES it. This used to call reset_session() unconditionally, so switching
    # cases — or coming back to one tomorrow — silently destroyed the investigation, which is why
    # the case library had to warn "your current progress will be lost". Starting over is now an
    # explicit choice.
    if req.restart:
        sess = reset_session(req.case_id, current_player_id())
    else:
        sess = get_session(req.case_id, current_player_id())

    response = {
        "active_session_id": req.case_id,
        "resumed": bool(sess.discovered_clue_ids or sess.claims or sess.notes),
        "discovered_clue_count": len(sess.discovered_clue_ids),
        "accused": sess.accusation is not None,
    }
    if sess.recovered_from_corrupt_save:
        # Say it once, at the moment they open the case — not silently.
        response["recovered_from_corrupt_save"] = True
        response["save_notice"] = (
            "Your previous save of this case could not be read and has been set aside; "
            "the investigation has started fresh."
        )
        sess.recovered_from_corrupt_save = False
    return response


def _generated_case_entry(p) -> Optional[dict]:
    """Player-safe library entry for one generated-case directory, or None.

    This is the ONLY shape generated-case endpoints may return: title + recipe
    metadata. The full bundle contains the solution and must never cross the API.
    """
    from .case_store import normalize_case_metadata

    if not (p.is_dir() and p.name != "templates"):
        return None
    if not (p.name.startswith("gen_") or (p / "metadata.json").exists()):
        return None

    load_status = "ok"
    metadata = normalize_case_metadata(None)

    # 1. Try loading metadata
    metadata_path = p / "metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path) as f:
                raw_m = json.load(f)
            metadata = normalize_case_metadata(raw_m)
        except Exception:
            load_status = "corrupted_metadata"
    else:
        load_status = "missing_metadata"

    # 2. Try loading case.json
    title = "Corrupted Case"
    case_type_val = "unknown"
    difficulty_val = "standard"
    case_path = p / "case.json"
    if case_path.exists():
        try:
            with open(case_path) as f:
                case_info = json.load(f)
            title = case_info.get("title", "Untitled Case")
            case_type_val = case_info.get("case_type", "unknown")
            difficulty_val = case_info.get("difficulty", "standard")
        except Exception:
            load_status = "missing_case_data"
    else:
        load_status = "missing_case_data"

    # Verify other vital files exist to confirm ok status
    for vital in ["clues.json", "agents.json", "locations.json", "solution.json"]:
        if not (p / vital).exists():
            load_status = "missing_case_data"
            break

    quality_report = metadata.get("quality_report", {})
    q_score = quality_report.get("overall_score") if quality_report else None
    candidate_scores = metadata.get("candidate_scores", [])
    candidate_count = len(candidate_scores) if candidate_scores else 1

    return {
        "case_id": p.name,
        "title": title,
        "case_type": case_type_val,
        "difficulty": difficulty_val,
        "mode": metadata.get("mode", "deterministic"),
        "seed": metadata.get("seed", 12345),
        "selected_seed": metadata.get("selected_seed"),
        "best_of_n_used": metadata.get("best_of_n_used", False),
        "candidate_count": candidate_count,
        "num_suspects": metadata.get("num_suspects"),
        "num_locations": metadata.get("num_locations"),
        "theme_preset": metadata.get("theme_preset"),
        "custom_theme": metadata.get("custom_theme"),
        "tone": metadata.get("tone", "standard"),
        "quality_score": q_score,
        "quality_report": quality_report,
        "fallback_used": metadata.get("fallback_used", False),
        "repair_attempts": metadata.get("repair_attempts", 0),
        "compaction_applied": metadata.get("compaction_applied", False),
        "created_at": metadata.get("created_at"),
        "activated_at": metadata.get("activated_at"),
        "load_status": load_status,
    }


@app.get("/api/generated_cases")
def list_generated_cases(
    sort_by: Optional[str] = None, # "quality_score", "created_at"
    tone: Optional[str] = None,
    case_type: Optional[str] = None,
    best_of_n: Optional[bool] = None,
    fallback_used: Optional[bool] = None
):
    from .case_store import DATA_DIR

    entries = []
    if not DATA_DIR.exists():
        return entries

    for p in DATA_DIR.iterdir():
        entry = _generated_case_entry(p)
        if entry is not None:
            entries.append(entry)

    # Filtering
    if tone:
        entries = [e for e in entries if e["tone"] == tone]
    if case_type:
        entries = [e for e in entries if e["case_type"] == case_type]
    if best_of_n is not None:
        entries = [e for e in entries if e["best_of_n_used"] == best_of_n]
    if fallback_used is not None:
        entries = [e for e in entries if e["fallback_used"] == fallback_used]

    # Sorting
    if sort_by == "quality_score":
        entries.sort(key=lambda e: e["quality_score"] or 0.0, reverse=True)
    elif sort_by == "created_at":
        entries.sort(key=lambda e: e["created_at"] or "", reverse=True)
    else:
        entries.sort(key=lambda e: e["created_at"] or "", reverse=True)

    return entries


@app.get("/api/generated_cases/{case_id}")
def get_generated_case(case_id: str):
    """Library metadata for one generated case.

    This used to return the entire raw CaseData — solution, killer, lie flags and
    all — which broke the game's core invariant for any client that asked. Only
    the player-safe library entry may cross the API; the case content itself is
    served through the projected gameplay endpoints once the case is activated.
    """
    from .case_store import DATA_DIR, is_safe_case_id

    if not is_safe_case_id(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    entry = _generated_case_entry(DATA_DIR / case_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if entry["load_status"] == "missing_case_data":
        raise HTTPException(status_code=400, detail="Case is corrupted: missing_case_data")
    # Nested "case" block kept for callers that read case-shaped metadata.
    return {
        "case": {
            "case_id": entry["case_id"],
            "title": entry["title"],
            "case_type": entry["case_type"],
            "difficulty": entry["difficulty"],
        },
        **entry,
    }


@app.post("/api/generated_cases/{case_id}/activate")
def activate_generated_case(case_id: str):
    from .case_store import save_case_to_disk, CaseLoadError
    from datetime import datetime

    try:
        case_data = fetch_case(case_id)
        if case_data.metadata and case_data.metadata.get("load_status") in ["corrupted_metadata", "missing_case_data"]:
            raise HTTPException(status_code=400, detail="Cannot activate a corrupted case")
    except CaseLoadError as cle:
        if cle.load_status == "missing_case_data":
            raise HTTPException(status_code=404, detail="Case not found")
        raise HTTPException(status_code=400, detail=f"Cannot activate case: {cle.load_status}")
    except Exception:
        raise HTTPException(status_code=404, detail="Case not found")
        
    _activate_for_current_player(case_id)
    set_active_start_time(case_data.case.sim_start_time)
    reset_session(case_id, current_player_id())

    if case_data.metadata:
        case_data.metadata["activated_at"] = datetime.now().isoformat() + "Z"
        save_case_to_disk(case_data)

    return {"status": "success", "active_session_id": case_id}


@app.post("/api/generated_cases/{case_id}/regenerate")
def regenerate_generated_case(case_id: str):
    from datetime import datetime
    from .case_store import CaseLoadError
    
    try:
        case_data = fetch_case(case_id)
    except CaseLoadError as cle:
        if cle.load_status == "missing_case_data":
            raise HTTPException(status_code=404, detail="Case not found")
        raise HTTPException(status_code=400, detail=f"Cannot regenerate from corrupted case: {cle.load_status}")
    except Exception:
        raise HTTPException(status_code=404, detail="Case not found")
        
    metadata = case_data.metadata or {}
    if metadata.get("load_status") == "missing_metadata" or not metadata.get("mode"):
        raise HTTPException(status_code=400, detail="Recipe metadata is missing or invalid")
        
    # Reconstruct the recipe from metadata
    recipe_req = GenerateCaseRequest(
        case_type=case_data.case.case_type,
        difficulty=metadata.get("difficulty", "standard"),
        seed=int(datetime.now().timestamp()) % 100000, # New seed
        activate=False,
        mode=metadata.get("mode", "deterministic"),
        fallback_allowed=metadata.get("fallback_allowed", True),
        num_suspects=metadata.get("num_suspects"),
        num_locations=metadata.get("num_locations"),
        theme_preset=metadata.get("theme_preset"),
        custom_theme=metadata.get("custom_theme"),
        tone=metadata.get("tone"),
        llm_notes=metadata.get("llm_notes"),
        candidate_count=metadata.get("candidate_count", 1)
    )
    
    return generate(recipe_req)


@app.delete("/api/generated_cases/{case_id}")
def delete_generated_case(case_id: str):
    from .case_store import delete_case_from_disk, CaseDeleteError
    try:
        delete_case_from_disk(case_id)
    except CaseDeleteError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError:
        logging.getLogger(__name__).exception("Could not delete case %s", case_id)
        raise HTTPException(status_code=500, detail="Could not delete the case from disk.")
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Developer Map Editor Endpoints (Dev-only)
# ---------------------------------------------------------------------------

def _layout_file_version(path) -> str:
    """Hash of the layout file's current on-disk bytes, used as an optimistic
    concurrency token: a save proceeds only if the client's copy was loaded
    from this exact on-disk state, so two editors saving around the same time
    can't silently clobber each other. Empty file == no file, so a fresh
    editor session (nothing to conflict with) still gets a stable token."""

    if not path.exists():
        return "empty"
    return hashlib.sha256(path.read_bytes()).hexdigest()


@app.get("/api/dev/map-editor/layout")
def get_dev_map_layout():
    import json
    enable_editor = os.getenv("ENABLE_DEV_MAP_EDITOR", "false").lower() == "true"
    if not enable_editor:
        raise HTTPException(status_code=403, detail="Developer Map Editor is disabled. Set ENABLE_DEV_MAP_EDITOR=true to enable it.")

    from .town_map import TOWN_LAYOUT_FILE, _BOUNDS_TILES, list_hd_tile_variants
    from .place_library import load_building_library, location_search_illustration
    from .case_store import list_all_cases, get_case

    layout_version = _layout_file_version(TOWN_LAYOUT_FILE)
    layout_data = {}
    if TOWN_LAYOUT_FILE.exists():
        try:
            layout_data = json.loads(TOWN_LAYOUT_FILE.read_text())
        except Exception:
            layout_data = {}
            
    if not layout_data:
        layout_data = {
            "version": "town_layout_editor_v2",
            "grid": {"cols": 64, "rows": 48, "tile_size": 32},
            "canonical_locations": {},
            "case_overrides": {},
            "tile_layers": {},
            "prop_instances": {},
            "building_instances": [],
            "lights": {},
            "ambient_sprites": {}
        }
        
    cases_details = []
    for c in list_all_cases():
        case_id = c["case_id"]
        try:
            case_data = get_case(case_id)
            locations = []
            for l in case_data.locations:
                locations.append({
                    "location_id": l.location_id,
                    "name": l.name,
                    "description": l.description,
                    "search_illustration": location_search_illustration(l.location_id, case_id),
                    "legacy_bounds": l.map_bounds.model_dump() if hasattr(l.map_bounds, "model_dump") else (l.map_bounds if l.map_bounds else None),
                    "legacy_position": l.map_position.model_dump() if hasattr(l.map_position, "model_dump") else (l.map_position if l.map_position else None),
                    "visual_layer": l.visual_layer
                })
            objects = []
            for o in case_data.objects:
                objects.append({
                    "object_id": o.object_id,
                    "name": o.name,
                    "description": o.description,
                    "normal_location_id": o.normal_location_id,
                    "final_location_id": o.final_location_id,
                })
            clues = []
            for clue in case_data.clues:
                d = clue.discoverability
                clues.append({
                    "clue_id": clue.clue_id,
                    "title": clue.title,
                    "clue_type": clue.clue_type,
                    "strength": clue.strength,
                    "method": d.method,
                    "location_id": d.location_id,
                    "object_id": d.object_id,
                    "reveal_on": d.reveal_on,
                    "x": d.x,
                    "y": d.y,
                    "radius": d.radius if d.radius is not None else 8.0,
                })
            cases_details.append({
                "case_id": case_id,
                "title": case_data.case.title,
                "locations": locations,
                "objects": objects,
                "clues": clues
            })
        except Exception:
            pass

    return {
        "layout": layout_data,
        "layout_version": layout_version,
        "cases": cases_details,
        "canonical_recommended_locations": {
            loc_id: {
                "bounds": {"x": b[0], "y": b[1], "w": b[2], "h": b[3]},
                "mode": "interior" if loc_id in {
                    "loc_cafe_kitchen", "loc_cafe_storage", "loc_bookshop_back",
                    "loc_clinic_dispensary", "loc_marcus_study", "loc_clara_flat",
                    "loc_ben_flat", "loc_priya_flat", "loc_nadia_flat"
                } else "exterior"
            }
            for loc_id, b in _BOUNDS_TILES.items()
        },
        "building_library": load_building_library(),
        "tile_art_variants": list_hd_tile_variants()
    }


@app.post("/api/dev/map-editor/layout")
def save_dev_map_layout(payload: dict = Body(...), x_base_layout_version: str | None = Header(default=None)):
    import json
    enable_editor = os.getenv("ENABLE_DEV_MAP_EDITOR", "false").lower() == "true"
    if not enable_editor:
        raise HTTPException(status_code=403, detail="Developer Map Editor is disabled. Set ENABLE_DEV_MAP_EDITOR=true to enable it.")

    from .town_map import TOWN_LAYOUT_FILE, validate_town_layout_payload

    errors = validate_town_layout_payload(payload)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    # Optimistic concurrency: reject a save whose base version no longer
    # matches what's on disk, rather than silently overwriting another
    # editor session's more recent save (two open tabs, or a stray
    # automated session, would otherwise clobber each other's work with no
    # way to recover the loser's edits — only one backup slot is kept).
    current_version = _layout_file_version(TOWN_LAYOUT_FILE)
    if x_base_layout_version is not None and x_base_layout_version != current_version:
        raise HTTPException(
            status_code=409,
            detail="The layout changed on disk since you loaded it (likely saved from another tab or session). "
            "Reload the editor to see the latest version before saving again, or your changes will overwrite theirs.",
        )

    try:
        temp_file = TOWN_LAYOUT_FILE.with_suffix(".json.tmp")
        backup_file = TOWN_LAYOUT_FILE.with_suffix(".json.bak")

        TOWN_LAYOUT_FILE.parent.mkdir(parents=True, exist_ok=True)

        temp_file.write_text(json.dumps(payload, indent=2))

        if TOWN_LAYOUT_FILE.exists():
            if backup_file.exists():
                backup_file.unlink()
            TOWN_LAYOUT_FILE.rename(backup_file)

        temp_file.rename(TOWN_LAYOUT_FILE)
        return {"status": "success", "layout_version": _layout_file_version(TOWN_LAYOUT_FILE)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to persist layout: {e}")


@app.post("/api/dev/map-editor/clue-location")
def save_dev_map_clue_location(payload: dict = Body(...)):
    import json
    enable_editor = os.getenv("ENABLE_DEV_MAP_EDITOR", "false").lower() == "true"
    if not enable_editor:
        raise HTTPException(status_code=403, detail="Developer Map Editor is disabled. Set ENABLE_DEV_MAP_EDITOR=true to enable it.")

    from .case_store import DATA_DIR, load_case_from_disk

    case_id = payload.get("case_id")
    clue_id = payload.get("clue_id")
    x = payload.get("x")
    y = payload.get("y")
    radius = payload.get("radius", 8.0)
    if not case_id or not clue_id:
        raise HTTPException(status_code=400, detail="case_id and clue_id are required")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        raise HTTPException(status_code=400, detail="x and y must be numbers")
    if not 0 <= float(x) <= 100 or not 0 <= float(y) <= 100:
        raise HTTPException(status_code=400, detail="x and y must be percentages from 0 to 100")
    if not isinstance(radius, (int, float)) or float(radius) <= 0:
        raise HTTPException(status_code=400, detail="radius must be a positive number")

    case_dir = DATA_DIR / str(case_id)
    clues_file = case_dir / "clues.json"
    if not clues_file.exists():
        raise HTTPException(status_code=404, detail=f"No clues.json for case {case_id}")

    try:
        data = json.loads(clues_file.read_text())
        target = None
        for clue in data.get("clues", []):
            if clue.get("clue_id") == clue_id:
                target = clue
                break
        if target is None:
            raise HTTPException(status_code=404, detail=f"No clue {clue_id} in {case_id}")
        discoverability = target.setdefault("discoverability", {})
        if discoverability.get("method") != "inspect":
            raise HTTPException(status_code=400, detail="Only inspect clues have map-search locations")
        discoverability["x"] = round(float(x), 3)
        discoverability["y"] = round(float(y), 3)
        discoverability["radius"] = round(float(radius), 3)

        temp_file = clues_file.with_suffix(".json.tmp")
        backup_file = clues_file.with_suffix(".json.bak")
        temp_file.write_text(json.dumps(data, indent=2))
        if clues_file.exists():
            if backup_file.exists():
                backup_file.unlink()
            clues_file.rename(backup_file)
        temp_file.rename(clues_file)
        load_case_from_disk.cache_clear()
        return {
            "status": "success",
            "case_id": case_id,
            "clue_id": clue_id,
            "x": discoverability["x"],
            "y": discoverability["y"],
            "radius": discoverability["radius"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to persist clue location: {e}")
