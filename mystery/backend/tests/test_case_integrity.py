"""Fairness-validator-style checks for the hand-authored case (spec 09).

These run against the locked case data and fail if the mystery is
unsolvable, leaky, or internally inconsistent.
"""

import pytest

from app.store import load_case, minutes


@pytest.fixture(scope="module")
def case():
    return load_case("case_001")


def test_case_loads(case):
    assert case.case.status == "locked"
    assert case.case.killer_id != case.case.victim_id


def test_murder_event_is_hidden(case):
    murders = [e for e in case.events if e.event_type == "murder"]
    assert len(murders) == 1
    assert murders[0].visibility == "hidden"
    assert murders[0].time == case.case.time_of_death


def test_referential_integrity(case):
    agent_ids = {a.agent_id for a in case.agents}
    location_ids = {l.location_id for l in case.locations}
    object_ids = {o.object_id for o in case.objects}
    clue_ids = {c.clue_id for c in case.clues}
    event_ids = {e.event_id for e in case.events}

    for e in case.events:
        assert e.location_id in location_ids, e.event_id
        assert set(e.agent_ids) <= agent_ids, e.event_id
        assert set(e.object_ids) <= object_ids, e.event_id
        assert set(e.linked_clue_ids) <= clue_ids, e.event_id
    for c in case.clues:
        assert set(c.linked_event_ids) <= event_ids, c.clue_id
        assert set(c.linked_agent_ids) <= agent_ids, c.clue_id
        assert set(c.linked_location_ids) <= location_ids, c.clue_id
        assert set(c.linked_object_ids) <= object_ids, c.clue_id
        assert set(c.discoverability.required_prior_clue_ids) <= clue_ids, c.clue_id
    for conc in case.conclusions:
        assert set(conc.supported_by_clue_ids) <= clue_ids, conc.conclusion_id
    for m in case.memories:
        assert m.owner_agent_id in agent_ids, m.memory_id
        assert set(m.linked_clue_ids) <= clue_ids, m.memory_id


def test_three_clue_rule_for_required_conclusions(case):
    for conc in case.conclusions:
        if conc.required_for_solution:
            assert len(conc.supported_by_clue_ids) >= 3, (
                f"{conc.conclusion_id} has only {len(conc.supported_by_clue_ids)} clues"
            )


def test_every_clue_has_valid_discovery_path(case):
    location_ids = {l.location_id for l in case.locations}
    pack_by_agent = {p.agent_id: p for p in case.interview_packs}
    visible_event_ids = {
        e.event_id
        for e in case.events
        if e.visibility == "public" or (e.visibility == "public_partial" and e.player_description)
    }

    for clue in case.clues:
        d = clue.discoverability
        if d.method == "inspect":
            assert d.location_id in location_ids, clue.clue_id
        elif d.method == "interview":
            pack = pack_by_agent.get(d.agent_id)
            assert pack is not None, clue.clue_id
            revealing = [r for r in pack.rules if clue.clue_id in r.reveals_clue_ids]
            assert revealing, f"{clue.clue_id}: no interview rule reveals it"
        elif d.method == "observation":
            assert set(clue.linked_event_ids) & visible_event_ids, (
                f"{clue.clue_id}: observation clue has no visible linked event"
            )


def test_no_prerequisite_cycles(case):
    graph = {
        c.clue_id: set(c.discoverability.required_prior_clue_ids) for c in case.clues
    }
    resolved: set[str] = set()
    for _ in range(len(graph) + 1):
        for clue_id, prereqs in graph.items():
            if clue_id not in resolved and prereqs <= resolved:
                resolved.add(clue_id)
    assert resolved == set(graph), f"Unresolvable clues: {set(graph) - resolved}"


def test_killer_has_motive_means_opportunity(case):
    killer = case.case.killer_id
    types_for_killer = {
        conc.type
        for conc in case.conclusions
        if conc.target_agent_id == killer and conc.required_for_solution
    }
    assert {"motive", "opportunity", "means", "false_alibi"} <= types_for_killer


def test_at_least_two_red_herrings_with_anchors(case):
    herrings = [c for c in case.conclusions if c.type == "red_herring"]
    anchors = {
        c.target_agent_id for c in case.conclusions if c.type == "innocence_anchor"
    }
    assert len(herrings) >= 2
    for h in herrings:
        assert h.target_agent_id in anchors, f"{h.target_agent_id} has no innocence anchor"


def test_no_agent_in_two_places_at_once(case):
    seen: dict[tuple[str, str], str] = {}
    for e in case.events:
        for agent_id in e.agent_ids:
            key = (agent_id, e.time)
            if key in seen:
                assert seen[key] == e.location_id, (
                    f"{agent_id} at {e.time} in both {seen[key]} and {e.location_id}"
                )
            seen[key] = e.location_id


def test_timeline_order(case):
    c = case.case
    assert minutes(c.sim_start_time) < minutes(c.murder_window[0])
    assert minutes(c.murder_window[0]) <= minutes(c.time_of_death) <= minutes(c.murder_window[1])
    assert minutes(c.time_of_death) < minutes(c.discovery_time)


def test_killer_seed_requirements(case):
    """Killer needs motive, escalation, opportunity and cover-story seeds (spec 03)."""
    killer_functions = {
        m.case_function for m in case.memories if m.owner_agent_id == case.case.killer_id
    }
    assert "killer_motive" in killer_functions
    assert "opportunity_setup" in killer_functions
    assert "false_alibi_reason" in killer_functions
