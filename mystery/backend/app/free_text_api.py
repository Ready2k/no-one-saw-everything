import logging

from fastapi import HTTPException
from app.models import FreeTextAskRequest, FreeTextAskResponse, ChallengeSuggestion, AskRequest, ChallengeRequest, InterviewMessage, QuestionIntent

logger = logging.getLogger(__name__)
from app.question_classifier import classify_question
from app.llm.question_intent_classifier import classify_question_intent_llm
from app.llm.config import get_llm_config
from app.llm.dialogue_rewriter import generate_open_ended_response
from app.interview import answer_question, public_ask_response, examine_body
from app.world_state import build_conversation_context, build_world_state_digest
from app import challenge as challenge_engine
from app.challenge import ChallengeError
from app.dialogue_processor import humanize_response

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

    intent = classify_question(req.question, case, sess)
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
        fallback_msg = apply_deflection(agent)
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

        answer_text = agent.small_talk.get(intent.intent, "I don't have much to say about that.")
        answer_text = humanize_response(answer_text, agent, count)
        
        transcript.messages.append(InterviewMessage(speaker="player", text=req.question, question_type=None))
        transcript.messages.append(
            InterviewMessage(
                speaker="agent",
                text=answer_text,
                llm_rewrite_used=False,
                llm_rewrite_fallback=False,
            )
        )
        return FreeTextAskResponse(
            intent=intent,
            answer={
                "question_text": req.question,
                "answer_text": answer_text,
                "deterministic_answer_text": answer_text,
                "answer_type": "small_talk",
                "emotional_shift": None,
                "new_claims": [],
                "revealed_clues": [],
                "suggested_followups": _generic_followups(case),
                "llm_rewrite_used": False,
                "llm_rewrite_fallback": False,
                "llm_rewrite_fallback_reason": None,
            },
        )

    # Mapping based on intent rules
    if intent.intent == "fallback_unknown":
        config = get_llm_config()
        if not config.dialogue_enabled:
            return fallback_resp

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
        )

        transcript.messages.append(InterviewMessage(speaker="player", text=req.question, question_type=None))
        transcript.messages.append(
            InterviewMessage(
                speaker="agent",
                text=result.rewritten_text,
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
                "new_claims": [],
                "revealed_clues": [],
                "suggested_followups": _generic_followups(case),
                "llm_rewrite_used": True,
                "llm_rewrite_fallback": result.fallback_used,
                "llm_rewrite_fallback_reason": result.fallback_reason,
            },
        )
        
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
                return fallback_resp
    if ask_req.question_type == "location" and not ask_req.topic_location_id:
        return fallback_resp
        
    resp = answer_question(case, sess, ask_req)
    pub_resp = public_ask_response(resp)
    
    return FreeTextAskResponse(
        intent=intent,
        answer=pub_resp
    )
