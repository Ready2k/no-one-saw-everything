from fastapi import HTTPException
from app.models import FreeTextAskRequest, FreeTextAskResponse, ChallengeSuggestion, AskRequest, ChallengeRequest
from app.question_classifier import classify_question
from app.llm.question_intent_classifier import classify_question_intent_llm
from app.interview import answer_question, public_ask_response
from app import challenge as challenge_engine
from app.challenge import ChallengeError

def handle_free_text(req: FreeTextAskRequest, case, sess) -> FreeTextAskResponse:
    if req.agent_id == case.case.victim_id:
        raise HTTPException(400, "The victim is unavailable for comment.")
    if not any(a.agent_id == req.agent_id for a in case.agents):
        raise HTTPException(404, "No such agent")
        
    intent = classify_question(req.question, case, sess)
    if not intent:
        intent = classify_question_intent_llm(req.question, case, sess)
        
    fallback_resp = FreeTextAskResponse(
        intent=intent,
        fallback_message="I'm not sure what you mean. Ask me where I was, what I saw, or about a specific person or object."
    )
        
    # Mapping based on intent rules
    if intent.intent == "fallback_unknown":
        return fallback_resp
        
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

    ask_req = AskRequest(agent_id=req.agent_id, question_type="alibi")
    
    if intent.intent in ["alibi", "timeline", "last_seen_victim", "relationship", "location"]:
        ask_req.question_type = intent.intent
        ask_req.time_reference = intent.referenced_time
        ask_req.topic_location_id = intent.referenced_location_id
    elif intent.intent == "evidence":
        ask_req.question_type = "evidence"
        ask_req.topic_clue_id = intent.referenced_clue_id
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
            return fallback_resp
    if ask_req.question_type == "location" and not ask_req.topic_location_id:
        return fallback_resp
        
    resp = answer_question(case, sess, ask_req)
    pub_resp = public_ask_response(resp)
    
    return FreeTextAskResponse(
        intent=intent,
        answer=pub_resp
    )
