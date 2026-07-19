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
    BehaviouralBaseline,
    CaseData,
    Claim,
    InterviewMessage,
)
from .projections import project_claim, project_clue
from .session import Session
from .case_store import minutes
from .behavioural_tells import baseline_habit, interview_tells, pressure_band
from .llm.config import get_llm_config
from .llm.dialogue_rewriter import rewrite_interview_answer
from .world_state import build_conversation_context, build_world_state_digest

QUESTION_TEXT = {
    "alibi": "Where were you during the murder window, between {murder_start} and {murder_end}?",
    "last_seen_victim": "When did you last see {victim}?",
    "relationship": "What was your relationship with {victim}?",
}


def build_question_text(case: CaseData, req: AskRequest) -> str:
    victim = next(a for a in case.agents if a.agent_id == case.case.victim_id).full_name
    if req.question_type in QUESTION_TEXT:
        return QUESTION_TEXT[req.question_type].format(
            victim=victim,
            murder_start=case.case.murder_window[0],
            murder_end=case.case.murder_window[1]
        )
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

    # Prefer the player's own wording (free-text asks) over the templated
    # question text, so the transcript and the LLM rewrite react to what was
    # actually asked rather than a generic paraphrase (spec 06 free-text path).
    question_text = req.original_question_text or build_question_text(case, req)
    rule = _match_rule(pack, case, session, req)

    new_claims: list[Claim] = []
    revealed = []
    if rule is None:
        deterministic_answer = pack.default_answers.get(
            req.question_type, "I don't have anything to say about that."
        )
        if req.question_type == "location" and req.topic_location_id:
            if req.topic_location_id != case.case.murder_location_id:
                loc = next((l for l in case.locations if l.location_id == req.topic_location_id), None)
                loc_name = loc.name if loc else "that place"
                deterministic_answer = f"I don't have anything special to tell you about {loc_name}."
        elif req.question_type == "evidence" and req.topic_clue_id:
            clue = next((c for c in case.clues if c.clue_id == req.topic_clue_id), None)
            clue_name = clue.title if clue else "this"
            deterministic_answer = f"I don't know anything about '{clue_name}'."
        elif req.question_type == "timeline" and req.time_reference:
            # The default timeline answer is usually a generic statement about their morning.
            # Prepending the time makes it feel like they are directly answering the specific question.
            deterministic_answer = f"Around {req.time_reference}? {deterministic_answer}"
        
        answer_type = "uncertain"
        truthfulness = "unknown"
        emotional_shift = None
        suggested_followups: list[str] = []
    else:
        for ac in rule.claims:
            claim = Claim(
                claim_id=ac.claim_id,
                speaker_agent_id=req.agent_id,
                claim_text=ac.summary,
                claim_type=ac.claim_type,
                time_reference=ac.time_reference,
                location_reference_id=ac.location_reference_id,
                truthfulness=ac.truthfulness,
                # Who the statement places, and whether it puts them there — without these the
                # testimony engine cannot tell "Elias, at the fountain" from "Elias says CLARA
                # was never at the fountain", and one person's word can never disprove another's.
                about_agent_id=ac.about_agent_id,
                asserts_presence=ac.asserts_presence,
            )
            session.record_claim(claim)
            new_claims.append(claim)

        for clue_id in rule.reveals_clue_ids:
            clue = next((c for c in case.clues if c.clue_id == clue_id), None)
            if clue and clue_id not in session.discovered_clue_ids:
                session.discovered_clue_ids.add(clue_id)
                revealed.append(clue)

        deterministic_answer = rule.answer_text
        answer_type = rule.answer_type
        truthfulness = rule.truthfulness
        emotional_shift = rule.emotional_shift
        suggested_followups = rule.suggested_followups

    agent = next(a for a in case.agents if a.agent_id == req.agent_id)
    pressure = session.pressure_for(req.agent_id)

    # Baseline memory: quietly file away how this person behaves when calm, the
    # first time they answer unpressured. Later reads measure change against it.
    baseline = session.baselines.get(req.agent_id)
    if baseline is None and pressure < 0.35:
        habit_category, habit_text, deviation_cue = baseline_habit(agent, case.case.case_id)
        baseline = BehaviouralBaseline(
            agent_id=req.agent_id,
            habit_category=habit_category,
            habit_text=habit_text,
            captured_at_pressure=pressure,
            deviation_cue=deviation_cue,
        )
        session.baselines[req.agent_id] = baseline

    # "Different from earlier" is news exactly once per escalation: the first
    # answer after the suspect enters a new pressure band carries the comparison.
    note_baseline_shift = False
    band = pressure_band(pressure)
    if baseline is not None and band >= 2:
        noted = session.baseline_shift_noted.setdefault(req.agent_id, [])
        if band not in noted:
            noted.append(band)
            note_baseline_shift = True

    tell_seed = f"{case.case.case_id}:{req.agent_id}:{question_text}:{len(session.transcript_for(req.agent_id).messages)}"
    observable_tells = interview_tells(
        agent=agent,
        question_type=req.question_type,
        truthfulness=truthfulness,
        emotional_shift=emotional_shift,
        pressure=pressure,
        seed=tell_seed,
        baseline=baseline,
        note_baseline_shift=note_baseline_shift,
    )

    # Rewrite logic. Applies whether or not an authored rule matched — an
    # agent with no scripted line for this topic should still speak in their
    # own voice via the LLM rather than reciting pack.default_answers
    # verbatim every time.
    config = get_llm_config()
    display_answer = deterministic_answer
    llm_rewrite_used = False
    llm_rewrite_fallback = False
    llm_rewrite_fallback_reason = None

    if config.dialogue_enabled:
        allowed_facts = [c.claim_text for c in new_claims] + [c.title for c in revealed]
        # Recent turns verbatim plus an extractive summary of the interview's
        # earlier statements (spec 15 Phase B), so long interrogations keep
        # continuity with their own opening.
        recent_exchange = build_conversation_context(session, agent)

        # Has this agent already given the player this exact line? Only then is a
        # "you've asked me that" framing honest — see _diegetic_fallback.
        is_repeat = any(
            m.speaker == "agent" and m.deterministic_text == deterministic_answer
            for m in session.transcript_for(req.agent_id).messages
        )

        rewrite_result = rewrite_interview_answer(
            case=case,
            agent=agent,
            question_text=question_text,
            deterministic_text=deterministic_answer,
            allowed_facts=allowed_facts,
            pressure_level=pressure,
            recent_exchange=recent_exchange or None,
            emotion=emotional_shift or "neutral",
            world_state=build_world_state_digest(case, session, req.agent_id) or None,
            is_repeat=is_repeat,
        )
        display_answer = rewrite_result.rewritten_text
        llm_rewrite_used = True
        llm_rewrite_fallback = rewrite_result.fallback_used
        llm_rewrite_fallback_reason = rewrite_result.fallback_reason

    if revealed:
        # Spec 15 Phase C: newly surfaced evidence is a belief-update trigger
        # for the agents it points at. Fire-and-forget; no-op unless enabled.
        from .llm.belief_updater import schedule_belief_updates

        schedule_belief_updates(
            case,
            session,
            [aid for clue in revealed for aid in clue.linked_agent_ids],
            "The detective has turned up new evidence in the case.",
        )

    _record(
        session,
        req,
        question_text,
        deterministic_answer_text=deterministic_answer,
        display_answer_text=display_answer,
        claim_ids=[c.claim_id for c in new_claims],
        clue_ids=[c.clue_id for c in revealed],
        observable_tells=observable_tells,
        llm_rewrite_used=llm_rewrite_used,
        llm_rewrite_fallback=llm_rewrite_fallback,
        llm_rewrite_fallback_reason=llm_rewrite_fallback_reason,
    )

    return AskResponse(
        question_text=question_text,
        deterministic_answer_text=deterministic_answer,
        display_answer_text=display_answer,
        answer_type=answer_type,
        emotional_shift=emotional_shift,
        observable_tells=observable_tells,
        new_claims=new_claims,
        revealed_clues=revealed,
        suggested_followups=suggested_followups,
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
    observable_tells: list = [],
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
            observable_tells=observable_tells,
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
        "observable_tells": [t.model_dump() for t in resp.observable_tells],
        "new_claims": [project_claim(c) for c in resp.new_claims],
        "revealed_clues": [project_clue(c) for c in resp.revealed_clues],
        "suggested_followups": resp.suggested_followups,
        "llm_rewrite_used": resp.llm_rewrite_used,
        "llm_rewrite_fallback": resp.llm_rewrite_fallback,
    }

def is_body_examination_clue(clue, victim_id: str, discovery_location_id: str) -> bool:
    if clue.discoverability.method != "inspect":
        return False
        
    if clue.discoverability.reveal_on:
        return "examine_body" in clue.discoverability.reveal_on
    
    text = f"{clue.title} {clue.description}".lower()
    body_terms = ["body", "pocket", "hand", "clothes", "coat", "jacket", "wound", "note"]
    
    return (
        clue.discoverability.location_id == discovery_location_id
        and (
            victim_id in clue.linked_agent_ids
            or any(term in text for term in body_terms)
        )
    )

def examine_body(case: CaseData, session: Session, player_statement: str = "Examine body") -> AskResponse:
    cause_of_death = case.case.cause_of_death_observed or "Unknown"
    if not case.case.cause_of_death_observed and case.case.method:
        # Fallback to sanitized method if it doesn't look like a spoiler
        if case.case.method in ["blunt_force", "stabbing", "poison", "strangulation", "gunshot"]:
            cause_of_death = case.case.method.replace('_', ' ').capitalize()

    
    victim = next((a for a in case.agents if a.agent_id == case.case.victim_id), None)
    victim_name = victim.full_name.split()[0] if victim else "the victim"
    
    scene_desc = case.case.scene_description or f"The body of {victim_name} lies here."
    
    answer = f"You observe {victim_name}. {scene_desc}\n\nCause of death appears to be: {cause_of_death}.\n\nPlease use the dedicated visual autopsy view to search the body for clues."
        
    req = AskRequest(agent_id=case.case.victim_id, question_type="evidence")
    _record(
        session,
        req,
        question_text=player_statement,
        deterministic_answer_text=answer,
        display_answer_text=answer,
        claim_ids=[],
        clue_ids=[],
        llm_rewrite_used=False,
    )
    
    # Also log telemetry
    from .telemetry import log_telemetry_event
    log_telemetry_event(session, "body_examined", {"agent_id": case.case.victim_id, "clues_found": 0})

    return AskResponse(
        question_text=player_statement,
        deterministic_answer_text=answer,
        display_answer_text=answer,
        answer_type="claim",
        emotional_shift=None,
        new_claims=[],
        revealed_clues=[],
        suggested_followups=[],
        llm_rewrite_used=False,
        llm_rewrite_fallback=False,
    )
