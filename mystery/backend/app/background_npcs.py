"""Shared background-NPC injection, used by every case source: hand-authored
cases (case_001..case_006), the deterministic template generator, and
llm_assisted case assembly.

Background NPCs (`Agent.is_background = True`) are ambient, non-suspect
villagers who wander the map for flavor via ordinary public
movement/arrival/departure events. They are excluded from Suspects, the
Board, accusation, and interview (see main.py). Two invariants apply to
every route this module builds (see CLAUDE.md):

  1. Never route a background NPC through the murder location, its private
     back-rooms, or any location that stages a scripted clue event during
     the murder window.
  2. Never let a background NPC collide with itself in time (validator's
     "no agent in two places at once" rule) -- trivially satisfied here
     since each NPC's own stops are scheduled at strictly increasing
     minutes.

This module is deliberately independent of *how* a case was produced: it
only reads the assembled CaseData (locations, murder window, clues,
events) and appends new Agent/Event objects, so it can run as the final
step for every case-generation path without needing to understand
templates, LLM beats, or compaction.
"""

from __future__ import annotations

import random

from .models import Agent, CaseData, Event

MAX_BACKGROUND_NPCS = 10

# Fixed identity pool. `case_001` already ships two of these (Rosa, Tam) --
# add_background_npcs() skips any full_name already present in the case, so
# it never creates duplicates when topping up an existing cast.
BACKGROUND_NPC_POOL: list[dict] = [
    {"suffix": "rosa", "full_name": "Rosa Fenn", "occupation": "Groundskeeper",
     "portrait": "🌿", "pronoun": "she", "verb": "tending the flowerbeds"},
    {"suffix": "tam", "full_name": "Tam Doyle", "occupation": "Postal carrier",
     "portrait": "📨", "pronoun": "he", "verb": "finishing a post round"},
    {"suffix": "birdie", "full_name": "Birdie Voss", "occupation": "Street sweeper",
     "portrait": "🧹", "pronoun": "she", "verb": "sweeping the front step"},
    {"suffix": "gus", "full_name": "Gus Farrow", "occupation": "Newspaper seller",
     "portrait": "📰", "pronoun": "he", "verb": "setting out the morning papers"},
    {"suffix": "sal", "full_name": "Sal Ibori", "occupation": "Milkman",
     "portrait": "🥛", "pronoun": "he", "verb": "leaving bottles on the step"},
    {"suffix": "effie", "full_name": "Effie Marsh", "occupation": "Dog walker",
     "portrait": "🐕", "pronoun": "she", "verb": "walking the dog past"},
    {"suffix": "cole", "full_name": "Cole Byrne", "occupation": "Window cleaner",
     "portrait": "🪟", "pronoun": "he", "verb": "wiping down the windows"},
    {"suffix": "min", "full_name": "Min Okafor", "occupation": "Baker's assistant",
     "portrait": "🥖", "pronoun": "she", "verb": "carrying a tray of loaves"},
    {"suffix": "dez", "full_name": "Dez Holt", "occupation": "Market stallholder",
     "portrait": "🧺", "pronoun": "he", "verb": "setting up a stall"},
    {"suffix": "wren", "full_name": "Wren Ashby", "occupation": "Busker",
     "portrait": "🎻", "pronoun": "she", "verb": "tuning up for a morning busk"},
]


def _to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _to_hhmm(total: int) -> str:
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def _unsafe_locations(case: CaseData) -> set[str]:
    """Locations a background NPC must never be scheduled at: the murder
    location, the discovery location, and anywhere a clue-bearing or hidden
    (spine) event lands during the murder window."""
    c = case.case
    unsafe = {c.murder_location_id, c.discovery_location_id} - {None}
    try:
        window_start, window_end = _to_min(c.murder_window[0]), _to_min(c.murder_window[1])
    except Exception:
        return unsafe
    for e in case.events:
        try:
            t = _to_min(e.time)
        except Exception:
            continue
        if window_start <= t <= window_end and (
            e.linked_clue_ids or e.event_type in ("murder", "body_discovery") or e.visibility == "hidden"
        ):
            unsafe.add(e.location_id)
    return unsafe


def _safe_locations(case: CaseData) -> list[str]:
    unsafe = _unsafe_locations(case)
    return [l.location_id for l in case.locations if l.visibility_type == "public" and l.location_id not in unsafe]


def add_background_npcs(case: CaseData, rng: random.Random, target_count: int = MAX_BACKGROUND_NPCS) -> list[Agent]:
    """Tops up `case` with background NPCs (up to MAX_BACKGROUND_NPCS total)
    and their ambient events. Mutates `case.agents`/`case.events` in place
    and returns the newly added agents. Best-effort: if there's nowhere safe
    to put them, it's a silent no-op rather than a failure."""
    target_count = max(0, min(MAX_BACKGROUND_NPCS, target_count))
    existing_names = {a.full_name for a in case.agents}
    existing_ids = {a.agent_id for a in case.agents}
    need = target_count - sum(1 for a in case.agents if a.is_background)
    if need <= 0:
        return []

    safe_locations = _safe_locations(case)
    if not safe_locations:
        return []

    candidates = [npc for npc in BACKGROUND_NPC_POOL if npc["full_name"] not in existing_names]
    rng.shuffle(candidates)
    chosen = candidates[:need]
    if not chosen:
        return []

    c = case.case
    sim_start = _to_min(c.sim_start_time)
    window_start = _to_min(c.murder_window[0])
    span = max(6, window_start - sim_start - 5)

    locations_by_id = {l.location_id for l in case.locations}
    names_by_id = {l.location_id: l.name for l in case.locations}

    new_agents: list[Agent] = []
    new_events: list[Event] = []

    for i, npc in enumerate(chosen):
        agent_id = f"agent_bg_{npc['suffix']}"
        if agent_id in existing_ids:
            agent_id = f"agent_bg_{npc['suffix']}_{i}"
        existing_ids.add(agent_id)

        route = [safe_locations[i % len(safe_locations)]]
        if len(safe_locations) > 1:
            route.append(safe_locations[(i + 1) % len(safe_locations)])
        if len(safe_locations) > 2 and rng.random() < 0.6:
            route.append(safe_locations[(i + 2) % len(safe_locations)])

        home = route[0]
        work = route[1] if len(route) > 1 else home
        if work not in locations_by_id:
            work = home

        first_name = npc["full_name"].split()[0]
        agent = Agent(
            agent_id=agent_id,
            full_name=npc["full_name"],
            age=rng.randint(22, 70),
            occupation=npc["occupation"],
            traits=[],
            portrait=npc["portrait"],
            home_location_id=home,
            work_location_id=work,
            routine_summary=f"{first_name} keeps to a quiet {npc['occupation'].lower()} routine around the village.",
            relationships=[],
            is_background=True,
        )
        new_agents.append(agent)

        step = max(3, span // (len(route) + 1))
        t = sim_start + 2 + ((i * 7) % max(1, span // 2))
        prev_loc = None
        for j, loc in enumerate(route):
            t = min(t, window_start - 1)
            loc_name = names_by_id.get(loc, "the square")
            new_events.append(Event(
                event_id=f"ev_bg_{npc['suffix']}_{j}",
                time=_to_hhmm(t),
                location_id=loc,
                agent_ids=[agent_id],
                event_type="arrival" if j == 0 else "movement",
                truth_description=f"{first_name} is seen near {loc_name}, {npc['verb']}.",
                visibility="public",
                importance=2,
                from_location_id=prev_loc,
                to_location_id=loc,
            ))
            prev_loc = loc
            t += step

    case.agents.extend(new_agents)
    case.events.extend(new_events)
    return new_agents
