"""Challenge engine (Phase 5).

Deterministic and grounded: the player confronts a sim with a claim they
made and evidence that (they think) contradicts it. Outcomes come from
hand-authored ChallengeRules on the locked case; anything unscripted falls
back to a graceful, truth-preserving denial.

Like the interview engine, this implements the spec-06 challenge contract so
an LLM challenge resolver can later be plugged in behind `resolve_challenge`
without touching the API or the frontend.
"""

from __future__ import annotations

from typing import Optional

from .models import (
    CaseData,
    ChallengeRecord,
    ChallengeRequest,
    ChallengeRule,
    Claim,
    InterviewMessage,
)
from .projections import project_claim, project_clue
from .session import Session
from .llm.config import get_llm_config
from .llm.dialogue_rewriter import rewrite_challenge_response
from .world_state import build_world_state_digest


class ChallengeError(Exception):
    """Raised for invalid challenges (mapped to HTTP 400/404 in main.py)."""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(case: CaseData, session: Session, req: ChallengeRequest) -> Claim:
    agent = next((a for a in case.agents if a.agent_id == req.target_agent_id), None)
    if agent is None:
        raise ChallengeError(404, "No such agent.")
    if agent.is_victim or agent.agent_id == case.case.victim_id:
        raise ChallengeError(400, "You cannot challenge the victim.")
    if not any(p.agent_id == agent.agent_id for p in case.interview_packs):
        raise ChallengeError(400, "That person is not available for questioning.")

    claim = session.claims.get(req.challenged_claim_id)
    if claim is None:
        raise ChallengeError(404, "You have not heard that claim yet.")
    if claim.speaker_agent_id != req.target_agent_id:
        raise ChallengeError(400, "That claim was not made by this person.")

    if not req.evidence_clue_ids and not req.evidence_claim_ids:
        raise ChallengeError(400, "A challenge needs at least one piece of evidence.")
    for clue_id in req.evidence_clue_ids:
        if not any(c.clue_id == clue_id for c in case.clues):
            raise ChallengeError(404, f"No such clue: {clue_id}")
        if clue_id not in session.discovered_clue_ids:
            raise ChallengeError(400, "You can only challenge with evidence you have discovered.")

    # Testimony is evidence too, but only testimony the player has actually heard — you cannot
    # quote a statement nobody has made to you, and you cannot quote a person against themselves
    # by re-reading the very claim you are challenging.
    for claim_id in req.evidence_claim_ids:
        if claim_id not in session.claims:
            raise ChallengeError(404, "You have not heard that statement yet.")
        if claim_id == req.challenged_claim_id:
            raise ChallengeError(400, "That is the statement you are challenging.")
    return claim


# ---------------------------------------------------------------------------
# Rule matching
# ---------------------------------------------------------------------------

def _rule_matches(rule: ChallengeRule, session: Session, req: ChallengeRequest) -> bool:
    if rule.target_agent_id != req.target_agent_id:
        return False
    if rule.challenged_claim_id != req.challenged_claim_id:
        return False
    for prior in rule.required_prior_clue_ids:
        if prior not in session.discovered_clue_ids:
            return False

    # A rule may be triggered by clues, by testimony, or by both.
    supplied = set(req.evidence_clue_ids) | set(req.evidence_claim_ids)
    trigger = set(rule.evidence_clue_ids) | set(rule.evidence_claim_ids)
    if not trigger:
        return False
    if rule.match_mode == "all":
        return trigger <= supplied
    return bool(trigger & supplied)


# How decisive each scripted outcome is. Used to break ties when several rules match the same
# confrontation: bringing the decisive evidence must never produce a weaker response than
# bringing a fragment of it.
_OUTCOME_SEVERITY = {
    "contradiction_locked": 4,
    "partial_admission": 3,
    "reveal_innocent_secret": 2,
    "reframe": 1,
    "deflect": 0,
}


def _find_rule(case: CaseData, session: Session, req: ChallengeRequest) -> Optional[ChallengeRule]:
    """Pick the BEST matching rule, not merely the first one in file order.

    Rules match on *overlapping* evidence (match_mode "any"), so a one-clue `deflect` rule and
    the multi-clue `contradiction_locked` confession can both match the same confrontation. If
    we returned the first match, a player who correctly assembled the killing evidence would be
    fobbed off with a deflection authored for a single weak clue — which is exactly what
    happened to every confession added to cases 002-006 (they sat at the end of challenges.json
    and were shadowed by earlier, laxer rules).

    Rank by:
      1. whether the player supplied the rule's *entire* trigger — a fully-evidenced rule is a
         better fit than one that merely brushes against the evidence on offer;
      2. how decisive the outcome is — among fully-evidenced rules, the killer breaks;
      3. how much of the trigger overlapped, then file order, as stable tie-breaks.
    """
    supplied = set(req.evidence_clue_ids) | set(req.evidence_claim_ids)
    matches = [r for r in case.challenge_rules if _rule_matches(r, session, req)]
    if not matches:
        return None
    return max(
        matches,
        key=lambda r: (
            (set(r.evidence_clue_ids) | set(r.evidence_claim_ids)) <= supplied,
            _OUTCOME_SEVERITY.get(r.outcome, 0),
            len((set(r.evidence_clue_ids) | set(r.evidence_claim_ids)) & supplied),
            -case.challenge_rules.index(r),
        ),
    )


def _evidence_is_related(case: CaseData, claim: Claim, evidence_clue_ids: list[str]) -> bool:
    """A deterministic 'is this even relevant' check for unscripted challenges,
    so we can tell 'you're onto something' apart from a non-sequitur."""
    for clue_id in evidence_clue_ids:
        clue = next((c for c in case.clues if c.clue_id == clue_id), None)
        if clue is None:
            continue
        if claim.location_reference_id and claim.location_reference_id in clue.linked_location_ids:
            return True
        if claim.speaker_agent_id in clue.linked_agent_ids:
            return True
    return False


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve_challenge(case: CaseData, session: Session, req: ChallengeRequest) -> ChallengeRecord:
    claim = _validate(case, session, req)

    # De-duplicate: same claim + same evidence set returns the prior record.
    dedup_key = (
        req.challenged_claim_id,
        frozenset(req.evidence_clue_ids) | frozenset(req.evidence_claim_ids),
    )
    if dedup_key in session.challenge_index:
        prior = session.challenges[session.challenge_index[dedup_key]]
        return prior.model_copy(update={"duplicate": True})

    rule = _find_rule(case, session, req)
    if rule is None:
        record = _resolve_unscripted(case, session, req, claim)
    else:
        record = _apply_rule(case, session, req, claim, rule)

    config = get_llm_config()
    if config.dialogue_enabled:
        allowed_facts = [session.claims[cid].claim_text for cid in record.new_claim_ids]
        allowed_facts += [c.title for c in case.clues if c.clue_id in record.revealed_clue_ids]
        agent = next(a for a in case.agents if a.agent_id == req.target_agent_id)
        pressure = session.pressure_for(req.target_agent_id)
        evidence_clues = ", ".join(c.title for c in case.clues if c.clue_id in req.evidence_clue_ids)
        
        rewrite_result = rewrite_challenge_response(
            case=case,
            agent=agent,
            challenged_claim=claim.claim_text,
            evidence_clues=evidence_clues,
            player_statement=req.player_statement or "",
            outcome=record.outcome,
            deterministic_text=record.deterministic_response_text,
            allowed_facts=allowed_facts,
            pressure_level=pressure,
            emotion=record.emotional_shift or "neutral",
            world_state=build_world_state_digest(case, session, req.target_agent_id) or None,
        )
        record.display_response_text = rewrite_result.rewritten_text
        record.llm_rewrite_used = True
        record.llm_rewrite_fallback = rewrite_result.fallback_used
        record.llm_rewrite_fallback_reason = rewrite_result.fallback_reason

    session.challenges[record.challenge_id] = record
    session.challenge_index[dedup_key] = record.challenge_id
    _record_transcript(session, req, record)

    # Spec 15 Phase C: a resolved challenge is a belief-update trigger for
    # the challenged agent (and anyone tied to newly revealed clues).
    # Fire-and-forget; no-op unless the beliefs flag is on.
    from .llm.belief_updater import schedule_belief_updates

    affected = [req.target_agent_id] + [
        aid
        for c in case.clues
        if c.clue_id in record.revealed_clue_ids
        for aid in c.linked_agent_ids
    ]
    schedule_belief_updates(
        case,
        session,
        affected,
        "The detective just challenged a suspect's account with evidence; word travels fast in the village.",
    )
    return record


def _apply_rule(
    case: CaseData,
    session: Session,
    req: ChallengeRequest,
    claim: Claim,
    rule: ChallengeRule,
) -> ChallengeRecord:
    challenge_id = session.next_challenge_id()

    # New claims produced by the reaction.
    new_claim_ids: list[str] = []
    for nc in rule.new_claims:
        new_claim = Claim(
            claim_id=nc.claim_id,
            speaker_agent_id=req.target_agent_id,
            claim_text=nc.summary,
            claim_type=nc.claim_type,
            time_reference=nc.time_reference,
            location_reference_id=nc.location_reference_id,
            truthfulness=nc.truthfulness,
            # A claim wrung out under pressure is testimony like any other — Priya's admission
            # that she was in the alley is what makes her stockroom story impossible.
            about_agent_id=nc.about_agent_id,
            asserts_presence=nc.asserts_presence,
        )
        session.record_claim(new_claim)
        new_claim_ids.append(new_claim.claim_id)

    # Clue reveals (gated by discoverability prereqs already checked in the rule).
    revealed_clue_ids: list[str] = []
    for clue_id in rule.reveals_clue_ids:
        if any(c.clue_id == clue_id for c in case.clues) and clue_id not in session.discovered_clue_ids:
            session.discovered_clue_ids.add(clue_id)
            revealed_clue_ids.append(clue_id)

    # Memory reveals (only discoverable memories can ever surface).
    revealed_memory_ids: list[str] = []
    for mem_id in rule.reveals_memory_ids:
        mem = next((m for m in case.memories if m.memory_id == mem_id), None)
        if mem and mem.discoverable_by_player and mem_id not in session.revealed_memory_ids:
            session.revealed_memory_ids.add(mem_id)
            revealed_memory_ids.append(mem_id)

    # Update the challenged claim's status.
    if rule.sets_claim_status:
        claim.player_known_status = rule.sets_claim_status

    session.add_pressure(req.target_agent_id, rule.pressure_delta)

    # Auto-create a board note capturing the material outcome.
    created_note_ids = _auto_note(case, session, req, claim, rule, new_claim_ids, revealed_clue_ids)

    return ChallengeRecord(
        challenge_id=challenge_id,
        case_id=case.case.case_id,
        target_agent_id=req.target_agent_id,
        challenged_claim_id=req.challenged_claim_id,
        evidence_clue_ids=req.evidence_clue_ids,
        player_statement=req.player_statement,
        outcome=rule.outcome,
        deterministic_response_text=rule.response_text,
        display_response_text=rule.response_text,
        emotional_shift=rule.emotional_shift,
        new_claim_ids=new_claim_ids,
        revealed_memory_ids=revealed_memory_ids,
        revealed_clue_ids=revealed_clue_ids,
        pressure_delta=rule.pressure_delta,
        created_note_ids=created_note_ids,
    )


def _resolve_unscripted(
    case: CaseData, session: Session, req: ChallengeRequest, claim: Claim
) -> ChallengeRecord:
    """No authored reaction — but a real contradiction must still land.

    Testimony conflicts are settled deterministically from the claims' own structure (see
    testimony.find_conflict), so a player who puts Elias's word against Clara's gets a genuine
    result even where nobody authored that exact confrontation. The engine never invents facts:
    it only reports that two statements the player has *heard* cannot both be true.
    """
    from .testimony import find_conflict

    speaker_name = {a.agent_id: a.full_name.split()[0] for a in case.agents}

    # 1. Did the player put someone else's word against this one, and does it actually bite?
    for claim_id in req.evidence_claim_ids:
        other = session.claims[claim_id]
        conflict = find_conflict(claim, other)
        if conflict is None:
            continue

        witness = speaker_name.get(other.speaker_agent_id, "someone")
        if conflict.kind == "self_contradiction":
            response = (
                f"...I said that. I know I said that.\n\n"
                f"I don't— that's not— you're twisting two different things I've told you into "
                f"one thing I didn't."
            )
            emotion = "floundering"
            delta = 0.3
        else:
            # No pronouns: agents carry no gender, and guessing produced "Elias said that, did they."
            response = (
                f"So {witness} says.\n\n"
                f"Then {witness} is mistaken, or {witness} is lying, and I know which I'd put my "
                f"money on. I have told you where I was."
            )
            emotion = "rattled"
            delta = 0.25

        session.add_pressure(req.target_agent_id, delta)
        claim.player_known_status = "disputed"
        return ChallengeRecord(
            challenge_id=session.next_challenge_id(),
            case_id=case.case.case_id,
            target_agent_id=req.target_agent_id,
            challenged_claim_id=req.challenged_claim_id,
            evidence_clue_ids=req.evidence_clue_ids,
            evidence_claim_ids=req.evidence_claim_ids,
            player_statement=req.player_statement,
            outcome="deflect",
            deterministic_response_text=response,
            display_response_text=response,
            emotional_shift=emotion,
            pressure_delta=delta,
            testimony_conflict=conflict.explanation,
        )

    # 2. Testimony that doesn't actually conflict — say so honestly rather than implying it did.
    if req.evidence_claim_ids and not req.evidence_clue_ids:
        response = (
            "And? That doesn't contradict a word I've said. Two people can both be telling you "
            "the truth, detective. That's rather the difficulty, isn't it."
        )
        session.add_pressure(req.target_agent_id, 0.0)
        return ChallengeRecord(
            challenge_id=session.next_challenge_id(),
            case_id=case.case.case_id,
            target_agent_id=req.target_agent_id,
            challenged_claim_id=req.challenged_claim_id,
            evidence_clue_ids=req.evidence_clue_ids,
            evidence_claim_ids=req.evidence_claim_ids,
            player_statement=req.player_statement,
            outcome="deny",
            deterministic_response_text=response,
            display_response_text=response,
            emotional_shift="unmoved",
            pressure_delta=0.0,
        )

    related = _evidence_is_related(case, claim, req.evidence_clue_ids)
    if related:
        response = (
            "I don't see how that contradicts anything I've told you. "
            "You'll have to do better than that."
        )
        delta = 0.05
    else:
        response = "I'm sorry, but that has nothing to do with what you asked me."
        delta = 0.0
    session.add_pressure(req.target_agent_id, delta)
    return ChallengeRecord(
        challenge_id=session.next_challenge_id(),
        case_id=case.case.case_id,
        target_agent_id=req.target_agent_id,
        challenged_claim_id=req.challenged_claim_id,
        evidence_clue_ids=req.evidence_clue_ids,
        evidence_claim_ids=req.evidence_claim_ids,
        player_statement=req.player_statement,
        outcome="deny",
        deterministic_response_text=response,
        display_response_text=response,
        emotional_shift="unmoved",
        pressure_delta=delta,
    )


def _auto_note(
    case: CaseData,
    session: Session,
    req: ChallengeRequest,
    claim: Claim,
    rule: ChallengeRule,
    new_claim_ids: list[str],
    revealed_clue_ids: list[str],
) -> list[str]:
    from .models import Note

    agent_name = next(a.full_name for a in case.agents if a.agent_id == req.target_agent_id)
    evidence_titles = [
        c.title for c in case.clues if c.clue_id in req.evidence_clue_ids
    ]

    if rule.outcome == "reveal_innocent_secret":
        note = Note(
            note_id=session.next_note_id(),
            note_type="interview",
            title=f"{agent_name}'s secret explains the suspicious behaviour",
            body=(
                f"Challenged with {', '.join(evidence_titles)}, {agent_name} revealed an "
                f"innocent secret rather than guilt: {rule.response_text}"
            ),
            linked_agent_ids=[req.target_agent_id],
            linked_clue_ids=req.evidence_clue_ids + revealed_clue_ids,
            linked_claim_ids=[req.challenged_claim_id] + new_claim_ids,
            player_tags=["red_herring", "resolved"],
            status="resolved",
            pinned_to_agent_id=req.target_agent_id,
        )
        session.notes[note.note_id] = note
        return [note.note_id]

    if rule.outcome in ("partial_admission", "deflect", "contradiction_locked", "reframe"):
        resolved = rule.outcome in ("reframe",)
        note = Note(
            note_id=session.next_note_id(),
            note_type="contradiction",
            title=f"{agent_name}'s \"{claim.claim_text[:48]}…\" challenged",
            body=(
                f"Confronted with {', '.join(evidence_titles)}, {agent_name} responded: "
                f"{rule.response_text}"
            ),
            linked_agent_ids=[req.target_agent_id],
            linked_clue_ids=req.evidence_clue_ids,
            linked_claim_ids=[req.challenged_claim_id] + new_claim_ids,
            player_tags=["contradiction", rule.outcome],
            status="resolved" if resolved else "unresolved",
            pinned_to_agent_id=req.target_agent_id,
        )
        session.notes[note.note_id] = note
        return [note.note_id]

    return []


def _record_transcript(session: Session, req: ChallengeRequest, record: ChallengeRecord) -> None:
    transcript = session.transcript_for(req.target_agent_id)
    player_text = req.player_statement or "That doesn't match what I've found."
    transcript.messages.append(
        InterviewMessage(speaker="player", text=f"[Challenge] {player_text}")
    )
    transcript.messages.append(
        InterviewMessage(
            speaker="agent",
            text=record.display_response_text,
            deterministic_text=record.deterministic_response_text,
            generated_claim_ids=record.new_claim_ids,
            revealed_clue_ids=record.revealed_clue_ids,
            llm_rewrite_used=record.llm_rewrite_used,
            llm_rewrite_fallback=record.llm_rewrite_fallback,
            llm_rewrite_fallback_reason=record.llm_rewrite_fallback_reason,
        )
    )


# ---------------------------------------------------------------------------
# Player-safe projection
# ---------------------------------------------------------------------------

def public_challenge(case: CaseData, session: Session, record: ChallengeRecord) -> dict:
    """Strip hidden truth. Outcome/response are player-facing by design; new
    claims and revealed clues/memories are projected to their safe forms."""
    new_claims = [
        project_claim(session.claims[cid]) for cid in record.new_claim_ids if cid in session.claims
    ]
    revealed_clues = [
        project_clue(c) for c in case.clues if c.clue_id in record.revealed_clue_ids
    ]
    revealed_memories = []
    for mem_id in record.revealed_memory_ids:
        mem = next((m for m in case.memories if m.memory_id == mem_id), None)
        if mem:
            revealed_memories.append({"memory_id": mem.memory_id, "summary": mem.summary})
    return {
        "challenge_id": record.challenge_id,
        "target_agent_id": record.target_agent_id,
        "challenged_claim_id": record.challenged_claim_id,
        "evidence_clue_ids": record.evidence_clue_ids,
        "evidence_claim_ids": record.evidence_claim_ids,
        # Why the confrontation bit, in the player's own terms: the two statements that cannot
        # both be true. Not a hidden fact — it is assembled from what they have already heard.
        "testimony_conflict": record.testimony_conflict,
        "outcome": record.outcome,
        "response_text": record.display_response_text,
        "emotional_shift": record.emotional_shift,
        "new_claims": new_claims,
        "revealed_clues": revealed_clues,
        "revealed_memories": revealed_memories,
        "pressure_delta": round(record.pressure_delta, 3),
        "pressure_level": round(session.pressure_for(record.target_agent_id), 3),
        "created_note_ids": record.created_note_ids,
        "duplicate": record.duplicate,
        "llm_rewrite_used": record.llm_rewrite_used,
        "llm_rewrite_fallback": record.llm_rewrite_fallback,
    }
