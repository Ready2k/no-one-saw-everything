"""Confronting a suspect with MORE/BETTER evidence must never produce a WEAKER response.

Challenge rules match on overlapping evidence (match_mode "any"), so several rules can match the
same confrontation. `_find_rule` used to return the first match in file order, which meant the
`contradiction_locked` confession — appended to the end of challenges.json — was shadowed by an
earlier one-clue `deflect`/`partial_admission` rule. Every confession in cases 002-006 was
authored, wired, reachable on paper, and dead in play.
"""

import pytest

from app.case_store import load_case_from_disk as load_case
from app.challenge import _find_rule
from app.models import ChallengeRequest
from app.session import Session

CASE_IDS = ["case_001", "case_002", "case_003", "case_004", "case_005", "case_006", "case_007"]


def _session_with_all_clues(case) -> Session:
    s = Session(case_id=case.case.case_id)
    s.discovered_clue_ids = {c.clue_id for c in case.clues}
    return s


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_confession_is_not_shadowed_by_a_weaker_rule(case_id):
    """The killer's confession must actually fire when its evidence is supplied."""
    case = load_case(case_id)
    killer = case.case.killer_id
    session = _session_with_all_clues(case)

    confessions = [
        r for r in case.challenge_rules
        if r.target_agent_id == killer and r.outcome == "contradiction_locked"
    ]
    assert confessions, f"{case_id}: killer has no confession to fire"

    for rule in confessions:
        req = ChallengeRequest(
            target_agent_id=killer,
            challenged_claim_id=rule.challenged_claim_id,
            evidence_clue_ids=list(rule.evidence_clue_ids),
        )
        chosen = _find_rule(case, session, req)
        assert chosen is not None, f"{case_id}: no rule matched {rule.challenged_claim_id}"
        assert chosen.outcome == "contradiction_locked", (
            f"{case_id}: confronting the killer with {rule.evidence_clue_ids} on "
            f"'{rule.challenged_claim_id}' resolved to '{chosen.outcome}' — the confession is "
            f"being shadowed by a weaker rule."
        )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_adding_evidence_never_weakens_the_outcome(case_id):
    """Supplying a confession's evidence PLUS extra clues must still confess."""
    from app.challenge import _OUTCOME_SEVERITY

    case = load_case(case_id)
    killer = case.case.killer_id
    session = _session_with_all_clues(case)
    extra = [c.clue_id for c in case.clues][:3]

    for rule in case.challenge_rules:
        if rule.target_agent_id != killer or rule.outcome != "contradiction_locked":
            continue
        req = ChallengeRequest(
            target_agent_id=killer,
            challenged_claim_id=rule.challenged_claim_id,
            evidence_clue_ids=list(dict.fromkeys(list(rule.evidence_clue_ids) + extra)),
        )
        chosen = _find_rule(case, session, req)
        assert _OUTCOME_SEVERITY[chosen.outcome] >= _OUTCOME_SEVERITY["contradiction_locked"], (
            f"{case_id}: piling on extra evidence downgraded the confession to "
            f"'{chosen.outcome}'."
        )
