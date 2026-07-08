"""Deterministic timeline compiler for LLM-generated cases.

Before this, every generated case replayed case_001's 29 template events verbatim
(only names/one-location/clock-offset swapped), so the Rewind and per-agent
Routines were always identical. This module injects variety while keeping the
case provably fair, under a deliberate boundary chosen with the user:

  * The **puzzle spine is kept, not regenerated.** The murder, the body
    discovery, and every clue-bearing event stay exactly as the template
    produced them — their times are already coherent with the clue text and
    with the murder (e.g. "a thud heard at 07:56" must stay at the murder
    minute, not drift). Keeping them means the compiled case inherits the
    template's validity and never leaks or mis-times the murder.
  * Only the **ambient flavour layer** — villagers' public comings and goings
    that carry no clue — is discarded and replaced with the LLM-authored beats,
    and every agent's ``routine_summary`` is refreshed from the plan.

So a generated morning now has fresh ambient life and fresh routines over the
same fair investigative backbone. Called from ``case_assembler.assemble_case``
only when a timeline plan is present; otherwise the template events are kept
unchanged (the no-regression fallback).
"""

import random
from typing import Optional

from ..models import CaseData, Event
from .schemas import TimelinePlan
from .case_assembler import resolve_role


_ALLOWED_BEAT_VIS = {"public", "public_partial", "private"}

# beat_kind -> (event_type, is_movement)
_BEAT_EVENT_TYPE = {
    "routine": ("routine", False),
    "approach": ("arrival", True),
    "opportunity": ("movement", True),
    "suspicious": ("movement", True),
    "sighting": ("movement", True),
    "cover": ("routine", False),
}

# An event is replaceable "ambient flavour" only if it carries no clue, is not
# referenced by any clue, is an ordinary public movement/routine, and is not the
# murder or its discovery. Everything else is the puzzle spine and is kept.
_AMBIENT_EVENT_TYPES = {"routine", "movement", "arrival", "departure"}
_AMBIENT_VISIBILITIES = {"public", "public_partial"}


def _to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _to_hhmm(total: int) -> str:
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def _is_public_location(loc) -> bool:
    if loc is None:
        return False
    if loc.location_type in ("public", "neutral", "crime_scene", "discovery"):
        return True
    return loc.visibility_type == "public"


def compile_timeline(
    timeline: TimelinePlan,
    case_data: CaseData,
    roles: dict[str, str],
    seed: int,
) -> None:
    """Replace the template's ambient events with a freshly authored flavour
    layer and refresh per-agent routines, keeping the puzzle spine intact.
    Mutates ``case_data`` in place."""
    c = case_data.case
    sim_start = _to_min(c.sim_start_time)
    window_start = _to_min(c.murder_window[0])

    agents_by_id = {a.agent_id: a for a in case_data.agents}
    locations_by_id = {l.location_id: l for l in case_data.locations}
    valid_agent_ids = set(agents_by_id)
    public_loc_ids = [l.location_id for l in case_data.locations if _is_public_location(l)]
    fallback_loc = (
        c.discovery_location_id
        or (public_loc_ids[0] if public_loc_ids else next(iter(locations_by_id), ""))
    )
    murder_loc_id = c.murder_location_id if c.murder_location_id in locations_by_id else fallback_loc

    def a_home(agent_id: str) -> Optional[str]:
        a = agents_by_id.get(agent_id)
        return (a.home_location_id or a.work_location_id) if a else None

    def public_loc(salt: str) -> str:
        if not public_loc_ids:
            return fallback_loc
        return public_loc_ids[hash(salt) % len(public_loc_ids)]

    # --- 1. KEEP the puzzle spine; drop only ambient flavour ---------------
    referenced = {eid for cl in case_data.clues for eid in cl.linked_event_ids}

    def is_ambient(e: Event) -> bool:
        return (
            not e.linked_clue_ids
            and e.event_id not in referenced
            and e.event_type in _AMBIENT_EVENT_TYPES
            and e.visibility in _AMBIENT_VISIBILITIES
            and e.event_type not in ("murder", "body_discovery")
        )

    kept = [e for e in case_data.events if not is_ambient(e)]

    # Seed the (agent, minute) reservations from the kept spine so new ambient
    # beats can never place an agent in two places at once (validator #9).
    reserved: dict[tuple[str, int], str] = {}
    for e in kept:
        try:
            t = _to_min(e.time)
        except Exception:
            continue
        for aid in e.agent_ids:
            reserved[(aid, t)] = e.location_id

    def claim(agent_id: str, minute: int, location_id: str) -> int:
        t = max(sim_start, min(minute, window_start - 1))
        for _ in range(max(2, window_start - sim_start + 1)):
            key = (agent_id, t)
            if key not in reserved or reserved[key] == location_id:
                reserved[key] = location_id
                return t
            t += 1
            if t >= window_start:
                t = sim_start
        reserved[(agent_id, minute)] = location_id
        return minute

    new_events: list[Event] = []
    n = 0

    def add_ambient(*, agent_id: str, location_id: str, minute: int, event_type: str,
                    truth: str, visibility: str, player: Optional[str], is_movement: bool):
        nonlocal n
        location_id = location_id if location_id in locations_by_id else fallback_loc
        t = claim(agent_id, minute, location_id)
        short = agent_id.replace("agent_", "")[:6]
        new_events.append(Event(
            event_id=f"ev_gen_amb_{n:02d}_{short}",
            time=_to_hhmm(t),
            location_id=location_id,
            agent_ids=[agent_id],
            event_type=event_type,
            truth_description=truth,
            player_description=player,
            visibility=visibility,
            importance=3,
            from_location_id=(a_home(agent_id) if is_movement else None),
            to_location_id=(location_id if is_movement else None),
        ))
        n += 1

    # --- 2. AMBIENT LAYER from the LLM beats -------------------------------
    span = max(1, window_start - sim_start - 3)
    for b in sorted(timeline.beats, key=lambda x: x.order_hint):
        actor = resolve_role(b.role, roles)
        if actor not in valid_agent_ids or actor == c.victim_id:
            continue  # the victim's movements are part of the fixed spine
        lr = (b.location_role or "public").strip().lower()
        if lr == "murder_scene":
            loc = public_loc(b.role)          # ambient villagers never staged at the scene
        elif lr == "victim_home":
            loc = a_home(c.victim_id) or public_loc(b.role)
        elif lr == "killer_home":
            loc = a_home(c.killer_id) or public_loc(b.role)
        elif lr == "role_home":
            loc = a_home(actor) or public_loc(b.role)
        else:  # public / witness_spot / unknown
            loc = public_loc(b.role + b.location_role)

        vis = b.visibility if b.visibility in _ALLOWED_BEAT_VIS else "public"
        player = b.public_summary
        if vis == "public_partial" and not player:
            vis = "private"
        if vis != "public_partial":
            player = None

        etype, is_move = _BEAT_EVENT_TYPE.get(b.beat_kind, ("routine", False))
        minute = sim_start + 2 + (b.order_hint % span)
        add_ambient(agent_id=actor, location_id=loc, minute=minute, event_type=etype,
                    truth=b.action_summary, visibility=vis, player=player, is_movement=is_move)

    # --- 3. COVERAGE: no suspect with an empty rewind ----------------------
    present = {aid for e in (kept + new_events) for aid in e.agent_ids}
    for idx, aid in enumerate(sorted({p.agent_id for p in case_data.interview_packs} - present)):
        if aid not in valid_agent_ids or aid == c.victim_id:
            continue
        a = agents_by_id[aid]
        add_ambient(agent_id=aid, location_id=a_home(aid) or public_loc(aid),
                    minute=sim_start + 4 + idx * 5, event_type="routine",
                    truth=f"{a.full_name} goes about the start of the morning.",
                    visibility="public", player=None, is_movement=False)

    # --- 4. COMMIT ---------------------------------------------------------
    case_data.events = sorted(kept + new_events, key=lambda e: e.time)

    # --- 5. ROUTINES -------------------------------------------------------
    for rp in timeline.routines:
        a = agents_by_id.get(resolve_role(rp.role, roles))
        if a and rp.routine_summary and rp.routine_summary.strip():
            a.routine_summary = rp.routine_summary.strip()
