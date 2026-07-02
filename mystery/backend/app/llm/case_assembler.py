"""Converts an LLM CasePlan into a valid CaseData object."""

import json
import random
from typing import Dict, List, Any
from copy import deepcopy

from ..models import CaseData, CaseFile, Agent, Location, GameObject, SeededMemory, Event, Clue, Conclusion, AgentInterviewPack, ChallengeRule, Solution, Discoverability, AnswerRule
from .schemas import CasePlan

def assemble_case(
    plan: CasePlan,
    base_case_data: CaseData,
    roles: Dict[str, str],
    seed: int
) -> CaseData:
    """
    Assembles a CaseData from an LLM CasePlan by injecting the flavour into the 
    deterministic scaffold (base_case_data) which already has roles substituted.
    """
    # Create a deep copy to avoid mutating the base template
    case_data = deepcopy(base_case_data)
    rng = random.Random(seed)
    
    # 1. Update Case Overview & Title
    case_data.case.title = plan.title
    case_data.case.motive_summary = plan.motive_variant
    
    # 2. Update Solution Text
    case_data.solution.explanation = plan.reveal_narration
    case_data.solution.motive.canonical = plan.killer_rationale
    
    # 3. Add Seeded Memories
    # The deterministic scaffold might have its own memories, we can replace or append.
    # Let's replace them to use the LLM's rich memories.
    new_memories = []
    for i, mem_plan in enumerate(plan.seeded_memories):
        owner_id = roles.get(mem_plan.owner_role, mem_plan.owner_role)
        known_by = [roles.get(r, r) for r in mem_plan.known_by_roles]
        
        new_memories.append(SeededMemory(
            memory_id=f"mem_llm_{i}",
            owner_agent_id=owner_id,
            memory_type=mem_plan.memory_type, # e.g. 'secret', 'observation'
            truth_status=mem_plan.truth_status, # e.g. 'true', 'false'
            case_function=mem_plan.case_function, # e.g. 'motive', 'alibi'
            summary=mem_plan.summary,
            known_by_agent_ids=known_by
        ))
    case_data.memories = new_memories
    
    # 4. We keep the deterministic Clues and Events because they form the hard puzzle logic.
    # But we can UPDATE the descriptions of the clues based on LLM plans if they match,
    # or just ADD the LLM clues as extra flavor clues.
    # For a robust MVP, we'll append the LLM clues as flavor (if they don't break validation)
    # The validator requires every clue to have valid references.
    locations = [l.location_id for l in case_data.locations]
    
    for i, clue_plan in enumerate(plan.clue_plans):
        linked_agent_id = roles.get(clue_plan.linked_role, clue_plan.linked_role)
        
        # We need a valid discovery method. "observation" would require linking
        # the clue to a visible event, which the assembler cannot invent, so it
        # maps to "inspect" rather than guaranteeing a validation failure. The
        # same applies to interview clues linked to someone with no interview
        # pack (e.g. the victim).
        method = clue_plan.discovery_method if clue_plan.discovery_method in ["inspect", "interview"] else "inspect"
        if method == "interview" and not any(
            p.agent_id == linked_agent_id for p in case_data.interview_packs
        ):
            method = "inspect"

        discoverability = Discoverability(method=method)
        if method == "inspect":
            discoverability.location_id = rng.choice(locations)
        elif method == "interview":
            discoverability.agent_id = linked_agent_id
            discoverability.question_type = "timeline"

            # Inject an AnswerRule into the agent's interview pack
            for pack in case_data.interview_packs:
                if pack.agent_id == linked_agent_id:
                    pack.rules.append(AnswerRule(
                        question_type="timeline",
                        answer_text=clue_plan.player_facing_description,
                        reveals_clue_ids=[f"clue_llm_{i}"]
                    ))
            
        new_clue = Clue(
            clue_id=f"clue_llm_{i}",
            title=clue_plan.player_facing_description[:30] + "...",
            clue_type=clue_plan.clue_type,
            description=clue_plan.player_facing_description,
            strength="medium",
            reliability=0.8,
            ambiguity=clue_plan.ambiguity_level,
            discoverability=discoverability,
            supports_conclusion_ids=[], # Can't blindly map to deterministic conclusions without risk
            linked_agent_ids=[linked_agent_id] if linked_agent_id in [a.agent_id for a in case_data.agents] else []
        )
        case_data.clues.append(new_clue)

    # 5. Witness Fragments
    # We can inject these into the agent interview packs
    for frag in plan.witness_fragments:
        agent_id = roles.get(frag.witness_role, frag.witness_role)
        for pack in case_data.interview_packs:
            if pack.agent_id == agent_id:
                pack.default_answers["timeline"] = frag.observation_summary

    # 6. Interview Flavour
    # Map interview_flavour dictionary
    for role_key, flavours in plan.interview_flavour.items():
        agent_id = roles.get(role_key, role_key)
        for pack in case_data.interview_packs:
            if pack.agent_id == agent_id:
                # Update fallback text or rules if we want to be fancy
                if "general" in flavours:
                    pack.default_answers["relationship"] = flavours["general"]
                    
    # Return assembled case data
    return case_data
