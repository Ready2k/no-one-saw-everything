"""Testimony as evidence: when can one person's word disprove another's?

The game's premise is that no one saw everything — every villager holds a fragment, and the truth
is only visible when the fragments are laid against each other. But until now a claim could only
be broken by a physical clue. The player could find the blue coat, but could never say to Clara:
*"Elias sat facing that fountain all morning and never saw you there."*

Claims already carry the structure needed to settle this deterministically — a time, a location,
and (now) who they place and whether they place them there at all:

    claim_clara_fountain     speaker=clara  about=clara  loc=fountain  07:50  presence
    claim_elias_no_fountain  speaker=elias  about=clara  loc=fountain  07:50  ABSENCE

Two statements about the same person at the same time cannot both be true if one puts them
somewhere and the other puts them somewhere else, or insists they were not there at all.

This is deliberately CONSERVATIVE: it reports a conflict only when the structured fields make one
unavoidable. It never guesses from prose. A witness who saw "someone in a blue coat" is not
making a claim *about Clara* — connecting the coat to the woman is the player's job, and stays
the player's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .case_store import minutes
from .models import Claim

# Claims are INTERVALS. Most are a single minute; an alibi is a span ("I was home all evening"),
# and `time_to` says so. Two statements clash only if their intervals meet.
#
# The tolerance absorbs the coarseness of point claims ("about a quarter to eight") and nothing
# more. It must stay small: at 15 minutes this rule reported that Clara being in the cafe at
# 07:40 and at the fountain at 07:50 was a contradiction. It is not — she walked. A detector that
# cries wolf is worse than no detector, because the player stops believing it.
BILOCATION_TOLERANCE_MINUTES = 2

# A denial is different: a witness who sat facing the fountain all morning is speaking about a
# stretch of time, so their word bites across a wider window.
DENIAL_WINDOW_MINUTES = 20


@dataclass(frozen=True)
class TestimonyConflict:
    kind: str  # "bilocation" | "denial" | "self_contradiction"
    subject_agent_id: str
    explanation: str


def _subject(claim: Claim) -> Optional[str]:
    """Whose whereabouts this claim pins down — and None unless it says so explicitly.

    Defaulting this to the speaker was wrong, and produced exactly the false positive this whole
    module must avoid: a witness statement carries the location of the thing OBSERVED, not of the
    observer, so "Elias says Isabella arrived at the bookshop at 12:32" looked like a claim that
    *Elias* was at the bookshop — and Elias appeared to contradict himself.

    Silence therefore means "this statement does not place anybody". A claim only enters the
    contradiction machinery when an author has said whose movements it settles.
    """
    return claim.about_agent_id


def _interval(claim: Claim) -> Optional[tuple[int, int]]:
    """The stretch of time a claim covers. A point claim is a one-minute interval."""
    if not claim.time_reference:
        return None
    try:
        start = minutes(claim.time_reference)
        end = minutes(claim.time_to) if claim.time_to else start
    except Exception:
        return None
    return (start, end) if end >= start else (end, start)


def _gap_minutes(a: Claim, b: Claim) -> Optional[int]:
    """Minutes between two claims' intervals — 0 when they overlap."""
    ia, ib = _interval(a), _interval(b)
    if ia is None or ib is None:
        return None
    if ia[0] <= ib[1] and ib[0] <= ia[1]:
        return 0
    return ib[0] - ia[1] if ib[0] > ia[1] else ia[0] - ib[1]


def find_conflict(challenged: Claim, evidence: Claim) -> Optional[TestimonyConflict]:
    """Does `evidence` make `challenged` impossible? None if the two can both be true.

    Both must place the SAME person, at the SAME time, somewhere. Then:

      * different places          -> they cannot both be true (bilocation)
      * same place, one a denial  -> they cannot both be true (denial)

    Anything else — a different person, a different hour, a claim with no location, two claims
    that simply sit side by side — is not a contradiction, and saying so would be lying to the
    player.
    """
    if challenged.claim_id == evidence.claim_id:
        return None

    subject = _subject(challenged)
    if subject is None or subject != _subject(evidence):
        return None
    if not (challenged.location_reference_id and evidence.location_reference_id):
        return None

    gap = _gap_minutes(challenged, evidence)
    if gap is None:
        return None

    same_place = challenged.location_reference_id == evidence.location_reference_id
    self_contradiction = challenged.speaker_agent_id == evidence.speaker_agent_id

    if same_place:
        if challenged.asserts_presence == evidence.asserts_presence:
            return None  # they agree
        if gap > DENIAL_WINDOW_MINUTES:
            return None
        return TestimonyConflict(
            kind="denial",
            subject_agent_id=subject,
            explanation=(
                f"{evidence.claim_text} That cannot be true at the same time as: "
                f"{challenged.claim_text}"
            ),
        )

    # Different places. Only impossible if BOTH statements actually put them somewhere ("I wasn't
    # in the alley" and "I was at the fountain" agree perfectly), and only if they are about the
    # same moment — ten minutes apart in a village is a walk, not a contradiction.
    if not (challenged.asserts_presence and evidence.asserts_presence):
        return None
    if gap > BILOCATION_TOLERANCE_MINUTES:
        return None

    return TestimonyConflict(
        kind="self_contradiction" if self_contradiction else "bilocation",
        subject_agent_id=subject,
        explanation=(
            f"{challenged.claim_text} — but {evidence.claim_text} "
            f"Nobody is in two places at once."
        ),
    )


def find_tension(a: Claim, b: Claim, *, max_gap_minutes: int = 30) -> Optional[int]:
    """The minute gap between two of the SAME person's claims at two
    DIFFERENT locations, when that gap is tight enough to be worth a
    detective remarking on it — without being a genuine impossibility.

    Deliberately narrow (a sibling of `find_conflict`, not a replacement):
    both claims must place the same person, must be at different places,
    and must NOT already constitute a testimony conflict — a real
    contradiction is `find_conflict`'s job, and it is the more serious of
    the two. This only covers the remaining case where both statements can
    be true and the player has done the work of citing both times back at
    the suspect: "you argued with him at 07:05, and by 07:15 you were in
    your yard — that's a tight ten minutes, isn't it?" A gap of zero (they
    overlap) or a gap wider than `max_gap_minutes` isn't tension, it's
    either impossible (find_conflict's job) or unremarkable.
    """
    if a.claim_id == b.claim_id:
        return None
    subject = _subject(a)
    if subject is None or subject != _subject(b):
        return None
    if not (a.location_reference_id and b.location_reference_id):
        return None
    if a.location_reference_id == b.location_reference_id:
        return None
    if not (a.asserts_presence and b.asserts_presence):
        return None
    if find_conflict(a, b) is not None:
        return None
    gap = _gap_minutes(a, b)
    if gap is None or gap == 0 or gap > max_gap_minutes:
        return None
    return gap


def conflicts_for(challenged: Claim, pool: list[Claim]) -> list[tuple[Claim, TestimonyConflict]]:
    out = []
    for other in pool:
        c = find_conflict(challenged, other)
        if c:
            out.append((other, c))
    return out
