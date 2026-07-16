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
     "no agent in two places at once" rule) — trivially satisfied here
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
#
# `activities` is keyed by time-of-day bucket (see _time_bucket): cases run at
# any hour (case_004 starts at 22:00), so each NPC needs phrases that make
# sense at that hour, and at least two per bucket so consecutive sightings of
# the same NPC don't repeat the same line.
BACKGROUND_NPC_POOL: list[dict] = [
    {"suffix": "rosa", "full_name": "Rosa Fenn", "occupation": "Groundskeeper",
     "portrait": "🌿", "pronoun": "she", "age": 54,
     "routine": "Tends the fountain flowerbeds at first light, then sweeps the rear paths before the village wakes properly.", "activities": {
         "morning": ["tending the flowerbeds", "watering the planters"],
         "afternoon": ["trimming the hedges", "raking the paths"],
         "evening": ["packing away her garden tools", "doing a last sweep of the green"],
         "night": ["locking up the tool shed", "carrying a lantern home from the green"]}},
    {"suffix": "tam", "full_name": "Tam Doyle", "occupation": "Postal carrier",
     "portrait": "📨", "pronoun": "he", "age": 47,
     "routine": "Does the post round through the square, the bookshop and the clinic before most doors have even opened.", "activities": {
         "morning": ["starting the early post round", "sorting letters from his mailbag"],
         "afternoon": ["finishing a post round", "emptying the postbox"],
         "evening": ["heading home with an empty mailbag", "dropping off one last parcel"],
         "night": ["out for some late air, off duty", "posting a letter of his own on the way home"]}},
    {"suffix": "birdie", "full_name": "Birdie Voss", "occupation": "Street sweeper",
     "portrait": "🧹", "pronoun": "she", "age": 66,
     "routine": "Sweeps the shopfronts in the order the village wakes — cafe, bookshop, clinic — and knows everyone's doormat better than they do.", "activities": {
         "morning": ["sweeping the front step", "brushing down the pavement"],
         "afternoon": ["sweeping out the gutters", "picking up stray litter"],
         "evening": ["sweeping up after the day's foot traffic", "stacking her brooms on the cart"],
         "night": ["sweeping under the lamplight", "clearing the day's litter before turning in"]}},
    {"suffix": "gus", "full_name": "Gus Farrow", "occupation": "Newspaper seller",
     "portrait": "📰", "pronoun": "he", "age": 51,
     "routine": "Sets the papers out from the fountain to the cafe and reads every front page aloud to whoever stands still long enough.", "activities": {
         "morning": ["setting out the morning papers", "calling the day's headlines"],
         "afternoon": ["hawking the midday edition", "restocking his paper rack"],
         "evening": ["selling off the last of the evening edition", "bundling unsold papers"],
         "night": ["tying up bundles for tomorrow's papers", "shuttering the news stand"]}},
    {"suffix": "sal", "full_name": "Sal Ibori", "occupation": "Milkman",
     "portrait": "🥛", "pronoun": "he", "age": 54,
     "routine": "Runs the milk round in strict order — cafe first, bookshop second — and rates every doorstep in the village by how promptly they bring the empties back.", "activities": {
         "morning": ["leaving bottles on the step", "clinking crates off the milk cart"],
         "afternoon": ["collecting the empties", "settling milk accounts door to door"],
         "evening": ["loading crates for tomorrow's round", "wheeling the milk cart back to the yard"],
         "night": ["collecting empty bottles ahead of the dawn round", "readying the cart for the early round"]}},
    {"suffix": "effie", "full_name": "Effie Marsh", "occupation": "Dog walker",
     "portrait": "🐕", "pronoun": "she", "age": 46,
     "routine": "Walks three dogs that aren't hers on a route their owners never chose; the terrier decides when they stop, and it always stops at the fountain.", "activities": {
         "morning": ["walking the dog past", "letting the dog sniff every lamppost"],
         "afternoon": ["walking a pair of dogs past", "throwing a stick for the dog"],
         "evening": ["taking the dog for its evening walk", "coaxing the dog along home"],
         "night": ["giving the dog its late-night walk", "walking the dog one last time before bed"]}},
    {"suffix": "cole", "full_name": "Cole Byrne", "occupation": "Window cleaner",
     "portrait": "🪟", "pronoun": "he", "age": 26,
     "routine": "Works his ladder clockwise around the square; swears the clinic's windows are the only ones anyone ever thanks him for.", "activities": {
         "morning": ["wiping down the windows", "setting his ladder against a wall"],
         "afternoon": ["polishing the shopfront glass", "moving his ladder to the next building"],
         "evening": ["packing up his ladder and bucket", "collecting payment for the day's work"],
         "night": ["carrying his ladder home", "heading home after a long day"]}},
    {"suffix": "min", "full_name": "Min Okafor", "occupation": "Baker's assistant",
     "portrait": "🥖", "pronoun": "she", "age": 22,
     "routine": "Up before the ovens, delivers the morning loaves to the cafe and the bookshop, and always keeps the misshapen one back for herself.", "activities": {
         "morning": ["carrying a tray of loaves", "delivering warm bread"],
         "afternoon": ["fetching sacks of flour", "handing out the last of the lunch rolls"],
         "evening": ["scrubbing down the bakery trays", "carrying home the day's unsold bread"],
         "night": ["heading in to start the overnight dough", "hauling flour in for the overnight bake"]}},
    {"suffix": "dez", "full_name": "Dez Holt", "occupation": "Market stallholder",
     "portrait": "🧺", "pronoun": "he", "age": 61,
     "routine": "Trundles his stall cart around the village testing pitches; has moved 'the perfect spot' four times this year and defends each one loudly.", "activities": {
         "morning": ["setting up a stall", "laying out the morning's produce"],
         "afternoon": ["calling out prices at the stall", "haggling with a customer"],
         "evening": ["packing up the stall", "selling off the day's leftovers cheap"],
         "night": ["wheeling the empty stall cart home", "counting the day's takings"]}},
    {"suffix": "wren", "full_name": "Wren Ashby", "occupation": "Busker",
     "portrait": "🎻", "pronoun": "she", "age": 61,
     "routine": "Tunes the fiddle by the square until her fingers warm up, then follows the smell of coffee to the cafe pitch.", "activities": {
         "morning": ["tuning up for a morning busk", "picking a good corner to play"],
         "afternoon": ["busking for the afternoon crowd", "collecting coins from her violin case"],
         "evening": ["playing a last tune for the evening", "counting the coins from her case"],
         "night": ["carrying her violin case home", "humming her way home from a late set"]}},
]


def _time_bucket(minute: int) -> str:
    """Coarse time-of-day bucket for an absolute minute-of-day."""
    h = (minute // 60) % 24
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 17:
        return "afternoon"
    if 17 <= h < 21:
        return "evening"
    return "night"


def npc_activity(npc: dict, minute: int, stop_index: int) -> str:
    """Pick an activity phrase appropriate to the hour, cycling through the
    bucket's variants so back-to-back sightings don't repeat."""
    phrases = npc["activities"][_time_bucket(minute)]
    return phrases[stop_index % len(phrases)]


# Every ambient sighting used to read "<Name> is seen near <Place>, <activity>." — ten NPCs
# times three stops meant thirty near-identical lines per case, which is what made the
# generated villages read as a screensaver. Vary the framing instead.
_SIGHTING_FRAMES = [
    "{name} is at {place}, {activity}.",
    "{name} passes {place}, {activity}.",
    "{name} stops by {place}, {activity}.",
    "At {place}, {name} is {activity}.",
    "{name} is by {place}, {activity}.",
]


def npc_sighting(npc: dict, place: str, minute: int, stop_index: int, variant: int) -> str:
    """Ambient sighting line: place + hour-appropriate activity, in a varied frame."""
    frame = _SIGHTING_FRAMES[variant % len(_SIGHTING_FRAMES)]
    return frame.format(
        name=npc["full_name"].split()[0],
        place=place,
        activity=npc_activity(npc, minute, stop_index),
    )


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
            # Fixed in the pool, not rolled per case: these are the *same villagers* across
            # every case, and re-rolling made Sal 54 in case_001 and 24 in case_002.
            age=npc["age"],
            occupation=npc["occupation"],
            traits=[],
            portrait=npc["portrait"],
            home_location_id=home,
            work_location_id=work,
            # An authored routine with an opinion in it. The generated "<Name> keeps to a quiet
            # <job> routine around the village" made all ten NPCs interchangeable and collapsed
            # the village-realism score of every generated case.
            routine_summary=npc["routine"],
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
                truth_description=npc_sighting(npc, loc_name, t, j, variant=i + j),
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
