"""LLM dialogue rewriting module."""

import json
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


def _diegetic_fallback(deterministic_text: str, pressure_level: float) -> str:
    """Frames a fallback-to-deterministic-text as the character deliberately
    clamming up, rather than an invisible swap back to the exact same line
    the player may have already seen — so a rejected/unavailable rewrite
    reads as an interview beat, not a broken feature. Pressure-tiered so it
    isn't the same single stock phrase every time.
    
    At low pressure, we return the text unadorned so that if the LLM is
    entirely disconnected, regular conversation doesn't become repetitive."""
    if pressure_level >= 0.6:
        opener = "I'm not saying anything more than this:"
        return f"{opener} {deterministic_text}"
    elif pressure_level >= 0.3:
        opener = "That's all I'll say about that:"
        return f"{opener} {deterministic_text}"
    
    return deterministic_text


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
                rewritten_text=_diegetic_fallback(deterministic_text, pressure_level),
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
            rewritten_text=_diegetic_fallback(deterministic_text, pressure_level),
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
                rewritten_text=_diegetic_fallback(deterministic_text, pressure_level),
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
            rewritten_text=_diegetic_fallback(deterministic_text, pressure_level),
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
            "I'm not sure how to answer that.",
            "I don't think I follow.",
            "I'm afraid I can't help you with that.",
            "I don't really know what you're talking about."
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
