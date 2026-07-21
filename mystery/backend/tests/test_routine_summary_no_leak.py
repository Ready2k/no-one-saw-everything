"""Agent.routine_summary is player-visible (projections.project_agent) and is shown on the
Suspects screen before any clue is discovered. It must therefore describe an ORDINARY day
and never carry case truth.

This guards a real regression: cases 004, 005 and 006 shipped with routine_summary fields
that stated the killer's motive, named the false alibi as false, and gave away the case 006
identity twist — all readable from GET /api/agents with zero clues discovered.

A routine_summary must not contain:
  * authorial scaffolding ("will need to be dismantled", "will matter", "will have seen")
  * an assertion that someone lied / has a false alibi
  * what the agent did *on the night of the murder* ("that night ...")
  * the murder method, or the solution's motive
"""

import re

import pytest

from app.case_store import load_case_from_disk as load_case

CASE_IDS = ["case_001", "case_002", "case_003", "case_004", "case_005", "case_006", "case_007"]

# Author-facing scaffolding, or naked statements of hidden truth.
FORBIDDEN_PATTERNS = [
    r"\bwill need to be\b",
    r"\bwill matter\b",
    r"\bwill have seen\b",
    r"\bwill recognise\b",
    r"\bwill be (?:revealed|discovered|proven)\b",
    r"\bforged alibi\b",
    r"\bfalse alibi\b",
    r"\b(?:he|she|they) lied\b",
    r"\blying about\b",
    r"\bsecretly (?:owed|killed|poisoned|followed)\b",
    r"\bthe killer\b",
    r"\bthe murderer\b",
    r"\bcommitted the murder\b",
    r"\bif anyone asked\b",          # "asked him to say he was at the yard if anyone asked"
    r"\bto say he was\b",
    r"\basked him to lie\b",
    # "that night ..." — a routine is what happens on an ordinary day, not on the murder night.
    r"\bthat night\b",
]


# A routine may legitimately involve another villager ("checks in on Elias most afternoons").
# What it may never do is reveal that agent's *secret* — which in practice always reads as an
# epistemic/complicity verb attached to another suspect's name. This is the shape of the
# case_006 leak: "Dimly recalls Ruth's maiden name was Bell before she married."
SECRET_VERBS = [
    "recalls", "remembers", "knows that", "found out", "discovered",
    "asked him", "asked her", "told him to", "told her to",
    "owed", "owes", "protecting", "protect", "cover for", "covering for",
    "maiden name", "really is", "actually is",
]


def _routine_offences(text: str) -> list[str]:
    return [p for p in FORBIDDEN_PATTERNS if re.search(p, text, re.IGNORECASE)]


def _names_another_suspect_secret(text: str, self_id: str, suspects: dict[str, str]) -> list[str]:
    """Flag a routine that names ANOTHER suspect alongside a secret-bearing verb."""
    lowered = text.lower()
    if not any(v in lowered for v in SECRET_VERBS):
        return []
    return [
        first_name
        for agent_id, first_name in suspects.items()
        if agent_id != self_id and re.search(rf"\b{re.escape(first_name.lower())}\b", lowered)
    ]


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_routine_summary_has_no_authorial_or_truth_leak(case_id):
    case = load_case(case_id)
    offences = []
    for agent in case.agents:
        hits = _routine_offences(agent.routine_summary or "")
        if hits:
            offences.append(f"{agent.agent_id}: {agent.routine_summary!r} matched {hits}")
    assert not offences, (
        f"{case_id}: routine_summary is shown to the player before any clue is discovered "
        f"and must not carry case truth or author notes:\n  " + "\n  ".join(offences)
    )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_routine_summary_does_not_reveal_another_suspects_secret(case_id):
    case = load_case(case_id)
    suspects = {
        a.agent_id: a.full_name.split()[0]
        for a in case.agents
        if not a.is_background
    }
    offences = []
    for agent in case.agents:
        if agent.is_background:
            continue
        named = _names_another_suspect_secret(
            agent.routine_summary or "", agent.agent_id, suspects
        )
        if named:
            offences.append(
                f"{agent.agent_id}: {agent.routine_summary!r} reveals a secret about {named}"
            )
    assert not offences, (
        f"{case_id}: a routine_summary may involve another villager, but must not disclose "
        f"their secret — it is on the Suspects screen before any clue is found:\n  "
        + "\n  ".join(offences)
    )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_routine_summary_does_not_name_the_killer_motive(case_id):
    """The solution's motive keywords must not be readable off the Suspects screen.

    We check the killer's own routine_summary against their motive concept groups: if a
    routine hits two or more distinct motive concept groups, the player can infer the motive
    without investigating (this is exactly how case 004 leaked "found his father's papers").
    """
    case = load_case(case_id)
    killer_id = case.case.killer_id
    killer = next(a for a in case.agents if a.agent_id == killer_id)
    routine = (killer.routine_summary or "").lower()

    hit_groups = [
        group
        for group in case.solution.motive.concept_groups
        if any(term.lower() in routine for term in group)
    ]
    assert len(hit_groups) < 2, (
        f"{case_id}: killer {killer_id}'s routine_summary {killer.routine_summary!r} matches "
        f"{len(hit_groups)} motive concept groups — the motive is legible before play."
    )
