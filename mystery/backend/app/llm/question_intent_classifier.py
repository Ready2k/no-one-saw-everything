import logging
from app.models import CaseData

logger = logging.getLogger(__name__)
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

# relationship/motive are broad narrative buckets with a single scripted
# blurb behind them — a wrong-but-plausible-sounding match here is exactly
# how a specific question (an alleged amount, date, or claim) ends up
# answered with an unrelated canned summary. Held to a higher bar than the
# other intents, which are narrower and less prone to a false-but-confident fit.
MIN_INTENT_CONFIDENCE_NARRATIVE = 0.85
_NARRATIVE_INTENTS = {"relationship", "motive"}


def classify_question_intent_llm(
    question: str,
    case: CaseData,
    session: Session,
    fallback_allowed: bool = True,
    agent_id: str | None = None,
) -> QuestionIntent:
    client = get_llm_client()

    # Recent conversation with this suspect, so follow-ups ("tell me more",
    # "let's go back to...") classify to the topic under discussion. Only the
    # display text is used — it has already been shown to the player, so this
    # adds no new leak surface.
    recent_exchange = "None"
    recent_player_text = ""
    if agent_id:
        transcript = session.transcript_for(agent_id)
        if transcript.messages:
            lines = []
            player_lines = []
            for msg in transcript.messages[-6:]:
                speaker = "Detective" if msg.speaker == "player" else "Suspect"
                lines.append(f"{speaker}: {msg.text}")
                if msg.speaker == "player":
                    player_lines.append(msg.text)
            recent_exchange = "\n".join(lines)
            recent_player_text = " ".join(player_lines)

    # We must only expose discovered/public things to the LLM. A pronoun-only
    # follow-up ("What did you see from there?") names nothing itself, so the
    # player's own recent wording is included as extra matching surface — it's
    # already on the player's screen, so this resolves the topic they raised
    # without exposing anything new. Deliberately excludes the suspect's own
    # replies: an incidental noun in their answer (e.g. mentioning where crates
    # are stored while describing the alley) is not the topic being followed
    # up on, and including it would resolve "there" to the wrong place.
    refs = resolve_references(question, case, session, extra_text=recent_player_text)

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
- relationship: Asking broadly about the general nature or history of their relationship
  with the victim or another named suspect (e.g. "how did you know him", "what was your
  history with her"). Do NOT use this for a question that alleges or asks about a specific
  fact you have no evidence the game has scripted for — e.g. a specific amount, debt, date,
  or claim ("how much does he owe you", "did he threaten you last week"). Those specific
  questions have no scripted answer to draw on, so they should be fallback_unknown instead
  of forced into this bucket, which would otherwise reply with an unrelated canned summary.
- evidence: Asking about a specific clue.
- location: Asking about a specific location.
- motive: Asking broadly why they might want the victim dead in general terms. As with
  relationship, a specific alleged fact ("was it about the €8,000 loan") is fallback_unknown,
  not motive.
- object: Asking about a physical item or evidence.
- contradiction: Asking a vague question about a lie or contradictory statement ("Why did someone say X?").
- explicit_challenge: Explicitly demanding to confront or challenge the suspect with evidence ("Challenge Clara with Ben's sighting").
- fallback_unknown: Anything else — including personal background, childhood, feelings,
  opinions, hobbies, small talk, or a specific alleged fact/detail not covered by the other
  categories above, that is not specifically about the victim, another named suspect, a piece
  of evidence, or the murder. When the question could plausibly go either way, or asks about
  a specific detail rather than a general topic, prefer fallback_unknown and give it a lower
  confidence score rather than forcing a fit.
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
        threshold = (
            MIN_INTENT_CONFIDENCE_NARRATIVE
            if intent.intent in _NARRATIVE_INTENTS
            else MIN_INTENT_CONFIDENCE
        )
        if intent.intent != "fallback_unknown" and intent.confidence < threshold:
            intent = intent.model_copy(update={
                "intent": "fallback_unknown",
                "rewritten_structured_question": "Unknown question",
            })
        return intent
    except Exception as e:
        logger.warning("Intent classification failed: %s", e)
        return QuestionIntent(
            intent="fallback_unknown",
            confidence=1.0,
            rewritten_structured_question="Unknown question",
            **refs
        )
