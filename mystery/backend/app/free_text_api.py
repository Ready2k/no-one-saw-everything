import logging
import re

from fastapi import HTTPException
from app.models import FreeTextAskRequest, FreeTextAskResponse, ChallengeSuggestion, AskRequest, ChallengeRequest, InterviewMessage, QuestionIntent

logger = logging.getLogger(__name__)
from app.question_classifier import classify_question
from app.llm.question_intent_classifier import classify_question_intent_llm
from app.llm.config import get_llm_config
from app.llm.dialogue_rewriter import generate_open_ended_response, rewrite_interview_answer
from app.interview import answer_question, public_ask_response, examine_body
from app.world_state import build_conversation_context, build_world_state_digest
from app import challenge as challenge_engine
from app.challenge import ChallengeError
from app.case_store import minutes
from app.testimony import find_tension
from app.dialogue_processor import humanize_response, default_small_talk_line
from app.behavioural_tells import open_ended_tells

_TIME_PATTERN = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


def _detect_claim_tension(sess, agent_id: str, question: str):
    """Layer 6 tension detector (persona_chat_lab/ENGINE_SPEC.md §8), ported
    onto the real claim/testimony machinery instead of reinvented: fires
    only when the player's own question cites the exact times of two claims
    already recorded THIS session that place the interviewed suspect at two
    different locations — arithmetic on facts the player already earned,
    never new information — and only when the pair is not already a
    genuine testimony conflict (that's `find_conflict`'s job, via the
    formal Challenge flow, and it is the more serious of the two).
    Deliberately narrow, per the spec's own warning against this growing
    into a library of bespoke detectors: this covers exactly one pattern.
    Returns (early_claim, late_claim, gap_minutes) or None.
    """
    time_strs = _TIME_PATTERN.findall(question)
    if len(time_strs) < 2:
        return None
    try:
        cited = {minutes(f"{h}:{m}") for h, m in time_strs}
    except Exception:
        return None
    if len(cited) < 2:
        return None

    candidates = [
        c for c in sess.claims.values()
        if c.about_agent_id == agent_id and c.time_reference
    ]
    matched = []
    for c in candidates:
        try:
            if minutes(c.time_reference) in cited:
                matched.append(c)
        except Exception:
            continue
    matched.sort(key=lambda c: c.claim_id)

    for i in range(len(matched)):
        for j in range(i + 1, len(matched)):
            a, b = matched[i], matched[j]
            gap = find_tension(a, b)
            if gap is not None:
                early, late = (a, b) if minutes(a.time_reference) <= minutes(b.time_reference) else (b, a)
                return early, late, gap
    return None


def _tension_reply(case, sess, req: FreeTextAskRequest, tension) -> FreeTextAskResponse:
    early, late, gap = tension
    agent = next(a for a in case.agents if a.agent_id == req.agent_id)
    pressure = sess.pressure_for(req.agent_id)
    transcript = sess.transcript_for(req.agent_id)

    # Built entirely from claim_text already displayed to the player earlier
    # this session (never from hidden case data) — pure arithmetic (a gap in
    # minutes) on facts already told to them, which is why this is safe to
    # hand straight to the same grounded rewrite+sanitiser every other
    # answer goes through, with those two claim texts as the allowed facts.
    deterministic_text = f"{early.claim_text} {late.claim_text} That's a {gap}-minute gap."

    rewrite_result = rewrite_interview_answer(
        case=case,
        agent=agent,
        question_text=req.question,
        deterministic_text=deterministic_text,
        allowed_facts=[early.claim_text, late.claim_text],
        pressure_level=pressure,
        recent_exchange=build_conversation_context(sess, agent) or None,
        emotion="defensive",
        world_state=build_world_state_digest(case, sess, req.agent_id) or None,
        is_repeat=False,
        session=sess,
    )
    display_text = rewrite_result.rewritten_text

    tell_seed = f"{case.case.case_id}:{sess.session_seed}:{req.agent_id}:tension:{early.claim_id}:{late.claim_id}"
    observable_tells = open_ended_tells(agent=agent, pressure=pressure, seed=tell_seed, guarded=True)

    transcript.messages.append(InterviewMessage(speaker="player", text=req.question, question_type=None))
    transcript.messages.append(
        InterviewMessage(
            speaker="agent",
            text=display_text,
            deterministic_text=deterministic_text,
            observable_tells=observable_tells,
            llm_rewrite_used=True,
            llm_rewrite_fallback=rewrite_result.fallback_used,
            llm_rewrite_fallback_reason=rewrite_result.fallback_reason,
        )
    )

    intent = QuestionIntent(
        intent="contradiction",
        confidence=0.7,
        referenced_agent_id=req.agent_id,
        rewritten_structured_question="Can you explain this?",
    )
    return FreeTextAskResponse(
        intent=intent,
        answer={
            "question_text": req.question,
            "answer_text": display_text,
            "deterministic_answer_text": deterministic_text,
            "answer_type": "tension",
            "emotional_shift": "defensive",
            "observable_tells": [t.model_dump() for t in observable_tells],
            "new_claims": [],
            "revealed_clues": [],
            "suggested_followups": _generic_followups(case),
            "llm_rewrite_used": True,
            "llm_rewrite_fallback": rewrite_result.fallback_used,
            "llm_rewrite_fallback_reason": rewrite_result.fallback_reason,
        },
    )

def _generic_followups(case) -> list[str]:
    """Safe, always-available on-ramps back to the grounded structured
    questions, offered after an open-ended reply so the player isn't left
    guessing how to steer the conversation back on track. Deliberately
    generic — not derived from the specific free-text question — so this
    never introduces a new leak surface. Only called for non-victim agents;
    the victim path returns earlier via examine_body."""
    victim = next((a for a in case.agents if a.is_victim), None)
    victim_name = victim.full_name if victim else "the victim"
    return [
        "Where were you during the murder window?",
        f"What was your relationship with {victim_name}?",
        f"When did you last see {victim_name}?",
    ]


def _open_ended_reply(
    case, sess, req: FreeTextAskRequest, intent: QuestionIntent, *, guarded: bool = False
) -> FreeTextAskResponse:
    """Let the agent improvise an in-character reply with no deterministic
    ground truth to rewrite — used for genuinely unmatched questions, a
    confrontation/bluff with no evidence behind it, and a reference to an
    object/location/clue that never resolved (undiscovered, or just not a
    real thing) — so a suspect reacts instead of hitting a flat meta-message.
    Guarded by the same forbidden-facts list and sanitiser as every grounded
    rewrite. `guarded` marks a question the agent has real reason to dodge
    (a bluff or confrontation), which biases the accompanying observable
    tell toward evasion rather than plain pressure."""
    agent = next(a for a in case.agents if a.agent_id == req.agent_id)
    pressure = sess.pressure_for(req.agent_id)
    transcript = sess.transcript_for(req.agent_id)
    recent_exchange = build_conversation_context(sess, agent)

    result = generate_open_ended_response(
        case=case,
        agent=agent,
        question_text=req.question,
        pressure_level=pressure,
        recent_exchange=recent_exchange or None,
        world_state=build_world_state_digest(case, sess, req.agent_id) or None,
        session=sess,
    )

    tell_seed = f"{case.case.case_id}:{sess.session_seed}:{req.agent_id}:{req.question}:{len(transcript.messages)}"
    observable_tells = open_ended_tells(agent=agent, pressure=pressure, seed=tell_seed, guarded=guarded)

    transcript.messages.append(InterviewMessage(speaker="player", text=req.question, question_type=None))
    transcript.messages.append(
        InterviewMessage(
            speaker="agent",
            text=result.rewritten_text,
            observable_tells=observable_tells,
            llm_rewrite_used=True,
            llm_rewrite_fallback=result.fallback_used,
            llm_rewrite_fallback_reason=result.fallback_reason,
        )
    )

    return FreeTextAskResponse(
        intent=intent,
        answer={
            "question_text": req.question,
            "answer_text": result.rewritten_text,
            "deterministic_answer_text": result.rewritten_text,
            "answer_type": "open_ended",
            "emotional_shift": None,
            "observable_tells": [t.model_dump() for t in observable_tells],
            "new_claims": [],
            "revealed_clues": [],
            "suggested_followups": _generic_followups(case),
            "llm_rewrite_used": True,
            "llm_rewrite_fallback": result.fallback_used,
            "llm_rewrite_fallback_reason": result.fallback_reason,
        },
    )


def _record_fallback_and_return(
    sess, req: FreeTextAskRequest, fallback_resp: FreeTextAskResponse
) -> FreeTextAskResponse:
    """A canned deflection (no LLM configured, or nothing grounded to answer
    with) previously never touched the transcript at all — every other reply
    path records both sides of the exchange, but this one silently skipped
    it. That meant a suspect's own conversation history had gaps exactly
    where the player asked something the engine couldn't answer, which is
    precisely where a later pronoun follow-up ("when did you last see
    them?") most needs that history to disambiguate who "them" is."""
    transcript = sess.transcript_for(req.agent_id)
    transcript.messages.append(InterviewMessage(speaker="player", text=req.question, question_type=None))
    transcript.messages.append(
        InterviewMessage(
            speaker="agent",
            text=fallback_resp.fallback_message or "",
            llm_rewrite_used=False,
            llm_rewrite_fallback=False,
        )
    )
    return fallback_resp


def handle_free_text(req: FreeTextAskRequest, case, sess) -> FreeTextAskResponse:
    if req.agent_id == case.case.victim_id:
        resp = examine_body(case, sess, req.question)
        return FreeTextAskResponse(
            intent=QuestionIntent(
                intent="evidence",
                confidence=1.0,
                rewritten_structured_question="Examine body"
            ),
            answer=public_ask_response(resp)
        )
    if not any(a.agent_id == req.agent_id for a in case.agents):
        raise HTTPException(404, "No such agent")

    tension = _detect_claim_tension(sess, req.agent_id, req.question)
    if tension:
        return _tension_reply(case, sess, req, tension)

    intent = classify_question(req.question, case, sess, agent_id=req.agent_id)
    if not intent:
        try:
            intent = classify_question_intent_llm(req.question, case, sess, agent_id=req.agent_id)
        except Exception as e:
            logger.warning("LLM intent classification failed, falling back: %s", e)
            intent = None
        
    if not intent:
        intent = QuestionIntent(
            intent="fallback_unknown",
            confidence=1.0,
            rewritten_structured_question="Unknown"
        )

    agent = next((a for a in case.agents if a.agent_id == req.agent_id), None)
    if agent:
        from app.dialogue_processor import apply_deflection
        fallback_msg = apply_deflection(agent, seed=f"{case.case.case_id}:{req.agent_id}:{req.question}")
    else:
        fallback_msg = "I'm not sure what you mean. Ask me where I was, what I saw, or about a specific person or object."

    fallback_resp = FreeTextAskResponse(
        intent=intent,
        fallback_message=fallback_msg
    )

    SMALL_TALK_INTENTS = ["greeting", "how_are_you", "occupation", "how_can_help", "favorite_thing", "about_me", "general_relationships", "emotions"]
    
    if intent.intent in SMALL_TALK_INTENTS:
        agent = next(a for a in case.agents if a.agent_id == req.agent_id)
        transcript = sess.transcript_for(req.agent_id)

        transcript.intent_counts[intent.intent] = transcript.intent_counts.get(intent.intent, 0) + 1
        count = transcript.intent_counts[intent.intent]

        pressure = sess.pressure_for(req.agent_id)
        tell_seed = f"{case.case.case_id}:{sess.session_seed}:{req.agent_id}:{intent.intent}:{count}"

        deterministic_text = agent.small_talk.get(intent.intent) or default_small_talk_line(agent, intent.intent)
        deterministic_text = humanize_response(deterministic_text, agent, count, seed=tell_seed, pressure=pressure)

        display_text = deterministic_text
        llm_rewrite_used = False
        llm_rewrite_fallback = False
        llm_rewrite_fallback_reason = None

        # Small talk had no ground truth to rewrite from and always played the
        # same one or two canned lines verbatim — the LLM rewrite path was
        # skipped entirely regardless of configuration, so a friendly
        # rapport-building question always got a flat, robotic non-answer.
        # Route it through the same trusted rewrite+sanitiser used for every
        # other grounded answer, with the canned line as both the ground
        # truth and the only allowed fact, so it stays exactly as safe.
        config = get_llm_config()
        if config.dialogue_enabled:
            is_repeat = any(
                m.speaker == "agent" and m.deterministic_text == deterministic_text
                for m in transcript.messages
            )
            rewrite_result = rewrite_interview_answer(
                case=case,
                agent=agent,
                question_text=req.question,
                deterministic_text=deterministic_text,
                allowed_facts=[deterministic_text],
                pressure_level=sess.pressure_for(req.agent_id),
                recent_exchange=build_conversation_context(sess, agent) or None,
                emotion="neutral",
                world_state=build_world_state_digest(case, sess, req.agent_id) or None,
                is_repeat=is_repeat,
                session=sess,
            )
            display_text = rewrite_result.rewritten_text
            llm_rewrite_used = True
            llm_rewrite_fallback = rewrite_result.fallback_used
            llm_rewrite_fallback_reason = rewrite_result.fallback_reason

        observable_tells = open_ended_tells(agent=agent, pressure=pressure, seed=tell_seed)

        transcript.messages.append(InterviewMessage(speaker="player", text=req.question, question_type=None))
        transcript.messages.append(
            InterviewMessage(
                speaker="agent",
                text=display_text,
                deterministic_text=deterministic_text,
                observable_tells=observable_tells,
                llm_rewrite_used=llm_rewrite_used,
                llm_rewrite_fallback=llm_rewrite_fallback,
                llm_rewrite_fallback_reason=llm_rewrite_fallback_reason,
            )
        )
        return FreeTextAskResponse(
            intent=intent,
            answer={
                "question_text": req.question,
                "answer_text": display_text,
                "deterministic_answer_text": deterministic_text,
                "observable_tells": [t.model_dump() for t in observable_tells],
                "answer_type": "small_talk",
                "emotional_shift": None,
                "new_claims": [],
                "revealed_clues": [],
                "suggested_followups": _generic_followups(case),
                "llm_rewrite_used": llm_rewrite_used,
                "llm_rewrite_fallback": llm_rewrite_fallback,
                "llm_rewrite_fallback_reason": llm_rewrite_fallback_reason,
            },
        )

    # Mapping based on intent rules
    if intent.intent == "fallback_unknown":
        config = get_llm_config()
        if not config.dialogue_enabled:
            return _record_fallback_and_return(sess, req, fallback_resp)
        return _open_ended_reply(case, sess, req, intent)

    if intent.intent in ["contradiction", "explicit_challenge"]:
        if not intent.referenced_clue_id:
            for rule in case.challenge_rules:
                if rule.target_agent_id == req.agent_id and rule.challenged_claim_id in sess.claims:
                    for clue_id in rule.evidence_clue_ids:
                        if clue_id in sess.discovered_clue_ids:
                            clue = next((c for c in case.clues if c.clue_id == clue_id), None)
                            if clue:
                                if intent.referenced_agent_id and intent.referenced_agent_id in clue.linked_agent_ids:
                                    intent.referenced_clue_id = clue_id
                                    break
                                if intent.referenced_object_id and getattr(clue, "linked_object_ids", []) and intent.referenced_object_id in clue.linked_object_ids:
                                    intent.referenced_clue_id = clue_id
                                    break
                if intent.referenced_clue_id:
                    break

        if intent.referenced_clue_id:
            for rule in case.challenge_rules:
                if rule.target_agent_id == req.agent_id and intent.referenced_clue_id in rule.evidence_clue_ids:
                    if rule.challenged_claim_id in sess.claims:
                        clue = next((c for c in case.clues if c.clue_id == intent.referenced_clue_id), None)
                        claim = sess.claims[rule.challenged_claim_id]
                        if intent.intent == "explicit_challenge":
                            # Execute the challenge
                            chal_req = ChallengeRequest(
                                target_agent_id=req.agent_id,
                                challenged_claim_id=rule.challenged_claim_id,
                                evidence_clue_ids=[intent.referenced_clue_id],
                                player_statement=req.question
                            )
                            try:
                                chal_res = challenge_engine.resolve_challenge(case, sess, chal_req)
                            except ChallengeError as e:
                                # Guardrail tripped (e.g. undiscovered evidence);
                                # degrade gracefully instead of a 500.
                                return FreeTextAskResponse(
                                    intent=intent,
                                    fallback_message=e.detail,
                                )
                            public_res = challenge_engine.public_challenge(case, sess, chal_res)
                            return FreeTextAskResponse(
                                intent=intent,
                                challenge_result=public_res
                            )
                        else:
                            return FreeTextAskResponse(
                                intent=intent,
                                challenge_suggestion=ChallengeSuggestion(
                                    target_agent_id=req.agent_id,
                                    challenged_claim_id=rule.challenged_claim_id,
                                    claim_text=claim.claim_text,
                                    claim_status=claim.player_known_status,
                                    evidence_clue_id=intent.referenced_clue_id,
                                    evidence_title=clue.title if clue else ""
                                )
                            )
        # No evidence backs this up — a bluff, or a reference the player made
        # that has no scripted rule. Still worth an in-character reaction
        # (denial, suspicion) rather than a flat UI hint, when a rewrite
        # model is available; otherwise keep the original meta message so
        # the player still knows to use the Challenge button.
        if get_llm_config().dialogue_enabled:
            return _open_ended_reply(case, sess, req, intent, guarded=True)
        return FreeTextAskResponse(
            intent=intent,
            fallback_message="That sounds like something to challenge directly. Use the Challenge button if you have evidence."
        )

    ask_req = AskRequest(agent_id=req.agent_id, question_type="alibi", original_question_text=req.question)
    
    if intent.intent in ["alibi", "timeline", "last_seen_victim", "relationship", "location"]:
        ask_req.question_type = intent.intent
        # The referenced time may come from an LLM classifier; anything that
        # isn't a clean HH:MM is dropped (the timeline ask then degrades to an
        # alibi question below) rather than crashing time arithmetic later.
        import re as _re
        t = (intent.referenced_time or "").strip()
        ask_req.time_reference = t if _re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", t) else None
        ask_req.topic_location_id = intent.referenced_location_id
    elif intent.intent == "evidence":
        ask_req.question_type = "evidence"
        ask_req.topic_clue_id = intent.referenced_clue_id
        ask_req.topic_location_id = intent.referenced_location_id
    elif intent.intent == "object":
        ask_req.question_type = "evidence"
        ask_req.topic_object_id = intent.referenced_object_id
    elif intent.intent == "motive":
        if intent.referenced_clue_id:
            ask_req.question_type = "evidence"
            ask_req.topic_clue_id = intent.referenced_clue_id
        else:
            ask_req.question_type = "relationship"

    if ask_req.question_type == "timeline" and not ask_req.time_reference:
        ask_req.question_type = "alibi"
    if ask_req.question_type == "evidence":
        if not ask_req.topic_clue_id and not ask_req.topic_object_id:
            # "evidence" without a clue/object to anchor it is often really a
            # question about a place ("what did you see from there?") that the
            # classifier mislabelled — if a location did resolve, ask about
            # that instead of bouncing to the generic fallback message.
            if ask_req.topic_location_id:
                ask_req.question_type = "location"
            else:
                # The player named an object/clue the resolver could not
                # place — often evidence that just hasn't been discovered
                # yet, by design (app/reference_resolver.py only recognises
                # an object once a clue has linked it). There is nothing
                # grounded to answer with, but a flat "that's not relevant"
                # line about the actual murder weapon reads as broken, not
                # careful — let the agent react in-voice instead when a
                # rewrite model is available.
                if get_llm_config().dialogue_enabled:
                    return _open_ended_reply(case, sess, req, intent)
                return _record_fallback_and_return(sess, req, fallback_resp)
    if ask_req.question_type == "location" and not ask_req.topic_location_id:
        if get_llm_config().dialogue_enabled:
            return _open_ended_reply(case, sess, req, intent)
        return _record_fallback_and_return(sess, req, fallback_resp)
        
    resp = answer_question(case, sess, ask_req)
    pub_resp = public_ask_response(resp)
    
    return FreeTextAskResponse(
        intent=intent,
        answer=pub_resp
    )
