"""Player-safe projections of locked truth.

Nothing that crosses the API boundary may leak hidden truth: killer
identity, lie flags, hidden events, secret relationships, or which
conclusions a clue supports.
"""

from __future__ import annotations

from typing import Any, Optional

from .models import Agent, CaseData, Claim, Clue, Event, GameObject, Location
from .session import Session
from .case_store import minutes


def project_agent(agent: Agent) -> dict[str, Any]:
    return {
        "agent_id": agent.agent_id,
        "full_name": agent.full_name,
        "age": agent.age,
        "occupation": agent.occupation,
        "traits": agent.traits,
        "portrait": agent.portrait,
        "home_location_id": agent.home_location_id,
        "work_location_id": agent.work_location_id,
        "routine_summary": agent.routine_summary,
        "is_victim": agent.is_victim,
    }


def project_location(loc: Location) -> dict[str, Any]:
    return {
        "location_id": loc.location_id,
        "name": loc.name,
        "description": loc.description,
        "connected_location_ids": loc.connected_location_ids,
        "visibility_type": loc.visibility_type,
    }


def project_event(event: Event) -> Optional[dict[str, Any]]:
    """Return the player-visible form of an event, or None if invisible."""
    if event.visibility == "hidden":
        return None
    if event.visibility == "public":
        text = event.truth_description
        agent_ids = event.agent_ids
    elif event.visibility == "public_partial":
        if not event.player_description:
            return None
        text = event.player_description
        agent_ids = []  # identity is part of what's obscured
    else:  # private: locked placeholder only if authored
        if not event.player_description:
            return None
        text = event.player_description
        agent_ids = []
    return {
        "event_id": event.event_id,
        "time": event.time,
        "location_id": event.location_id,
        "agent_ids": agent_ids,
        "event_type": event.event_type if event.visibility == "public" else "observation",
        "description": text,
        "visibility": event.visibility,
        "importance": event.importance,
    }


def visible_events(
    case: CaseData,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    location_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    out = []
    for event in case.events:
        projected = project_event(event)
        if projected is None:
            continue
        if time_from and minutes(event.time) < minutes(time_from):
            continue
        if time_to and minutes(event.time) > minutes(time_to):
            continue
        if location_id and event.location_id != location_id:
            continue
        # Agent filtering only matches events where the agent is publicly
        # identifiable — otherwise "follow sim" would deanonymise partials.
        if agent_id and agent_id not in projected["agent_ids"]:
            continue
        out.append(projected)
    out.sort(key=lambda e: minutes(e["time"]))
    return out


def project_clue(clue: Clue) -> dict[str, Any]:
    return {
        "clue_id": clue.clue_id,
        "title": clue.title,
        "clue_type": clue.clue_type,
        "description": clue.description,
        "strength": clue.strength,
        "reliability": clue.reliability,
        "ambiguity": clue.ambiguity,
        "linked_event_ids": clue.linked_event_ids,
        "linked_agent_ids": clue.linked_agent_ids,
        "linked_location_ids": clue.linked_location_ids,
        "linked_object_ids": clue.linked_object_ids,
    }


def project_claim(claim: Claim) -> dict[str, Any]:
    return {
        "claim_id": claim.claim_id,
        "speaker_agent_id": claim.speaker_agent_id,
        "claim_text": claim.claim_text,
        "claim_type": claim.claim_type,
        "time_reference": claim.time_reference,
        "location_reference_id": claim.location_reference_id,
        "player_known_status": claim.player_known_status,
    }


def project_object(obj: GameObject, case: CaseData, session: Session) -> Optional[dict[str, Any]]:
    """Objects surface only once a discovered clue references them."""
    referenced = any(
        obj.object_id in clue.linked_object_ids
        for clue in case.clues
        if clue.clue_id in session.discovered_clue_ids
    )
    if not referenced:
        return None
    return {
        "object_id": obj.object_id,
        "name": obj.name,
        "description": obj.description,
        "normal_location_id": obj.normal_location_id,
    }


def build_playtest_export(session: Session, case: CaseData, include_reveal: bool = False) -> dict[str, Any]:
    export = {
        "export_visibility": "post_reveal" if include_reveal else "pre_reveal",
        "case_metadata": {
            "case_id": case.case.case_id,
            "case_type": case.case.case_type,
            "title": case.case.title,
        },
        "telemetry": session.event_log,
        "discovered_clues": [project_clue(c) for c in case.clues if c.clue_id in session.discovered_clue_ids],
        "notes": [n.model_dump() for n in session.notes.values()],
        "interviews": [t.model_dump() for t in session.transcripts.values()],
        "challenges": [c.model_dump() for c in session.challenges.values()],
        "markers": session.case_board_markers,
        "suspicion": session.suspicion,
        "feedback": session.feedback.model_dump() if session.feedback else None,
    }
    
    if include_reveal and session.accusation:
        export["accusation_result"] = session.accusation.model_dump()
        
    return export
