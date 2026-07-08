"""Guards the background-NPC invariants documented in CLAUDE.md: they must
never be routed through the murder scene or a clue-bearing moment, they must
never collide with themselves, and every case source (hand-authored,
deterministic generator, llm_assisted generator) should end up with them."""

import random

from app.background_npcs import MAX_BACKGROUND_NPCS, _to_min, _unsafe_locations, add_background_npcs
from app.case_store import list_all_cases, load_case_from_disk
from app.generator import generate_case
from app.validator import validate_case

STATIC_CASE_IDS = [c["case_id"] for c in list_all_cases() if c["case_id"].startswith("case_")]


def test_static_cases_have_background_npcs():
    assert STATIC_CASE_IDS, "expected at least one hand-authored case"
    for case_id in STATIC_CASE_IDS:
        case = load_case_from_disk(case_id)
        bg = [a for a in case.agents if a.is_background]
        assert bg, f"{case_id} has no background NPCs"
        assert len(bg) <= MAX_BACKGROUND_NPCS


def test_background_npcs_never_leak_into_the_murder_window():
    for case_id in STATIC_CASE_IDS:
        case = load_case_from_disk(case_id)
        unsafe = _unsafe_locations(case)
        window_start = _to_min(case.case.murder_window[0])
        window_end = _to_min(case.case.murder_window[1])
        for e in case.events:
            agent = next((a for a in case.agents if a.agent_id in e.agent_ids and a.is_background), None)
            if agent is None:
                continue
            assert e.location_id not in unsafe, (
                f"{case_id}: background NPC {agent.full_name} routed through unsafe "
                f"location {e.location_id} via {e.event_id}"
            )
            t = _to_min(e.time)
            assert not (window_start <= t <= window_end and e.location_id == case.case.murder_location_id)


def test_background_npcs_never_collide_with_themselves():
    for case_id in STATIC_CASE_IDS:
        case = load_case_from_disk(case_id)
        seen: dict[tuple[str, str], str] = {}
        for e in case.events:
            for aid in e.agent_ids:
                key = (aid, e.time)
                if key in seen:
                    assert seen[key] == e.location_id, f"{case_id}: agent {aid} bilocated at {e.time}"
                seen[key] = e.location_id


def test_static_cases_still_validate_with_background_npcs():
    for case_id in STATIC_CASE_IDS:
        case = load_case_from_disk(case_id)
        result = validate_case(case)
        # Background NPCs must never be the source of a validation error.
        assert not any("agent_bg_" in err for err in result["errors"])


def test_add_background_npcs_is_a_noop_with_no_safe_locations(monkeypatch):
    case = load_case_from_disk("case_001")
    monkeypatch.setattr("app.background_npcs._safe_locations", lambda c: [])
    added = add_background_npcs(case, random.Random(1))
    assert added == []


def test_generated_cases_get_background_npcs():
    for mode in ("deterministic", "llm_assisted"):
        case, _fallback, _reason, _attempts = generate_case("blackmail", "standard", seed=123, mode=mode)
        bg = [a for a in case.agents if a.is_background]
        assert bg, f"{mode} generated case has no background NPCs"
        result = validate_case(case)
        assert result["valid"], result["errors"]
        living_suspects = [a.agent_id for a in case.agents if not a.is_victim and not a.is_background]
        assert case.metadata["num_suspects"] == len(living_suspects)
