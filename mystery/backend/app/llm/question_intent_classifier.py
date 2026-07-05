from app.models import CaseData
from app.session import Session
from app.models import QuestionIntent
from app.llm.client import get_llm_client
from app.reference_resolver import resolve_references

# Below this, a structured classification is treated as too shaky to commit
# to — the question is routed to the open-ended in-character responder
# instead of forcing a possibly-wrong scripted answer. Self-reported LLM
# confidence isn't perfectly calibrated (a small local model can be
# confidently wrong), so this is a blunt backstop, not a precise filter —
# the prompt wording below is the first line of defence.
MIN_INTENT_CONFIDENCE = 0.7


def classify_question_intent_llm(
    question: str,
    case: CaseData,
    session: Session,
    fallback_allowed: bool = True,
    agent_id: str | None = None,
) -> QuestionIntent:
    client = get_llm_client()

    # We must only expose discovered/public things to the LLM
    refs = resolve_references(question, case, session)

    # Recent conversation with this suspect, so follow-ups ("tell me more",
    # "let's go back to...") classify to the topic under discussion. Only the
    # display text is used — it has already been shown to the player, so this
    # adds no new leak surface.
    recent_exchange = "None"
    if agent_id:
        transcript = session.transcript_for(agent_id)
        if transcript.messages:
            lines = []
            for msg in transcript.messages[-6:]:
                speaker = "Detective" if msg.speaker == "player" else "Suspect"
                lines.append(f"{speaker}: {msg.text}")
            recent_exchange = "\n".join(lines)

    # Provide the LLM with context about what these IDs mean so it can map accurately
    # e.g., if referenced_agent_id is present, tell LLM their name.
    available_context = []

    if refs["referenced_agent_id"]:
        agent = next((a for a in case.agents if a.agent_id == refs["referenced_agent_id"]), None)
        if agent:
            available_context.append(f"Agent: {agent.full_name} ({agent.agent_id})")

    if refs["referenced_location_id"]:
        loc = next((l for l in case.locations if l.location_id == refs["referenced_location_id"]), None)
        if loc:
            available_context.append(f"Location: {loc.name} ({loc.location_id})")

    if refs["referenced_object_id"]:
        obj = next((o for o in case.objects if o.object_id == refs["referenced_object_id"]), None)
        if obj:
            available_context.append(f"Object: {obj.name} ({obj.object_id})")

    if refs["referenced_clue_id"]:
        clue = next((c for c in case.clues if c.clue_id == refs["referenced_clue_id"]), None)
        if clue:
            available_context.append(f"Clue: {clue.title} ({clue.clue_id})")

    context_str = "\n".join(available_context) if available_context else "None"

    system_prompt = (
        "You are a classification system for a detective game. The player has asked "
        "a suspect a question. Map the free-text question into a structured "
        "QuestionIntent JSON object. Never invent IDs; only use IDs given to you."
    )
    user_prompt = f"""
Question: "{question}"

Recent exchange with this suspect (for resolving follow-ups; may be None):
{recent_exchange}

Resolved references in the question (Use ONLY these IDs if applicable, do not invent IDs):
{context_str}

Intent rules:
- If the question is a follow-up ("tell me more", "go back to that", "and then?"),
  infer the intent from the topic of the recent exchange above.
- alibi: Asking where they were during the murder.
- timeline: Asking what they were doing at a specific time.
- last_seen_victim: Asking when they last saw the victim.
- relationship: Asking specifically about their relationship or history with the victim,
  or with another named suspect already established in this case.
- evidence: Asking about a specific clue.
- location: Asking about a specific location.
- motive: Asking why they might want the victim dead.
- object: Asking about a physical item or evidence.
- contradiction: Asking a vague question about a lie or contradictory statement ("Why did someone say X?").
- explicit_challenge: Explicitly demanding to confront or challenge the suspect with evidence ("Challenge Clara with Ben's sighting").
- fallback_unknown: Anything else — including personal background, childhood, feelings,
  opinions, hobbies, or small talk that is not specifically about the victim, another named
  suspect, a piece of evidence, or the murder. When the question could plausibly go either
  way, prefer fallback_unknown and give it a lower confidence score rather than forcing a fit.
"""
    try:
        intent = client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=QuestionIntent,
        )
        # Ensure we only use the safely resolved IDs, whatever the LLM returned.
        intent = intent.model_copy(update=refs)
        # A shaky structured guess is worse than admitting uncertainty: better
        # to let the open-ended responder speak in character than force an
        # answer to a question that was probably misclassified.
        if intent.intent != "fallback_unknown" and intent.confidence < MIN_INTENT_CONFIDENCE:
            intent = intent.model_copy(update={
                "intent": "fallback_unknown",
                "rewritten_structured_question": "Unknown question",
            })
        return intent
    except Exception:
        return QuestionIntent(
            intent="fallback_unknown",
            confidence=1.0,
            rewritten_structured_question="Unknown question",
            **refs
        )
