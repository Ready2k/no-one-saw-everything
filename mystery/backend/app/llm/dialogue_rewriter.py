"""LLM dialogue rewriting module."""

import json
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
    for fact in forbidden_facts:
        if len(fact) > 10 and fact.lower() in text_lower:
            return f"Contains forbidden fact: {fact}"

    # 5. Unsupported facts
    # The rewrite may not introduce cast members that the grounded answer never
    # mentioned — that's how hallucinated sightings get invented. A name is only
    # allowed if it appears somewhere in the deterministic answer, the allowed
    # facts, or the question/claim context. Word-boundary match so "Ben" does
    # not trip on "been".
    allowed_blob = " ".join(allowed_facts + allowed_context).lower()
    for agent in case.agents:
        first_name = agent.full_name.split()[0].lower()
        pattern = rf"\b{re.escape(first_name)}\b"
        if re.search(pattern, text_lower) and not re.search(pattern, allowed_blob):
            return f"Contains unsupported fact: {agent.full_name.split()[0]}"

    return None


def rewrite_interview_answer(
    case: CaseData,
    agent: Agent,
    question_text: str,
    deterministic_text: str,
    allowed_facts: list[str],
    pressure_level: float
) -> RewriteResult:
    
    system_prompt = _load_prompt("dialogue_rewrite_system.txt")
    user_prompt_template = _load_prompt("interview_rewrite_user.txt")
    
    forbidden_facts = _build_forbidden_facts(case, agent)
    
    user_prompt = user_prompt_template.format(
        name=agent.full_name,
        occupation=agent.occupation,
        traits=", ".join(agent.traits),
        emotion="neutral",
        pressure_level=pressure_level,
        question_text=question_text,
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

        allowed_context = [question_text, deterministic_text, agent.full_name]
        rejection = _sanitise(
            result.rewritten_text, forbidden_facts, allowed_facts, case, allowed_context
        )
        if rejection:
            logger.warning(f"Rewrite rejected: {rejection}")
            return RewriteResult(
                rewritten_text=deterministic_text,
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
            rewritten_text=deterministic_text,
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
    pressure_level: float
) -> RewriteResult:
    
    system_prompt = _load_prompt("dialogue_rewrite_system.txt")
    user_prompt_template = _load_prompt("challenge_rewrite_user.txt")
    
    forbidden_facts = _build_forbidden_facts(case, agent)
    
    user_prompt = user_prompt_template.format(
        name=agent.full_name,
        occupation=agent.occupation,
        traits=", ".join(agent.traits),
        emotion="neutral",
        pressure_level=pressure_level,
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
                rewritten_text=deterministic_text,
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
            rewritten_text=deterministic_text,
            fallback_used=True,
            fallback_reason="provider_error"
        )
