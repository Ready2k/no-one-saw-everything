"""Structured interview engine (Phase 4).

Deterministic and fully grounded: every answer comes from the agent's
hand-authored interview pack, which is itself derived from their seeded
memories and lie state. This module implements the same input/output
contract the future LLM-backed engine will use (spec 06), so an LLM
provider can be swapped in behind `answer_question` later.
"""

from __future__ import annotations

from typing import Optional

from .models import (
    AgentInterviewPack,
    AnswerRule,
    AskRequest,
    AskResponse,
    CaseData,
    Claim,
    InterviewMessage,
)
from .projections import project_claim, project_clue
from .session import Session
from .case_store import minutes
from .llm.config import get_llm_config
from .llm.dialogue_rewriter import rewrite_interview_answer

QUESTION_TEXT = {
    "alibi": "Where were you during the murder window, between 07:45 and 08:00?",
    "last_seen_victim": "When did you last see {victim}?",
    "relationship": "What was your relationship with {victim}?",
}


def build_question_text(case: CaseData, req: AskRequest) -> str:
    victim = next(a for a in case.agents if a.agent_id == case.case.victim_id).full_name
    if req.question_type in QUESTION_TEXT:
        return QUESTION_TEXT[req.question_type].format(victim=victim)
    if req.question_type == "timeline":
        return f"What were you doing around {req.time_reference}?"
    if req.question_type == "evidence":
        if req.topic_clue_id:
            clue = next((c for c in case.clues if c.clue_id == req.topic_clue_id), None)
            topic = clue.title if clue else "this evidence"
        else:
            obj = next((o for o in case.objects if o.object_id == req.topic_object_id), None)
            topic = obj.name if obj else "this object"
        return f"What do you know about {topic}?"
    if req.question_type == "location":
        loc = next((l for l in case.locations if l.location_id == req.topic_location_id), None)
        return f"Tell me about your movements around {loc.name if loc else 'that place'}."
    return "Tell me what you know."


def _prereqs_met(case: CaseData, session: Session, rule: AnswerRule) -> bool:
    """A rule that reveals clues is only reachable once those clues'
    prerequisite discoveries have been made (spec 09 discoverability)."""
    for clue_id in rule.reveals_clue_ids:
        clue = next((c for c in case.clues if c.clue_id == clue_id), None)
        if clue is None:
            continue
        for prior in clue.discoverability.required_prior_clue_ids:
            if prior not in session.discovered_clue_ids:
                return False
    return True


def _match_rule(
    pack: AgentInterviewPack, case: CaseData, session: Session, req: AskRequest
) -> Optional[AnswerRule]:
    # How many times the player has already asked this agent this question
    # type (the current ask is not yet recorded), for depth-gated rules.
    prior_asks = sum(
        1
        for m in session.transcript_for(req.agent_id).messages
        if m.speaker == "player" and m.question_type == req.question_type
    )
    for rule in pack.rules:
        if rule.question_type != req.question_type:
            continue
        if prior_asks < rule.min_ask_count:
            continue
        if req.question_type == "timeline":
            if not req.time_reference:
                continue
            t = minutes(req.time_reference)
            if rule.time_from and t < minutes(rule.time_from):
                continue
            if rule.time_to and t > minutes(rule.time_to):
                continue
        if req.question_type == "evidence":
            if rule.topic_clue_id and rule.topic_clue_id != req.topic_clue_id:
                continue
            if rule.topic_object_id and rule.topic_object_id != req.topic_object_id:
                continue
            if not rule.topic_clue_id and not rule.topic_object_id:
                continue
        if req.question_type == "location":
            if rule.topic_location_id != req.topic_location_id:
                continue
        if not _prereqs_met(case, session, rule):
            continue
        return rule
    return None


def answer_question(case: CaseData, session: Session, req: AskRequest) -> AskResponse:
    pack = next((p for p in case.interview_packs if p.agent_id == req.agent_id), None)
    if pack is None:
        raise ValueError(f"No interview pack for {req.agent_id}")

    question_text = build_question_text(case, req)
    rule = _match_rule(pack, case, session, req)

    if rule is None:
        deterministic_answer = pack.default_answers.get(
            req.question_type, "I don't have anything to say about that."
        )
        response = AskResponse(
            question_text=question_text,
            deterministic_answer_text=deterministic_answer,
            display_answer_text=deterministic_answer,
            answer_type="uncertain",
        )
        _record(
            session, req, question_text,
            deterministic_answer_text=deterministic_answer,
            display_answer_text=deterministic_answer,
            claim_ids=[], clue_ids=[],
            llm_rewrite_used=False,
            llm_rewrite_fallback=False,
            llm_rewrite_fallback_reason=None
        )
        return response

    new_claims: list[Claim] = []
    for ac in rule.claims:
        claim = Claim(
            claim_id=ac.claim_id,
            speaker_agent_id=req.agent_id,
            claim_text=ac.summary,
            claim_type=ac.claim_type,
            time_reference=ac.time_reference,
            location_reference_id=ac.location_reference_id,
            truthfulness=ac.truthfulness,
        )
        session.record_claim(claim)
        new_claims.append(claim)

    revealed = []
    for clue_id in rule.reveals_clue_ids:
        clue = next((c for c in case.clues if c.clue_id == clue_id), None)
        if clue and clue_id not in session.discovered_clue_ids:
            session.discovered_clue_ids.add(clue_id)
            revealed.append(clue)

    # Rewrite logic
    config = get_llm_config()
    deterministic_answer = rule.answer_text
    display_answer = deterministic_answer
    llm_rewrite_used = False
    llm_rewrite_fallback = False
    llm_rewrite_fallback_reason = None
    
    if config.dialogue_enabled:
        allowed_facts = [c.claim_text for c in new_claims] + [c.title for c in revealed]
        agent = next(a for a in case.agents if a.agent_id == req.agent_id)
        pressure = session.pressure_for(req.agent_id)

        # Last few turns of this interview (display text only — already shown
        # to the player) so the rewrite can keep conversational continuity.
        transcript = session.transcript_for(req.agent_id)
        recent_exchange = [
            f"{'Detective' if m.speaker == 'player' else agent.full_name}: {m.text}"
            for m in transcript.messages[-6:]
        ]

        rewrite_result = rewrite_interview_answer(
            case=case,
            agent=agent,
            question_text=question_text,
            deterministic_text=deterministic_answer,
            allowed_facts=allowed_facts,
            pressure_level=pressure,
            recent_exchange=recent_exchange or None,
        )
        display_answer = rewrite_result.rewritten_text
        llm_rewrite_used = True
        llm_rewrite_fallback = rewrite_result.fallback_used
        llm_rewrite_fallback_reason = rewrite_result.fallback_reason

    _record(
        session,
        req,
        question_text,
        deterministic_answer_text=deterministic_answer,
        display_answer_text=display_answer,
        claim_ids=[c.claim_id for c in new_claims],
        clue_ids=[c.clue_id for c in revealed],
        llm_rewrite_used=llm_rewrite_used,
        llm_rewrite_fallback=llm_rewrite_fallback,
        llm_rewrite_fallback_reason=llm_rewrite_fallback_reason,
    )

    return AskResponse(
        question_text=question_text,
        deterministic_answer_text=deterministic_answer,
        display_answer_text=display_answer,
        answer_type=rule.answer_type,
        emotional_shift=rule.emotional_shift,
        new_claims=new_claims,
        revealed_clues=revealed,
        suggested_followups=rule.suggested_followups,
        llm_rewrite_used=llm_rewrite_used,
        llm_rewrite_fallback=llm_rewrite_fallback,
        llm_rewrite_fallback_reason=llm_rewrite_fallback_reason,
    )


def _record(
    session: Session,
    req: AskRequest,
    question_text: str,
    deterministic_answer_text: str,
    display_answer_text: str,
    claim_ids: list[str],
    clue_ids: list[str],
    llm_rewrite_used: bool = False,
    llm_rewrite_fallback: bool = False,
    llm_rewrite_fallback_reason: Optional[str] = None,
) -> None:
    transcript = session.transcript_for(req.agent_id)
    transcript.messages.append(
        InterviewMessage(speaker="player", text=question_text, question_type=req.question_type)
    )
    transcript.messages.append(
        InterviewMessage(
            speaker="agent",
            text=display_answer_text,
            deterministic_text=deterministic_answer_text,
            generated_claim_ids=claim_ids,
            revealed_clue_ids=clue_ids,
            llm_rewrite_used=llm_rewrite_used,
            llm_rewrite_fallback=llm_rewrite_fallback,
            llm_rewrite_fallback_reason=llm_rewrite_fallback_reason,
        )
    )


def public_ask_response(resp: AskResponse) -> dict:
    """Strip hidden truth (lie flags) before the response crosses the API."""
    return {
        "question_text": resp.question_text,
        "answer_text": resp.display_answer_text,
        "deterministic_answer_text": resp.deterministic_answer_text,
        "answer_type": resp.answer_type,
        "emotional_shift": resp.emotional_shift,
        "new_claims": [project_claim(c) for c in resp.new_claims],
        "revealed_clues": [project_clue(c) for c in resp.revealed_clues],
        "suggested_followups": resp.suggested_followups,
        "llm_rewrite_used": resp.llm_rewrite_used,
        "llm_rewrite_fallback": resp.llm_rewrite_fallback,
    }
