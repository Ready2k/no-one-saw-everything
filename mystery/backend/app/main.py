"""FastAPI app for the murder mystery investigation API."""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from fastapi import FastAPI, HTTPException, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import os

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
from .session import get_session, reset_session
from .case_store import get_case as fetch_case
from .telemetry import log_telemetry_event

ACTIVE_CASE_ID = "case_001"

from .case_store import set_active_start_time
set_active_start_time(fetch_case(ACTIVE_CASE_ID).case.sim_start_time)

app = FastAPI(title="No One Saw Everything", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MYSTERY_PLAYTEST_MODE = os.getenv("MYSTERY_PLAYTEST_MODE", "false").lower() == "true"

@app.get("/api/config")
def get_config():
    from .llm.config import get_llm_config

    llm = get_llm_config()
    return {
        "playtest_mode": MYSTERY_PLAYTEST_MODE,
        "llm_dialogue_enabled": llm.dialogue_enabled,
        "llm_generation_available": llm.configured and llm.provider != "fake",
        "llm_model": llm.model if llm.provider != "fake" else None,
        "llm_detected_source": llm.detected_source,
    }


class LLMSettingsUpdate(BaseModel):
    provider: str  # "fake" | "auto" | "openai_compatible"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    dialogue_enabled: bool = False
    beliefs_enabled: bool = False


@app.get("/api/llm-settings")
def get_llm_settings():
    """Returns the saved LLM settings (if any) plus the currently effective config,
    so the in-game Settings panel can show what will actually be used."""
    from .llm.config import get_llm_config, load_saved_settings

    saved = load_saved_settings()
    effective = get_llm_config()
    return {
        "saved": saved.model_dump() if saved else None,
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


@app.put("/api/llm-settings")
def update_llm_settings(payload: LLMSettingsUpdate):
    from .llm.config import SavedLLMSettings, save_settings, get_llm_config

    if payload.provider not in ("fake", "auto", "openai_compatible"):
        raise HTTPException(status_code=400, detail="Invalid provider")
    if payload.provider == "openai_compatible" and (not payload.base_url or not payload.model):
        raise HTTPException(
            status_code=400,
            detail="base_url and model are required for the openai_compatible provider",
        )

    save_settings(SavedLLMSettings(**payload.model_dump()))

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

    if not payload.base_url.strip():
        raise HTTPException(status_code=400, detail="base_url is required")

    models, error = list_models_for_base_url(payload.base_url.strip(), payload.api_key)
    return {"models": models, "error": error}


class LlmTestRequest(BaseModel):
    base_url: str
    api_key: Optional[str] = None
    model: str


@app.post("/api/llm-settings/test")
def test_llm_settings(payload: LlmTestRequest):
    """Sends a real chat completion request to the given endpoint/model so the
    Settings panel can prove the LLM is actually generating a response, rather
    than just resolving a reachable model list."""
    from .llm.config import normalize_base_url
    from .llm.client import OpenAICompatibleLLMClient
    import time
    import uuid

    if not payload.base_url.strip() or not payload.model.strip():
        raise HTTPException(status_code=400, detail="base_url and model are required")

    base_url = normalize_base_url(payload.base_url.strip())
    nonce = uuid.uuid4().hex[:6]
    client = OpenAICompatibleLLMClient(
        base_url=base_url, api_key=payload.api_key, model=payload.model.strip()
    )

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


@app.post("/api/llm-settings/probe")
def probe_llm_settings():
    """Runs auto-detection now (bypassing the cache) so the Settings panel can
    show whether a local LLM host is currently reachable before the user saves
    provider='auto'."""
    from .llm.discovery import detect_llm

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


def case_data():
    return fetch_case(ACTIVE_CASE_ID)


def session():
    return get_session(ACTIVE_CASE_ID)


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
    from .case_store import list_all_cases
    return list_all_cases()


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
    from .town_map import canonical_map_definition, map_config, map_payload

    case = case_data()
    sess = session()

    # Migrated cases use the reusable canonical HD map contract; unmigrated
    # cases preserve the legacy fallback art and coordinates.
    if map_config(case.case.case_id):
        map_definition = canonical_map_definition()
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
    import hashlib
    for clue in case.clues:
        d = clue.discoverability
        if d.method != "inspect" or d.location_id != req.location_id:
            continue
        if clue.clue_id in sess.discovered_clue_ids:
            already.append(project_clue(clue))
            continue
        if any(p not in sess.discovered_clue_ids for p in d.required_prior_clue_ids):
            locked += 1  # something is here, but the player lacks context
            continue
            
        x = d.x
        y = d.y
        if x is None or y is None:
            seed_str = f"{case.case.case_id}:{req.location_id}:{clue.clue_id}"
            digest = hashlib.md5(seed_str.encode("utf-8")).hexdigest()
            x = 10 + ((int(digest[0:4], 16) / 65535.0) * 80)
            y = 10 + ((int(digest[4:8], 16) / 65535.0) * 80)
            
        hidden_clues.append({
            "clue_id": clue.clue_id,
            "x": x,
            "y": y,
            "radius": d.radius if d.radius is not None else 8.0,
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
    case = case_data()
    sess = session()
    from app.free_text_api import handle_free_text
    resp = handle_free_text(req, case, sess)
    log_telemetry_event(sess, "free_text_question_asked", {"agent_id": req.agent_id})
    log_telemetry_event(sess, "interview_answered", {"agent_id": req.agent_id, "question_type": "free_text"})
    return resp


@app.get("/api/interview/{agent_id}")
def transcript(agent_id: str):
    sess = session()
    t = sess.transcripts.get(agent_id)
    return t.messages if t else []


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
def challenge_suggestions(agent_id: Optional[str] = None):
    """Claims for which the player already holds evidence a challenge can use.
    Drives the 'Challenge' affordance without exposing the full rule set or
    any hidden truth — only heard claims and discovered clues are referenced."""
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
            # Log each suggestion once per session; the UI polls this endpoint.
            if key not in sess.logged_suggestion_keys:
                sess.logged_suggestion_keys.add(key)
                log_telemetry_event(sess, "challenge_suggested", {"target_agent_id": rule.target_agent_id, "challenged_claim_id": rule.challenged_claim_id})
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
    return out


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
    sess = session()
    sess.suspicion[payload.agent_id] = payload.level
    log_telemetry_event(sess, "marker_updated", {"agent_id": payload.agent_id, "type": "suspicion", "level": payload.level})
    return {"agent_id": payload.agent_id, "level": payload.level}

from .models import MarkerUpdate
@app.post("/api/session/markers")
def update_markers(payload: MarkerUpdate):
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
    return session().event_log

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
    reset_session(ACTIVE_CASE_ID)
    return {"reset": True}


@app.post("/api/cases/generate")
def generate(req: GenerateCaseRequest):
    from .generator import generate_case
    from .validator import validate_case
    from .case_store import register_case
    global ACTIVE_CASE_ID

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
        ACTIVE_CASE_ID = new_case.case.case_id
        set_active_start_time(new_case.case.sim_start_time)
        # A fresh activation always means a fresh investigation — otherwise
        # re-generating the same (type, seed) resurrects a stale session.
        reset_session(ACTIVE_CASE_ID)
        active_session_id = ACTIVE_CASE_ID

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

@app.post("/api/cases/activate")
def activate_case(req: ActivateCaseRequest):
    from .case_store import _GENERATED_CASES, load_case_from_disk
    global ACTIVE_CASE_ID
    
    # Validate case exists in store
    if req.case_id not in _GENERATED_CASES:
        try:
            load_case_from_disk(req.case_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Case not found")
            
    ACTIVE_CASE_ID = req.case_id
    set_active_start_time(fetch_case(ACTIVE_CASE_ID).case.sim_start_time)
    reset_session(ACTIVE_CASE_ID)
    
    return {"active_session_id": ACTIVE_CASE_ID}


@app.get("/api/generated_cases")
def list_generated_cases(
    sort_by: Optional[str] = None, # "quality_score", "created_at"
    tone: Optional[str] = None,
    case_type: Optional[str] = None,
    best_of_n: Optional[bool] = None,
    fallback_used: Optional[bool] = None
):
    from .case_store import DATA_DIR, normalize_case_metadata
    import json
    
    entries = []
    if not DATA_DIR.exists():
        return entries
        
    for p in DATA_DIR.iterdir():
        if p.is_dir() and p.name != "templates":
            if p.name.startswith("gen_") or (p / "metadata.json").exists():
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
                
                entries.append({
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
                    "load_status": load_status
                })

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
    from .case_store import CaseLoadError
    try:
        case_data = fetch_case(case_id)
        return case_data
    except CaseLoadError as cle:
        if cle.load_status == "missing_case_data":
            raise HTTPException(status_code=404, detail="Case not found")
        raise HTTPException(status_code=400, detail=f"Case is corrupted: {cle.load_status}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load case: {e}")


@app.post("/api/generated_cases/{case_id}/activate")
def activate_generated_case(case_id: str):
    from .case_store import save_case_to_disk, CaseLoadError
    from datetime import datetime
    global ACTIVE_CASE_ID
    
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
        
    ACTIVE_CASE_ID = case_id
    set_active_start_time(case_data.case.sim_start_time)
    reset_session(ACTIVE_CASE_ID)
    
    if case_data.metadata:
        case_data.metadata["activated_at"] = datetime.now().isoformat() + "Z"
        save_case_to_disk(case_data)
        
    return {"status": "success", "active_session_id": ACTIVE_CASE_ID}


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
    from .case_store import delete_case_from_disk
    try:
        delete_case_from_disk(case_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Developer Map Editor Endpoints (Dev-only)
# ---------------------------------------------------------------------------

def _layout_file_version(path) -> str:
    """Hash of the layout file's current on-disk bytes, used as an optimistic
    concurrency token: a save proceeds only if the client's copy was loaded
    from this exact on-disk state, so two editors saving around the same time
    can't silently clobber each other. Empty file == no file, so a fresh
    editor session (nothing to conflict with) still gets a stable token."""
    import hashlib

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
    from .place_library import load_building_library
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
            "lights": {}
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
            cases_details.append({
                "case_id": case_id,
                "title": case_data.case.title,
                "locations": locations,
                "objects": objects
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
