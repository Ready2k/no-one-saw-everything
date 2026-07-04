"""FastAPI app for the murder mystery investigation API."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Body
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

    models = list_models_for_base_url(payload.base_url.strip(), payload.api_key)
    return {"models": models}


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
    return [project_location(l) for l in case_data().locations]


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

    case = case_data()
    sess = session()

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
            "asset": MAP_ASSET,
            "image": MAP_IMAGE,
            "width": MAP_WIDTH,
            "height": MAP_HEIGHT,
        },
        "time_range": {
            "start": case.case.sim_start_time,
            "end": case.case.discovery_time,
        },
        "locations": [project_map_location(l) for l in case.locations],
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
        "location": project_map_location(location),
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
    return project_clue(clue)


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
        raise HTTPException(400, "The victim is unavailable for comment.")
    if not any(a.agent_id == req.agent_id for a in case.agents):
        raise HTTPException(404, "No such agent")
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
        if agent.is_victim:
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
    if not any(a.agent_id == req.accused_agent_id and not a.is_victim for a in case.agents):
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

    # Generate the case deterministically or via LLM
    new_case, fallback_used, fallback_reason, repair_attempts = generate_case(
        req.case_type, req.difficulty, req.seed, req.mode, req.fallback_allowed
    )

    # Validate
    val_result = validate_case(new_case)

    # Always register if generated, even if imperfect, but you might reject hard errors?
    # Spec says: "reject invalid generated cases". Let's block play if errors exist.
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
        "active_session_id": active_session_id
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
