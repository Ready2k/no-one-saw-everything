"""Converts an LLM CasePlan into a valid CaseData object."""

# import json  # UNUSED — commented out during code review [2026-07-19]
import random
import re
from typing import Dict, List, Any
from copy import deepcopy

from ..models import CaseData, CaseFile, Agent, Location, SeededMemory, Event, Clue, AgentInterviewPack, Discoverability, AnswerRule
# UNUSED — commented out during code review [2026-07-19]
# from ..models import GameObject, Conclusion, ChallengeRule, Solution
from .schemas import CasePlan

def resolve_role(role_key: str, roles: Dict[str, str]) -> str:
    if not role_key:
        return role_key
    if role_key in roles:
        return roles[role_key]
    braced = f"{{{role_key}}}"
    if braced in roles:
        return roles[braced]
    stripped = role_key.strip("{}")
    for k, v in roles.items():
        if k.strip("{}") == stripped:
            return v
    return role_key

def normalize_memory_type(val: str) -> str:
    val = val.lower().strip()
    allowed = {"private_secret", "shared_secret", "rumour", "witness_fragment", "false_belief", "deliberate_lie", "innocent_secret", "observed", "cover_story"}
    if val in allowed:
        return val
    if "secret" in val:
        return "private_secret"
    if "lie" in val:
        return "deliberate_lie"
    if "witness" in val or "fragment" in val:
        return "witness_fragment"
    if "observe" in val:
        return "observed"
    if "rumor" in val or "rumour" in val:
        return "rumour"
    return "private_secret"

def normalize_truth_status(val: str) -> str:
    val = val.lower().strip()
    allowed = {"true", "false", "mistaken", "rumour", "unknown"}
    if val in allowed:
        return val
    if "true" in val or "correct" in val:
        return "true"
    if "false" in val or "lie" in val:
        return "false"
    if "mistake" in val:
        return "mistaken"
    if "rumor" in val or "rumour" in val:
        return "rumour"
    return "true"

def normalize_ambiguity(val: str) -> str:
    val = val.lower().strip()
    if val in {"low", "medium", "high"}:
        return val
    if "low" in val:
        return "low"
    if "high" in val:
        return "high"
    return "medium"

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
    case_data.case.weather = plan.weather
    case_data.case.weather_intensity = plan.weather_intensity
    case_data.case.wind = plan.wind
    
    # Resolve murder location name
    murder_loc_name = "the room"
    for loc in case_data.locations:
        if loc.location_id == case_data.case.murder_location_id:
            murder_loc_name = loc.name
            break
            
    # Resolve discoverer name
    discoverer_name = "someone"
    for agent in case_data.agents:
        if agent.agent_id == case_data.case.discovered_by:
            discoverer_name = agent.full_name
            break
            
    # Substitute placeholders in scene_description. Small local models don't
    # always use the exact '{name}' syntax requested in the prompt (observed:
    # '<discovered_by_name>' with angle brackets instead) so both forms are
    # accepted here.
    desc = plan.scene_description
    for victim_ph in ("{VICTIM_NAME}", "<VICTIM_NAME>", "<victim_name>"):
        desc = desc.replace(victim_ph, roles.get("{VICTIM_NAME}", "the victim"))
    for weapon_ph in ("{WEAPON_NAME}", "<WEAPON_NAME>", "<weapon_name>"):
        desc = desc.replace(weapon_ph, roles.get("{WEAPON_NAME}", "the weapon"))
    for loc_ph in ("{murder_location}", "<murder_location>"):
        desc = desc.replace(loc_ph, murder_loc_name)
    for disc_ph in ("{discovered_by_name}", "<discovered_by_name>"):
        desc = desc.replace(disc_ph, discoverer_name)

    # Also replace any other roles that might be mentioned (e.g. {KILLER_NAME})
    for placeholder, val in roles.items():
        desc = desc.replace(placeholder, val)
        stripped = placeholder.strip("{}")
        desc = desc.replace(stripped, val)

    # Guard against a non-compliant LLM: sometimes it ignores the
    # {murder_location}/{WEAPON_NAME} placeholders entirely and invents its own
    # room/weapon flavour instead (observed: "...the air of the 'Vanderbilt
    # Gallery'..." while the real location was "Cafe Storage Room" — the
    # placeholder never appears, so the substitution above is a no-op and the
    # invented name survives), or leaves an unrecognised placeholder token
    # (any form the two loops above didn't already handle) verbatim in the
    # text. Detect either case by checking the real facts actually ended up
    # in the text and that no bracketed token remains; if not, fall back to
    # the deterministic, always grounded description already computed on the
    # scaffold instead of shipping prose that contradicts the rest of the
    # case or leaks a raw placeholder to the player.
    weapon_name = roles.get("{WEAPON_NAME}", "")
    location_ok = murder_loc_name.lower() in desc.lower()
    weapon_ok = (not weapon_name) or (weapon_name.lower() in desc.lower())
    no_leftover_placeholders = not re.search(r"[{<][A-Za-z_]+[}>]", desc)
    if not (location_ok and weapon_ok and no_leftover_placeholders) and base_case_data.case.overview_text:
        desc = base_case_data.case.overview_text

    case_data.case.scene_description = desc
    case_data.case.overview_text = desc
    
    # 2. Update Solution Text
    case_data.solution.explanation = plan.reveal_narration
    case_data.solution.motive.canonical = plan.killer_rationale
    
    # 3. Add Seeded Memories
    # The deterministic scaffold might have its own memories, we can replace or append.
    # Let's replace them to use the LLM's rich memories.
    new_memories = []
    killer_agent_id = roles.get("{KILLER_ID}")
    killer_req_funcs = ["killer_motive", "opportunity_setup", "false_alibi_reason"]
    killer_mem_count = 0
    
    valid_agent_ids = [a.agent_id for a in case_data.agents]
    for i, mem_plan in enumerate(plan.seeded_memories):
        owner_id = resolve_role(mem_plan.owner_role, roles)
        if owner_id not in valid_agent_ids:
            owner_id = killer_agent_id

        known_by = [resolve_role(r, roles) for r in mem_plan.known_by_roles]
        known_by = [r for r in known_by if r in valid_agent_ids]
        if not known_by:
            known_by = [owner_id]
        
        # Normalize enums
        m_type = normalize_memory_type(mem_plan.memory_type)
        t_status = normalize_truth_status(mem_plan.truth_status)
        
        # Enforce killer memory seeds required by validator, map others safely
        if owner_id == killer_agent_id:
            if killer_mem_count < len(killer_req_funcs):
                case_function = killer_req_funcs[killer_mem_count]
            else:
                case_function = "clue_support"
            killer_mem_count += 1
        elif owner_id in (roles.get("{RH1_ID}"), roles.get("{RH2_ID}")):
            case_function = "red_herring_motive"
        else:
            case_function = "clue_support"
            
        new_memories.append(SeededMemory(
            memory_id=f"mem_llm_{i}",
            owner_agent_id=owner_id,
            memory_type=m_type,
            truth_status=t_status,
            case_function=case_function,
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
        linked_agent_id = resolve_role(clue_plan.linked_role, roles)
        if linked_agent_id not in valid_agent_ids:
            linked_agent_id = killer_agent_id
        
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
            ambiguity=normalize_ambiguity(clue_plan.ambiguity_level),
            discoverability=discoverability,
            supports_conclusion_ids=[], # Can't blindly map to deterministic conclusions without risk
            linked_agent_ids=[linked_agent_id] if linked_agent_id in valid_agent_ids else []
        )
        case_data.clues.append(new_clue)

    # 5. Witness Fragments
    # We can inject these into the agent interview packs
    for frag in plan.witness_fragments:
        agent_id = resolve_role(frag.witness_role, roles)
        for pack in case_data.interview_packs:
            if pack.agent_id == agent_id:
                pack.default_answers["timeline"] = frag.observation_summary

    # 6. Interview Flavour
    # Map interview_flavour dictionary
    for role_key, flavours in plan.interview_flavour.items():
        agent_id = resolve_role(role_key, roles)
        for pack in case_data.interview_packs:
            if pack.agent_id == agent_id:
                # Update fallback text or rules if we want to be fancy
                if "general" in flavours:
                    pack.default_answers["relationship"] = flavours["general"]

    # 7. Timeline — replace the template's events and per-agent routines with a
    # freshly compiled morning when the LLM authored one. Absent/empty => the
    # template events are kept (the no-regression fallback). Imported lazily to
    # avoid a circular import (timeline_compiler reuses resolve_role here).
    if plan.timeline and (plan.timeline.beats or plan.timeline.routines):
        from .timeline_compiler import compile_timeline
        compile_timeline(plan.timeline, case_data, roles, seed)

    # Return assembled case data
    return case_data
