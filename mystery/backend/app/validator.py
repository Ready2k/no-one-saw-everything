"""Validates case data for fairness, solvability, and internal consistency."""

from __future__ import annotations

import re
from typing import Any

from . import case_store
from .case_store import minutes
from .models import CaseData

# Author-facing scaffolding, or naked case truth, that must never reach the player-visible
# Agent.routine_summary shown on the Suspects screen. See check 14 in _validate_case_inner.
ROUTINE_LEAK_PATTERNS = [
    r"\bthat night\b",
    r"\bwill need to be\b",
    r"\bwill matter\b",
    r"\bwill have seen\b",
    r"\bwill recognise\b",
    r"\b(?:forged|false) alibi\b",
    r"\b(?:he|she|they) lied\b",
    r"\bsecretly (?:owed|killed|poisoned|followed|paid)\b",
    r"\bthe (?:killer|murderer)\b",
    r"\bif anyone asked\b",
    r"\bmaiden name\b",
]


def validate_case(case: CaseData) -> dict[str, Any]:
    """
    Validates a case (static or generated) to ensure it is fully playable.
    Returns a dict with 'valid', 'score', 'errors', 'warnings', and 'info'.

    Time comparisons must wrap around midnight relative to *this* case's
    start time, not whichever case happens to be active — otherwise
    validating a case while another is active mis-orders its timeline.
    """
    saved_start_time = case_store._ACTIVE_START_TIME
    case_store.set_active_start_time(case.case.sim_start_time)
    try:
        return _validate_case_inner(case)
    finally:
        case_store.set_active_start_time(saved_start_time)


def _validate_case_inner(case: CaseData) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    # 1. Base case setup
    if case.case.killer_id == case.case.victim_id:
        errors.append("Killer and victim are the same person.")

    # 2. Murder event must be hidden
    murders = [e for e in case.events if e.event_type == "murder"]
    if len(murders) != 1:
        errors.append(f"Expected 1 murder event, found {len(murders)}.")
    elif murders[0].visibility != "hidden":
        errors.append("Murder event must have visibility 'hidden'.")
    elif murders[0].time != case.case.time_of_death:
        errors.append("Murder event time does not match case time_of_death.")

    # 3. Referential integrity
    agent_ids = {a.agent_id for a in case.agents}
    location_ids = {l.location_id for l in case.locations}
    object_ids = {o.object_id for o in case.objects}
    clue_ids = {c.clue_id for c in case.clues}
    event_ids = {e.event_id for e in case.events}

    for e in case.events:
        if e.location_id not in location_ids:
            errors.append(f"Event {e.event_id} has invalid location_id {e.location_id}")
        if not set(e.agent_ids) <= agent_ids:
            errors.append(f"Event {e.event_id} has invalid agent_ids")
        if not set(e.object_ids) <= object_ids:
            errors.append(f"Event {e.event_id} has invalid object_ids")
        if not set(e.linked_clue_ids) <= clue_ids:
            errors.append(f"Event {e.event_id} has invalid linked_clue_ids")

    for c in case.clues:
        if not set(c.linked_event_ids) <= event_ids:
            errors.append(f"Clue {c.clue_id} has invalid linked_event_ids")
        if not set(c.linked_agent_ids) <= agent_ids:
            errors.append(f"Clue {c.clue_id} has invalid linked_agent_ids")
        if not set(c.linked_location_ids) <= location_ids:
            errors.append(f"Clue {c.clue_id} has invalid linked_location_ids")
        if not set(c.linked_object_ids) <= object_ids:
            errors.append(f"Clue {c.clue_id} has invalid linked_object_ids")
        if not set(c.discoverability.required_prior_clue_ids) <= clue_ids:
            errors.append(f"Clue {c.clue_id} has invalid required_prior_clue_ids")

    for conc in case.conclusions:
        if not set(conc.supported_by_clue_ids) <= clue_ids:
            errors.append(f"Conclusion {conc.conclusion_id} has invalid supported_by_clue_ids")

    for m in case.memories:
        if m.owner_agent_id not in agent_ids:
            errors.append(f"Memory {m.memory_id} has invalid owner_agent_id")
        if not set(m.linked_clue_ids) <= clue_ids:
            errors.append(f"Memory {m.memory_id} has invalid linked_clue_ids")

    # 4. Three clue rule
    for conc in case.conclusions:
        if conc.required_for_solution:
            if len(conc.supported_by_clue_ids) < 3:
                warnings.append(f"Conclusion {conc.conclusion_id} has only {len(conc.supported_by_clue_ids)} supporting clues (expected 3+).")

    # 5. Discoverability
    pack_by_agent = {p.agent_id: p for p in case.interview_packs}
    visible_event_ids = {
        e.event_id
        for e in case.events
        if e.visibility == "public" or (e.visibility == "public_partial" and e.player_description)
    }

    for clue in case.clues:
        d = clue.discoverability
        if d.method == "inspect":
            if d.location_id not in location_ids:
                errors.append(f"Clue {clue.clue_id} (inspect) missing valid location_id")
        elif d.method == "interview":
            pack = pack_by_agent.get(d.agent_id)
            if not pack:
                errors.append(f"Clue {clue.clue_id} (interview) requires non-existent pack for {d.agent_id}")
            else:
                revealing = [r for r in pack.rules if clue.clue_id in r.reveals_clue_ids]
                if not revealing:
                    errors.append(f"Clue {clue.clue_id}: no interview rule reveals it")
        elif d.method == "observation":
            if not (set(clue.linked_event_ids) & visible_event_ids):
                errors.append(f"Clue {clue.clue_id}: observation clue has no visible linked event")

    # 6. No prerequisite cycles
    graph = {c.clue_id: set(c.discoverability.required_prior_clue_ids) for c in case.clues}
    resolved: set[str] = set()
    for _ in range(len(graph) + 1):
        for clue_id, prereqs in graph.items():
            if clue_id not in resolved and prereqs <= resolved:
                resolved.add(clue_id)
    if resolved != set(graph):
        errors.append(f"Unresolvable clues (cycles detected): {set(graph) - resolved}")

    # 7. Killer MMO
    killer = case.case.killer_id
    types_for_killer = {
        conc.type
        for conc in case.conclusions
        if conc.target_agent_id == killer and conc.required_for_solution
    }
    required_killer_types = {"motive", "opportunity", "means", "false_alibi"}
    missing = required_killer_types - types_for_killer
    if missing:
        errors.append(f"Killer {killer} missing required conclusions: {missing}")

    # 8. Red herrings
    herrings = [c for c in case.conclusions if c.type == "red_herring"]
    anchors = {c.target_agent_id for c in case.conclusions if c.type == "innocence_anchor"}
    if len(herrings) < 2:
        warnings.append(f"Expected at least 2 red herrings, found {len(herrings)}.")
    for h in herrings:
        if h.target_agent_id not in anchors:
            errors.append(f"Red herring for {h.target_agent_id} has no innocence anchor")

    # 9. No agent in two places at once
    seen: dict[tuple[str, str], str] = {}
    for e in case.events:
        for agent_id in e.agent_ids:
            key = (agent_id, e.time)
            if key in seen and seen[key] != e.location_id:
                errors.append(f"Agent {agent_id} at {e.time} in both {seen[key]} and {e.location_id}")
            seen[key] = e.location_id

    # 10. Timeline order
    c = case.case
    if not (minutes(c.sim_start_time) < minutes(c.murder_window[0])):
        errors.append("sim_start_time is not before murder_window start")
    if not (minutes(c.murder_window[0]) <= minutes(c.time_of_death) <= minutes(c.murder_window[1])):
        errors.append("time_of_death is not within murder_window")
    if not (minutes(c.time_of_death) < minutes(c.discovery_time)):
        errors.append("time_of_death is not before discovery_time")

    # 11. Killer seeds
    killer_functions = {
        m.case_function for m in case.memories if m.owner_agent_id == killer
    }
    if "killer_motive" not in killer_functions:
        errors.append("Killer missing 'killer_motive' memory seed")
    if "opportunity_setup" not in killer_functions:
        errors.append("Killer missing 'opportunity_setup' memory seed")
    if "false_alibi_reason" not in killer_functions:
        errors.append("Killer missing 'false_alibi_reason' memory seed")

    # 12. Suspect timeline coverage — every interviewable suspect should appear
    # in at least one event, or their rewind is empty. A soft warning (not an
    # error): the timeline compiler already guarantees this for generated
    # cases, so this is a diagnostic safety net rather than a gate.
    agents_in_events = {aid for e in case.events for aid in e.agent_ids}
    for pack in case.interview_packs:
        if pack.agent_id not in agents_in_events and pack.agent_id != case.case.victim_id:
            warnings.append(f"Suspect {pack.agent_id} appears in no events (empty rewind)")

    # 13. The third act. Cases 002-006 all shipped with no way for the killer to break and no
    # epilogues, so a player who solved the case correctly was met with a shrug and a blank
    # reveal screen. Both are engine-supported (challenge.py resolves `contradiction_locked`;
    # judge.py renders `solution.epilogues`) — they were simply never authored.
    killer_confessions = [
        ch for ch in case.challenge_rules
        if ch.target_agent_id == killer and ch.outcome == "contradiction_locked"
    ]
    if not killer_confessions:
        errors.append(
            f"Killer {killer} has no 'contradiction_locked' challenge — there is no way for the "
            "player to break them, so the case has no climax."
        )
    if not case.solution.epilogues:
        errors.append(
            "Solution has no epilogues — the post-accusation reveal screen will be empty."
        )

    # 13b. Testimony as evidence. A claim can only be used to break another person's story if it
    # says WHOSE whereabouts it settles (`about_agent_id`). Claims that name nobody are inert —
    # so a case where no claim is annotated has the mechanic the game is named after switched off.
    agent_ids = {a.agent_id for a in case.agents}
    annotated = 0
    for pack in case.interview_packs:
        for rule in pack.rules:
            for c in rule.claims:
                if not c.about_agent_id:
                    continue
                annotated += 1
                # An alibi claim about someone OTHER than the speaker is not a mistake — it is a
                # witness vouching for them (Nadia putting Isabella in the clinic, Col putting
                # Owen in the yard). Corroboration is a first-class move; only a dangling
                # reference is an error.
                if c.about_agent_id not in agent_ids:
                    errors.append(
                        f"Claim {c.claim_id} is about unknown agent '{c.about_agent_id}'"
                    )
    if annotated == 0:
        warnings.append(
            "No claim carries about_agent_id — no testimony can contradict any other, so one "
            "person's word can never be used against another's."
        )

    # 14. routine_summary is player-visible (projections.project_agent) and shown on the Suspects
    # screen before any clue is discovered. It must never carry case truth.
    for agent in case.agents:
        leaks = [p for p in ROUTINE_LEAK_PATTERNS if re.search(p, agent.routine_summary or "", re.I)]
        if leaks:
            errors.append(
                f"Agent {agent.agent_id} routine_summary leaks case truth to the Suspects screen "
                f"(matched {leaks}): {agent.routine_summary!r}"
            )

    # 15. Layer 7's combination-leak danger table (ENGINE_SPEC §9.1). This is the
    # "case-build time" the spec puts the O(n^2) pass at — validation is already
    # the one place every case, hand-authored or generated, has to pass through.
    # Computing it here also means an authoring change that creates a new
    # dangerous pair shows up in the same report as every other fairness check.
    from .danger_table import build_danger_table, pair_key

    danger = build_danger_table(case)
    info.append(f"Danger table: {len(danger)} dangerous claim pair(s).")

    # A pair is "dangerous" because saying both things spells out a solution
    # facet in the same vocabulary judge.py grades an accusation with. Layer 7
    # is stopped from assembling one; an authored rule that hands the player
    # both halves in a single breath is not a leak (the deterministic answer is
    # ground truth and may say what it says) but it does give the motive away
    # for one question, which is a difficulty problem worth seeing.
    for pack in case.interview_packs:
        for rule in pack.rules:
            ids = sorted({c.claim_id for c in rule.claims})
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    facet = danger.get(pair_key(a, b))
                    if facet:
                        warnings.append(
                            f"{pack.agent_id}: one answer makes both claims {a} and {b}, which "
                            f"together give away {facet} in a single turn."
                        )

    score = 1.0 - (len(warnings) * 0.1) - (len(errors) * 0.5)
    score = max(0.0, score)

    return {
        "case_id": case.case.case_id,
        "valid": len(errors) == 0,
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "info": info,
    }
