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
from .store import minutes

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
    for rule in pack.rules:
        if rule.question_type != req.question_type:
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
        answer_text = pack.default_answers.get(
            req.question_type, "I don't have anything to say about that."
        )
        response = AskResponse(
            question_text=question_text,
            answer_text=answer_text,
            answer_type="uncertain",
        )
        _record(session, req, question_text, answer_text, [], [])
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

    _record(
        session,
        req,
        question_text,
        rule.answer_text,
        [c.claim_id for c in new_claims],
        [c.clue_id for c in revealed],
    )

    return AskResponse(
        question_text=question_text,
        answer_text=rule.answer_text,
        answer_type=rule.answer_type,
        emotional_shift=rule.emotional_shift,
        new_claims=new_claims,
        revealed_clues=revealed,
        suggested_followups=rule.suggested_followups,
    )


def _record(
    session: Session,
    req: AskRequest,
    question_text: str,
    answer_text: str,
    claim_ids: list[str],
    clue_ids: list[str],
) -> None:
    transcript = session.transcript_for(req.agent_id)
    transcript.messages.append(
        InterviewMessage(speaker="player", text=question_text, question_type=req.question_type)
    )
    transcript.messages.append(
        InterviewMessage(
            speaker="agent",
            text=answer_text,
            generated_claim_ids=claim_ids,
            revealed_clue_ids=clue_ids,
        )
    )


def public_ask_response(resp: AskResponse) -> dict:
    """Strip hidden truth (lie flags) before the response crosses the API."""
    return {
        "question_text": resp.question_text,
        "answer_text": resp.answer_text,
        "answer_type": resp.answer_type,
        "emotional_shift": resp.emotional_shift,
        "new_claims": [project_claim(c) for c in resp.new_claims],
        "revealed_clues": [project_clue(c) for c in resp.revealed_clues],
        "suggested_followups": resp.suggested_followups,
    }
