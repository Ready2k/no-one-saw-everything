"""FastAPI app for the murder mystery investigation API."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import challenge as challenge_engine
from . import interview as interview_engine
from . import judge as judge_engine
from .challenge import ChallengeError
from .models import (
    AccusationRequest,
    AskRequest,
    ChallengeRequest,
    InspectRequest,
    Note,
    NoteCreate,
    NoteUpdate,
    SuspicionUpdate,
)
from .projections import (
    project_agent,
    project_claim,
    project_clue,
    project_location,
    visible_events,
)
from .session import get_session, reset_session
from .store import load_case

CASE_ID = "case_001"

app = FastAPI(title="No One Saw Everything", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def case_data():
    return load_case(CASE_ID)


def session():
    return get_session(CASE_ID)


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
    }


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
    newly, already, locked = [], [], 0
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
        sess.discovered_clue_ids.add(clue.clue_id)
        newly.append(project_clue(clue))

    hint = None
    if locked:
        hint = "Something about this place feels off, but you can't put your finger on it yet."
    return {
        "location": project_location(location),
        "new_clues": newly,
        "known_clues": already,
        "hint": hint,
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
    return interview_engine.public_ask_response(resp)


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
    session().suspicion[payload.agent_id] = payload.level
    return {"agent_id": payload.agent_id, "level": payload.level}


@app.get("/api/board")
def board():
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
    return result


@app.get("/api/reveal")
def reveal():
    """The truth is only available once an accusation has been submitted."""
    sess = session()
    if sess.accusation is None:
        raise HTTPException(403, "The truth is sealed until you make an accusation.")
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
    reset_session(CASE_ID)
    return {"reset": True}
