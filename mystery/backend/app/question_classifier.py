import re
from typing import Optional
from app.models import CaseData
from app.session import Session
from app.models import QuestionIntent
from app.reference_resolver import resolve_references, normalize_text

def _refers_to_victim(q_norm: str, q_words: set[str], victim) -> bool:
    """Word-boundary check for a victim reference. Pronouns like "her"/"him"
    must be whole words — a plain substring check matches "her" inside
    "there", "gathered", "weather" etc. and silently misroutes any question
    containing one of those, e.g. "what happened back there"."""
    if not victim:
        return False
    if normalize_text(victim.full_name.split()[0]) in q_norm:
        return True
    return bool({"him", "her", "them", "victim", "deceased"} & q_words)


def classify_question(question: str, case: CaseData, session: Session) -> Optional[QuestionIntent]:
    refs = resolve_references(question, case, session)
    q_norm = normalize_text(question)
    q_words = set(q_norm.split())

    # 1. Alibi
    if any(phrase in q_norm for phrase in ["where were you", "where was you", "your alibi"]):
        return QuestionIntent(
            intent="alibi",
            confidence=0.9,
            referenced_time=None,
            **refs,
            rewritten_structured_question="Where were you during the murder window?"
        )
        
    # 2. Timeline
    if any(phrase in q_norm for phrase in ["what were you doing", "what did you do", "where did you go"]):
        return QuestionIntent(
            intent="timeline",
            confidence=0.8,
            referenced_time=None, # extracting time from text deterministically is hard, leave None for fallback? or rely on LLM for timeline?
            **refs,
            rewritten_structured_question="What were you doing at that time?"
        )
        
    # 3. Last seen victim
    if any(phrase in q_norm for phrase in ["last see", "last saw", "when did you see"]):
        victim = next((a for a in case.agents if a.is_victim), None)
        if _refers_to_victim(q_norm, q_words, victim):
            return QuestionIntent(
                intent="last_seen_victim",
                confidence=0.9,
                **refs,
                rewritten_structured_question="When did you last see the victim?"
            )
            
    # 4. Relationship
    if any(phrase in q_norm for phrase in ["know", "relationship", "how did you feel about", "first met", "how you met"]):
        victim = next((a for a in case.agents if a.is_victim), None)
        if _refers_to_victim(q_norm, q_words, victim):
            return QuestionIntent(
                intent="relationship",
                confidence=0.85,
                **refs,
                rewritten_structured_question="What was your relationship with the victim?"
            )
            
    # 4b. Conflict/argument with the victim. "Argued", "fought", "disagreement"
    # etc. are not "when did you last see" phrasing (rule 3) and describe a
    # relationship dynamic, not a sighting — routing them to last_seen_victim
    # forces the dialogue rewriter to bridge an unrelated topic, which is how
    # it ends up inventing an incident ("we had a disagreement") that was
    # never in the seeded truth. The relationship answer is the nearest real
    # grounded topic.
    if any(phrase in q_norm for phrase in ["argu", "fight with", "fought with", "disagreement", "falling out", "quarrel"]):
        victim = next((a for a in case.agents if a.is_victim), None)
        if _refers_to_victim(q_norm, q_words, victim):
            return QuestionIntent(
                intent="relationship",
                confidence=0.85,
                **refs,
                rewritten_structured_question="What was your relationship with the victim?"
            )

    # 4c. Confrontational bluff ("we both know what happened", "just admit
    # it") demands a confession without necessarily naming a piece of
    # evidence. It must not fall through to the small-talk buckets below —
    # a suspect should react with suspicion or denial, not recite a generic
    # relationship blurb as if nothing happened.
    if any(phrase in q_norm for phrase in [
        "we both know", "we know what happened", "just admit", "just confess",
        "come clean", "tell me the truth", "stop lying", "you're lying", "why not just tell me",
    ]):
        return QuestionIntent(
            intent="explicit_challenge",
            confidence=0.6,
            **refs,
            rewritten_structured_question="Why not just tell me the truth?"
        )

    # 5. Explicit Challenge or Contradiction
    if any(phrase in q_norm for phrase in ["challenge", "confront", "accuse"]):
        if refs.get("referenced_agent_id") or refs.get("referenced_clue_id") or refs.get("referenced_object_id"):
            return QuestionIntent(
                intent="explicit_challenge",
                confidence=0.85,
                **refs,
                rewritten_structured_question="I challenge you on this."
            )

    if any(phrase in q_norm for phrase in ["why did", "how come", "but you said", "but they said", "someone said", "someone saw"]):
        # If there's a referenced agent, or referenced clue, might be contradiction
        if refs.get("referenced_agent_id") or refs.get("referenced_clue_id"):
            return QuestionIntent(
                intent="contradiction",
                confidence=0.8,
                **refs,
                rewritten_structured_question="Can you explain this contradiction?"
            )

    # 6. Motive
    if any(phrase in q_norm for phrase in ["why would you", "want dead", "reason to hurt", "angry with"]):
        return QuestionIntent(
            intent="motive",
            confidence=0.9,
            **refs,
            rewritten_structured_question="Did you have a motive?"
        )

    # 7. Object
    if refs.get("referenced_object_id"):
        return QuestionIntent(
            intent="object",
            confidence=0.9,
            **refs,
            rewritten_structured_question="What do you know about this object?"
        )
        
    # 8. Evidence (Clue)
    if refs.get("referenced_clue_id"):
        return QuestionIntent(
            intent="evidence",
            confidence=0.9,
            **refs,
            rewritten_structured_question="What do you know about this evidence?"
        )

    # 9. Location
    if refs.get("referenced_location_id"):
        return QuestionIntent(
            intent="location",
            confidence=0.9,
            **refs,
            rewritten_structured_question="What do you know about this location?"
        )
        
    # Small talk - Greetings
    words = set(q_norm.split())
    if "hi" in words or "hello" in words or "hey" in words or "greetings" in words:
        return QuestionIntent(
            intent="greeting",
            confidence=0.9,
            **refs,
            rewritten_structured_question="Hello."
        )

    # Small talk - How are you
    if any(phrase in q_norm for phrase in ["how are you", "how are things", "how do you do", "are you ok", "are you alright", "how's it going"]):
        return QuestionIntent(
            intent="how_are_you",
            confidence=0.9,
            **refs,
            rewritten_structured_question="How are you?"
        )

    # Small talk - Occupation
    if any(phrase in q_norm for phrase in ["what do you do", "your job", "your occupation", "where do you work", "what is your work"]):
        return QuestionIntent(
            intent="occupation",
            confidence=0.9,
            **refs,
            rewritten_structured_question="What is your occupation?"
        )

    # Small talk - How can help
    if any(phrase in q_norm for phrase in ["how can you help", "can you help", "what can you do", "help me out"]):
        return QuestionIntent(
            intent="how_can_help",
            confidence=0.9,
            **refs,
            rewritten_structured_question="How can you help?"
        )

    # Small talk - Favorite thing
    if any(phrase in q_norm for phrase in ["favorite", "favourite", "what do you like", "hobbies", "hobby"]):
        return QuestionIntent(
            intent="favorite_thing",
            confidence=0.9,
            **refs,
            rewritten_structured_question="What is your favorite thing?"
        )

    # Small talk - About me
    if any(phrase in q_norm for phrase in ["tell me about yourself", "who are you", "your background", "where are you from"]):
        return QuestionIntent(
            intent="about_me",
            confidence=0.9,
            **refs,
            rewritten_structured_question="Tell me about yourself."
        )

    # Small talk - Emotions
    if any(phrase in q_norm for phrase in ["happy", "sad", "smile", "cry"]) and any(phrase in q_norm for phrase in ["what makes", "do you", "are you"]):
        return QuestionIntent(
            intent="emotions",
            confidence=0.9,
            **refs,
            rewritten_structured_question="What makes you happy or sad?"
        )

    # Small talk - General relationships
    if any(phrase in q_norm for phrase in ["friends", "get along", "do you like people", "relationships"]):
        # Only if it wasn't already caught by the victim/suspect relationship intent
        return QuestionIntent(
            intent="general_relationships",
            confidence=0.8,
            **refs,
            rewritten_structured_question="Tell me about your relationships."
        )

    # Low confidence -> Return None to let LLM handle it
    return None
