"""LLM dialogue rewriting module."""

# import json  # UNUSED — commented out during code review [2026-07-19]
import random
import re
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

from pydantic import BaseModel

from .client import get_llm_client
from .schemas import DialogueRewrite
from ..models import CaseData, Agent

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

class RewriteResult(BaseModel):
    rewritten_text: str
    fallback_used: bool
    fallback_reason: Optional[str] = None


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text("utf-8")


def _build_forbidden_facts(case: CaseData, agent: Agent) -> list[str]:
    """Extract hidden facts that should never leak."""
    forbidden = []
    
    # Hidden roles
    if case.solution.killer_id == agent.agent_id:
        forbidden.append(f"{agent.full_name} is the killer.")
    
    for conclusion in case.conclusions:
        forbidden.append(conclusion.summary)
        
    for mem in case.memories:
        if mem.owner_agent_id == agent.agent_id and mem.truth_status != "true":
            forbidden.append(mem.summary)
            
    for rule in case.solution.motive.concept_groups:
        forbidden.extend(rule)
    for rule in case.solution.method.concept_groups:
        forbidden.extend(rule)
    for rule in case.solution.opportunity.concept_groups:
        forbidden.extend(rule)
        
    return forbidden


def _sanitise(
    text: str,
    forbidden_facts: list[str],
    allowed_facts: list[str],
    case: CaseData,
    allowed_context: list[str],
) -> Optional[str]:
    """
    Sanitises LLM text.
    Returns a rejection reason if invalid, else None.
    """
    text_lower = text.lower()
    allowed_blob = " ".join(allowed_facts + allowed_context).lower()

    # 1. Role labels
    bad_labels = ["killer", "red_herring", "victim_role"]
    for label in bad_labels:
        if label in text_lower:
            return f"Contains raw role label: {label}"

    # 2. JSON leakage
    if "{" in text or "}" in text:
        return "Contains JSON syntax or schema leakage"

    # 3. Hidden Event IDs / Clue IDs
    # Rather than checking all IDs, we just look for typical ID formats if they leak,
    # but more robustly, we just check forbidden facts.

    # 4. Forbidden facts
    # We do a basic substring check for very specific forbidden phrases, but a better
    # check is if any forbidden fact's key nouns are leaked in a way that suggests guilt.
    # To keep it simple and deterministic, we'll check exact string overlap of long chunks.
    # Actually, the requirement was "forbidden facts passed in forbidden_facts".
    #
    # Exempt any forbidden phrase that is already visible in the deterministic
    # text/allowed context being rewritten: the solution's grading concept
    # groups (used to score free-text accusations) share vocabulary with
    # scripted dialogue by design — e.g. a killer's false alibi is
    # deliberately worded close to the true murder window ("quarter to
    # eight"). That word overlap is the scripted lie doing its job, not the
    # model smuggling in a new fact, so a faithful paraphrase must not be
    # rejected for reusing wording the player could already see.
    for fact in forbidden_facts:
        fact_lower = fact.lower()
        if len(fact) > 10 and fact_lower in text_lower and fact_lower not in allowed_blob:
            return f"Contains forbidden fact: {fact}"

    # 5. Unsupported facts
    # The rewrite may not introduce cast members that the grounded answer never
    # mentioned — that's how hallucinated sightings get invented. A name is only
    # allowed if it appears somewhere in the deterministic answer, the allowed
    # facts, or the question/claim context. Word-boundary match so "Ben" does
    # not trip on "been".
    for agent in case.agents:
        first_name = agent.full_name.split()[0].lower()
        pattern = rf"\b{re.escape(first_name)}\b"
        if re.search(pattern, text_lower) and not re.search(pattern, allowed_blob):
            return f"Contains unsupported fact: {agent.full_name.split()[0]}"

    # 6. Ungrounded violence vocabulary — the invented-confession guard.
    # A model can break character and confess on an agent's behalf ("Fine — I
    # killed him") without using any role label or authored forbidden phrase.
    # Words of killing are only allowed when the grounded text being rewritten
    # (or the visible context) already uses them — an authored confession beat
    # says "killed" and its paraphrase may too; a calm alibi answer must not
    # suddenly acquire the word. Word-boundary match so "skilled" never trips
    # "killed".
    # term -> stem: the term is allowed when its stem already appears anywhere
    # in the visible context ("murder window" in the question grounds
    # "murdered"; an authored "killed" grounds a paraphrased "kill").
    VIOLENCE_TERMS = {
        "kill": "kill", "killed": "kill", "killing": "kill",
        "murdered": "murder", "murdering": "murder",
        "strangled": "strangl", "stabbed": "stab", "poisoned": "poison",
        "i did it": "did it", "it was me": "it was me",
    }
    for term, stem in VIOLENCE_TERMS.items():
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, text_lower) and stem not in allowed_blob:
            return f"Contains ungrounded violence vocabulary: {term}"

    return None


def _format_world_state(world_state: Optional[list[str]]) -> str:
    """World-state digest lines (spec 15 Phase A). Deliberately *not* added
    to the sanitiser's allowed context: the digest is atmosphere the model
    may allude to, but parroting its specifics (another suspect's name, a
    broken claim's content) back as first-person testimony must still be
    rejected by the unsupported-fact / forbidden-fact checks."""
    if not world_state:
        return "None"
    return "- " + "\n- ".join(world_state)


def _voice_card(agent: Agent) -> str:
    return agent.voice_card or "No particular mannerisms."


# Said when the agent is about to repeat a line the player has already heard. Rotated so a long
# interrogation doesn't hear the same stock phrase twice, and tiered by how hard the player is
# pressing.
_REPEAT_OPENERS_CALM = [
    "I've told you this already.",
    "As I said before.",
    "You've asked me that.",
    "Same answer as last time.",
]
_REPEAT_OPENERS_PRESSED = [
    "I'm not going to say it differently just because you ask it twice.",
    "You can keep asking. It doesn't change.",
    "Asking again won't make it a different morning.",
    "I've given you my answer. I'll give it to you again, word for word, if that helps.",
]


def _diegetic_fallback(
    deterministic_text: str,
    pressure_level: float,
    outcome: str | None = None,
    is_repeat: bool = False,
) -> str:
    """Return the authored line, framed as an interview beat only when that is what is happening.

    This wrapper used to fire on PRESSURE: once an agent was pressed past 0.3, every subsequent
    answer was prefixed "That's all I'll say about that:" — the same phrase, every time, whether
    or not the line was new. Because the wrapper also fires whenever the LLM rewrite is simply
    unavailable (and the default config points at a host that may not exist), that is what the
    game actually did out of the box:

        Q(relationship):     "That's all I'll say about that: He was exacting..."
        Q(last_seen_victim): "That's all I'll say about that: About twenty to eight..."
        Q(alibi):            "That's all I'll say about that: I was at the fountain..."

    Three identical prefixes in a row, several of them contradicting the line they introduce.

    The wrapper's real job is to stop a REPEATED line reading as a broken feature — so it now
    fires on repetition, not on pressure. A first-time answer is new information and is returned
    exactly as authored. A `contradiction_locked` outcome is the killer breaking, and is never
    adorned.
    """
    if outcome == "contradiction_locked":
        return deterministic_text
    if not is_repeat:
        return deterministic_text

    pool = _REPEAT_OPENERS_PRESSED if pressure_level >= 0.4 else _REPEAT_OPENERS_CALM
    opener = pool[hash(deterministic_text) % len(pool)]
    return f"{opener} {deterministic_text}"


def rewrite_interview_answer(
    case: CaseData,
    agent: Agent,
    question_text: str,
    deterministic_text: str,
    allowed_facts: list[str],
    pressure_level: float,
    recent_exchange: Optional[list[str]] = None,
    emotion: str = "neutral",
    world_state: Optional[list[str]] = None,
    is_repeat: bool = False,
) -> RewriteResult:

    system_prompt = _load_prompt("dialogue_rewrite_system.txt")
    user_prompt_template = _load_prompt("interview_rewrite_user.txt")

    forbidden_facts = _build_forbidden_facts(case, agent)

    user_prompt = user_prompt_template.format(
        name=agent.full_name,
        occupation=agent.occupation,
        traits=", ".join(agent.traits),
        voice_card=_voice_card(agent),
        emotion=emotion or "neutral",
        pressure_level=pressure_level,
        question_text=question_text,
        recent_exchange="\n".join(recent_exchange) if recent_exchange else "None",
        world_state=_format_world_state(world_state),
        allowed_facts="- " + "\n- ".join(allowed_facts) if allowed_facts else "None",
        forbidden_facts="- " + "\n- ".join(forbidden_facts) if forbidden_facts else "None",
        deterministic_text=deterministic_text
    )
    
    client = get_llm_client()
    try:
        result = client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=DialogueRewrite
        )

        # Prior displayed dialogue is already on the player's screen, so
        # echoing it back is continuity, not a new leak.
        allowed_context = [question_text, deterministic_text, agent.full_name]
        if recent_exchange:
            allowed_context.extend(recent_exchange)
        rejection = _sanitise(
            result.rewritten_text, forbidden_facts, allowed_facts, case, allowed_context
        )
        if rejection:
            logger.warning(f"Rewrite rejected: {rejection}")
            return RewriteResult(
                rewritten_text=_diegetic_fallback(deterministic_text, pressure_level, is_repeat=is_repeat),
                fallback_used=True,
                fallback_reason="validation_failed"
            )

        return RewriteResult(
            rewritten_text=result.rewritten_text,
            fallback_used=False
        )

    except Exception as e:
        logger.warning(f"Rewrite failed: {e}")
        return RewriteResult(
            rewritten_text=_diegetic_fallback(deterministic_text, pressure_level, is_repeat=is_repeat),
            fallback_used=True,
            fallback_reason="provider_error"
        )


def rewrite_challenge_response(
    case: CaseData,
    agent: Agent,
    challenged_claim: str,
    evidence_clues: str,
    player_statement: str,
    outcome: str,
    deterministic_text: str,
    allowed_facts: list[str],
    pressure_level: float,
    emotion: str = "neutral",
    world_state: Optional[list[str]] = None,
) -> RewriteResult:

    system_prompt = _load_prompt("dialogue_rewrite_system.txt")
    user_prompt_template = _load_prompt("challenge_rewrite_user.txt")

    forbidden_facts = _build_forbidden_facts(case, agent)

    user_prompt = user_prompt_template.format(
        name=agent.full_name,
        occupation=agent.occupation,
        traits=", ".join(agent.traits),
        voice_card=_voice_card(agent),
        emotion=emotion or "neutral",
        pressure_level=pressure_level,
        world_state=_format_world_state(world_state),
        challenged_claim=challenged_claim,
        evidence_clues=evidence_clues,
        player_statement=player_statement or "None",
        outcome=outcome,
        allowed_facts="- " + "\n- ".join(allowed_facts) if allowed_facts else "None",
        forbidden_facts="- " + "\n- ".join(forbidden_facts) if forbidden_facts else "None",
        deterministic_text=deterministic_text
    )
    
    client = get_llm_client()
    try:
        result = client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=DialogueRewrite
        )

        allowed_context = [
            challenged_claim,
            evidence_clues,
            player_statement or "",
            deterministic_text,
            agent.full_name,
        ]
        rejection = _sanitise(
            result.rewritten_text, forbidden_facts, allowed_facts, case, allowed_context
        )
        if rejection:
            logger.warning(f"Rewrite rejected: {rejection}")
            return RewriteResult(
                rewritten_text=_diegetic_fallback(deterministic_text, pressure_level, outcome),
                fallback_used=True,
                fallback_reason="validation_failed"
            )

        return RewriteResult(
            rewritten_text=result.rewritten_text,
            fallback_used=False
        )

    except Exception as e:
        logger.warning(f"Rewrite failed: {e}")
        return RewriteResult(
            rewritten_text=_diegetic_fallback(deterministic_text, pressure_level, outcome),
            fallback_used=True,
            fallback_reason="provider_error"
        )


def _get_open_ended_deflection(pressure_level: float) -> str:
    if pressure_level >= 0.6:
        return random.choice([
            "I'm done playing these games. Stick to the point.",
            "Are you trying to be funny? Because I'm not laughing.",
            "I don't have to sit here and listen to this nonsense.",
            "Stop wasting my time with these questions."
        ])
    elif pressure_level >= 0.3:
        return random.choice([
            "I don't see what that's got to do with your investigation, detective.",
            "I'd rather stick to the matter at hand, if you don't mind.",
            "Is that really relevant right now?",
            "Let's stay focused on the case, shall we?"
        ])
    else:
        return random.choice([
            "I'm sorry, my mind is a bit elsewhere with everything that's happened.",
            "I'm not quite sure what you mean.",
            "Hmm, I don't really know what to say to that.",
            "I'm afraid I don't have a good answer for that right now."
        ])


def generate_open_ended_response(
    case: CaseData,
    agent: Agent,
    question_text: str,
    pressure_level: float,
    recent_exchange: Optional[list[str]] = None,
    world_state: Optional[list[str]] = None,
) -> RewriteResult:
    """Handles free-text questions that match none of the fixed interview
    intents (spec 06) — e.g. "tell me about your childhood". Rather than a
    static "I don't understand" message, lets the LLM improvise a genuinely
    in-character reply: flavour when the topic is harmless, an in-character
    refusal when it reaches for hidden case truth. There is no deterministic
    ground truth to rewrite here, so the model is never given the case truth
    as context — only the same forbidden-facts list and the same sanitiser
    used for grounded rewrites, which is what still blocks a leak or an
    invented relationship to another named suspect."""

    system_prompt = _load_prompt("open_ended_system.txt")
    user_prompt_template = _load_prompt("open_ended_user.txt")

    forbidden_facts = _build_forbidden_facts(case, agent)

    user_prompt = user_prompt_template.format(
        name=agent.full_name,
        occupation=agent.occupation,
        traits=", ".join(agent.traits),
        voice_card=_voice_card(agent),
        routine_summary=agent.routine_summary or "Unknown",
        pressure_level=pressure_level,
        recent_exchange="\n".join(recent_exchange) if recent_exchange else "None",
        world_state=_format_world_state(world_state),
        forbidden_facts="- " + "\n- ".join(forbidden_facts) if forbidden_facts else "None",
        question_text=question_text,
    )

    client = get_llm_client()
    try:
        result = client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=DialogueRewrite,
        )

        allowed_context = [question_text, agent.full_name]
        if recent_exchange:
            allowed_context.extend(recent_exchange)
        rejection = _sanitise(result.rewritten_text, forbidden_facts, [], case, allowed_context)
        if rejection:
            logger.warning(f"Open-ended response rejected: {rejection}")
            return RewriteResult(
                rewritten_text=_get_open_ended_deflection(pressure_level),
                fallback_used=True,
                fallback_reason="validation_failed",
            )

        return RewriteResult(rewritten_text=result.rewritten_text, fallback_used=False)

    except Exception as e:
        logger.warning(f"Open-ended response failed: {e}")
        return RewriteResult(
            rewritten_text=_get_open_ended_deflection(pressure_level),
            fallback_used=True,
            fallback_reason="provider_error",
        )
