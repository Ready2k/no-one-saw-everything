"""Every authored interview rule must be capable of firing.

`interview._match_rule` silently SKIPS:
  * an `evidence` rule with neither topic_clue_id nor topic_object_id
  * a `location` rule whose topic_location_id does not match the asked location

Fourteen authored rules across four cases were unreachable — including the clue that was supposed
to close case_003's "you cannot prove I put those capsules there" gap, and most of case_005's
interrogation. They were valid data, they passed every other check, and no player could ever have
seen them. Dead dialogue is worse than missing dialogue: it looks finished.
"""

import pytest

from app.case_store import load_case_from_disk as load_case

CASE_IDS = ["case_001", "case_002", "case_003", "case_004", "case_005", "case_006", "case_007"]


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_interview_rule_can_fire(case_id):
    case = load_case(case_id)
    dead = []
    for pack in case.interview_packs:
        for i, rule in enumerate(pack.rules):
            if rule.question_type == "evidence" and not (rule.topic_clue_id or rule.topic_object_id):
                dead.append(
                    f"{pack.agent_id} rule[{i}] (evidence): no topic_clue_id/topic_object_id — "
                    f"_match_rule skips it, so this answer can never be reached"
                )
            if rule.question_type == "location" and not rule.topic_location_id:
                dead.append(
                    f"{pack.agent_id} rule[{i}] (location): no topic_location_id — "
                    f"it can only match a request with no location, which the UI never sends"
                )
    assert not dead, f"{case_id}: unreachable interview rules:\n  " + "\n  ".join(dead)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_interview_rule_topics_reference_real_things(case_id):
    case = load_case(case_id)
    clue_ids = {c.clue_id for c in case.clues}
    object_ids = {o.object_id for o in case.objects}
    location_ids = {l.location_id for l in case.locations}
    bad = []
    for pack in case.interview_packs:
        for i, rule in enumerate(pack.rules):
            if rule.topic_clue_id and rule.topic_clue_id not in clue_ids:
                bad.append(f"{pack.agent_id} rule[{i}]: unknown topic_clue_id {rule.topic_clue_id}")
            if rule.topic_object_id and rule.topic_object_id not in object_ids:
                bad.append(f"{pack.agent_id} rule[{i}]: unknown topic_object_id {rule.topic_object_id}")
            if rule.topic_location_id and rule.topic_location_id not in location_ids:
                bad.append(f"{pack.agent_id} rule[{i}]: unknown topic_location_id {rule.topic_location_id}")
            for cid in rule.reveals_clue_ids:
                if cid not in clue_ids:
                    bad.append(f"{pack.agent_id} rule[{i}]: reveals unknown clue {cid}")
    assert not bad, f"{case_id}:\n  " + "\n  ".join(bad)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_clue_marked_interview_is_revealed_by_a_reachable_rule(case_id):
    """An interview-discoverable clue that no *reachable* rule reveals is unobtainable."""
    case = load_case(case_id)
    revealed = set()
    for pack in case.interview_packs:
        for rule in pack.rules:
            reachable = not (
                (rule.question_type == "evidence" and not (rule.topic_clue_id or rule.topic_object_id))
                or (rule.question_type == "location" and not rule.topic_location_id)
            )
            if reachable:
                revealed.update(rule.reveals_clue_ids)

    missing = [
        c.clue_id
        for c in case.clues
        if c.discoverability.method == "interview" and c.clue_id not in revealed
    ]
    assert not missing, (
        f"{case_id}: interview clues that no reachable rule reveals: {missing}"
    )
