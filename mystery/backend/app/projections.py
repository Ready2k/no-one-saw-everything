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
        "portrait_art": agent.portrait_art.model_dump() if agent.portrait_art else None,
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


# ---------------------------------------------------------------------------
# Map replay projections (visual layer only — same visibility rules apply)
# ---------------------------------------------------------------------------

# Safe derivation of a visual marker type from a *public* event.
_PUBLIC_VISUAL_TYPES = {
    "movement": "agent_move",
    "arrival": "agent_move",
    "departure": "agent_move",
    "routine": "agent_present",
    "conversation": "conversation_marker",
    "argument": "conversation_marker",
    "private_meeting": "conversation_marker",
    "object_use": "object_marker",
    "object_drop": "object_marker",
    "sound": "sound_marker",
    "body_discovery": "body_discovery",
}

# For non-public events, only ambiguous marker types may cross the API —
# an authored visual type that would identify the actor is coerced.
_AMBIGUOUS_SAFE_TYPES = {"sound_marker", "body_discovery", "unknown_figure", "hidden_activity"}


def _visual_event_type(event: Event) -> str:
    if event.visibility == "public":
        return event.visual_event_type or _PUBLIC_VISUAL_TYPES.get(
            event.event_type, "agent_present"
        )
    # public_partial / private: never a type that implies a known actor.
    authored = event.visual_event_type
    if authored in _AMBIGUOUS_SAFE_TYPES:
        return authored
    if event.event_type == "sound":
        return "sound_marker"
    if event.event_type == "body_discovery":
        return "body_discovery"
    if event.visibility == "private":
        return "hidden_activity"
    return "unknown_figure"


def project_map_event(event: Event) -> Optional[dict[str, Any]]:
    """Player-safe map projection of an event, or None if invisible.

    Builds on project_event (same visibility gate) and adds only visual
    fields. from/to locations are exposed for public events, and for
    partials only when explicitly authored (the author has already decided
    the movement itself is observable, e.g. 'a figure crosses the alley').
    """
    projected = project_event(event)
    if projected is None:
        return None
    projected["visual_event_type"] = _visual_event_type(event)
    if event.visibility in ("public", "public_partial"):
        projected["from_location_id"] = event.from_location_id
        projected["to_location_id"] = event.to_location_id
    else:
        projected["from_location_id"] = None
        projected["to_location_id"] = None
    return projected


def project_map_location(loc: Location) -> dict[str, Any]:
    from .map_layout import location_visuals

    position, bounds, layer = location_visuals(loc)
    projected = project_location(loc)
    projected["map_position"] = position.model_dump() if position else None
    projected["map_bounds"] = bounds.model_dump() if bounds else None
    projected["visual_layer"] = layer
    return projected


def project_map_agent(agent: Agent) -> dict[str, Any]:
    from .map_layout import agent_sprite

    sprite_id, sprite_asset = agent_sprite(agent)
    projected = project_agent(agent)
    projected["sprite_id"] = sprite_id
    projected["sprite_asset"] = sprite_asset
    return projected


def visible_map_events(
    case: CaseData,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    location_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    out = []
    for event in case.events:
        projected = project_map_event(event)
        if projected is None:
            continue
        if time_from and minutes(event.time) < minutes(time_from):
            continue
        if time_to and minutes(event.time) > minutes(time_to):
            continue
        if location_id and event.location_id != location_id:
            continue
        # Same rule as visible_events: agent filtering only matches events
        # where the agent is publicly identifiable.
        if agent_id and agent_id not in projected["agent_ids"]:
            continue
        out.append(projected)
    out.sort(key=lambda e: minutes(e["time"]))
    return out


def truth_map_events(case: CaseData) -> list[dict[str, Any]]:
    """The full true timeline for the post-accusation truth replay.

    Only ever call this after an accusation has been judged — the caller
    is responsible for that gate.
    """
    out = []
    for event in case.events:
        out.append(
            {
                "event_id": event.event_id,
                "time": event.time,
                "location_id": event.location_id,
                "agent_ids": event.agent_ids,
                "event_type": event.event_type,
                "description": event.truth_description,
                "visibility": event.visibility,
                "importance": event.importance,
                "visual_event_type": (
                    "hidden_activity"
                    if event.event_type in ("murder", "hidden_action")
                    else event.visual_event_type
                    or _PUBLIC_VISUAL_TYPES.get(event.event_type, "agent_present")
                ),
                "from_location_id": event.from_location_id,
                "to_location_id": event.to_location_id,
                "was_hidden": event.visibility in ("hidden", "private"),
            }
        )
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
