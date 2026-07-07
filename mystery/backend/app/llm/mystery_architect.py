"""Orchestrates LLM generation, assembly, validation, and repair."""

import json
import logging
from pathlib import Path

from ..models import CaseData
from .schemas import CasePlan, PlotOutlinePlan, CluesPlan, MemoriesPlan, FlavourPlan
from .client import get_llm_client
from .case_assembler import assemble_case
from ..validator import validate_case

logger = logging.getLogger(__name__)

MAX_LLM_REPAIR_ATTEMPTS = 3

PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text()

def generate_llm_case(
    base_case_data: CaseData,
    roles: dict[str, str],
    case_type: str,
    difficulty: str,
    seed: int,
    custom_theme: str | None = None,
    tone: str | None = None,
    llm_notes: str | None = None,
    num_suspects: int | None = None,
    num_locations: int | None = None
) -> tuple[CaseData | None, str | None, int]:
    """
    1. Calls LLM to generate CasePlan
    2. Assembles CaseData
    3. Validates CaseData
    4. Repeats (repair) if invalid up to max attempts
    
    Returns: (assembled_case, fallback_reason, repair_attempts)
    """
    from .config import get_llm_config
    config = get_llm_config()
    if not config.configured:
        return None, config.fallback_reason or "llm_not_configured", 0

    client = get_llm_client()
    
    # Phase 1: Plot Outline
    import random
    rng = random.Random(seed)
    sub_themes = [
        "A hidden romantic affair gone wrong",
        "A secret gambling debt",
        "A dispute over a stolen antique",
        "Blackmail regarding a past crime",
        "A bitter inheritance dispute",
        "A forged document or fraud",
        "A petty rivalry that escalated too far",
        "A dark secret from their childhood",
    ]
    if custom_theme and custom_theme.strip():
        theme = custom_theme.strip()
    else:
        theme = rng.choice(sub_themes)
        
    tone_instruction = ""
    if tone == "family_friendly":
        tone_instruction = (
            "Content Safety / Tone requirement: FAMILY FRIENDLY. The case must be cozy, light-hearted, "
            "and suitable for all ages. Avoid any explicit or gory descriptions of the murder scene or body. "
            "Motive and background secrets should be non-violent, non-graphic (e.g. business rivalry, simple secrets, "
            "rather than gruesome crimes)."
        )
    elif tone == "dark_noir":
        tone_instruction = (
            "Content Safety / Tone requirement: DARK NOIR. The case should have a gritty, suspenseful, and mature "
            "detective noir aesthetic. It can feature darker psychological themes, realistic alibi tension, complex "
            "secrets, and a cynical alibi web. Embrace atmospheric tension. Avoid any explicit gore, graphic violence, or sexual content."
        )
    else:
        tone_instruction = (
            "Content Safety / Tone requirement: STANDARD murder mystery. Classic fair-play detective style."
        )

    loc_instruction = ""
    if num_locations is not None:
        loc_instruction = f"Constraint: The mystery must take place across exactly {num_locations} active locations. Avoid references to additional locations."

    notes_instruction = ""
    if llm_notes and llm_notes.strip():
        notes_instruction = (
            f"CRITICAL: The player has specified these custom guidelines and plot notes. "
            f"You MUST strictly follow and integrate them into the mystery plot and details:\n{llm_notes.strip()}"
        )

    # Determine allowed roles based on num_suspects
    allowed_roles = ["{VICTIM_ID}", "{KILLER_ID}", "{RH1_ID}", "{RH2_ID}"]
    if num_suspects is not None:
        witness_roles = ["{WITNESS1_ID}", "{WITNESS2_ID}", "{WITNESS3_ID}", "{WITNESS4_ID}"]
        needed_witnesses = max(0, num_suspects - 3)
        allowed_roles.extend(witness_roles[:needed_witnesses])
    else:
        allowed_roles.extend(["{WITNESS1_ID}", "{WITNESS2_ID}", "{WITNESS3_ID}", "{WITNESS4_ID}"])
    
    allowed_roles_str = ", ".join(allowed_roles)
    
    messages = [
        {"role": "system", "content": "You are a creative murder mystery architect writing a case for a detective game."},
        {"role": "user", "content": f"""Generate a murder mystery plot outline of type '{case_type}' and difficulty '{difficulty}'.
The core motive and plot MUST revolve around this theme: '{theme}'.

{tone_instruction}

{loc_instruction}

{notes_instruction}

Allowed roles to reference: {allowed_roles_str}.
Do NOT reference or assign alibis/memories to roles outside this list.

Define the following outline details in a JSON response:
- title: A fitting title for the mystery.
- motive_variant: A brief explanation of the motive.
- victim_rationale: Why the victim was killed.
- killer_rationale: Why the killer did it.
- red_herring_rationales: A dictionary mapping '{{RH1_ID}}' and '{{RH2_ID}}' to their suspicious but innocent rationales (if they are in the allowed roles list).
- scene_description: A paragraph explaining the discovery of the body. You MUST use the following placeholders instead of hardcoding names, locations, or weapons:
  * '{{VICTIM_NAME}}' for the victim's name.
  * '{{WEAPON_NAME}}' for the weapon used.
  * '{{murder_location}}' for the room where the body was found.
  * '{{discovered_by_name}}' for the person who discovered the body.
  '{{murder_location}}' will be substituted with this case's real location name (e.g. "Reed & Bell Bookshop" or "Priya's Flat") — it is NOT necessarily a manor, mansion, library, or study. Do NOT invent your own room type, building description, or synonym for the murder scene (no "grand old manor", "dimly lit library", "drawing room", etc.) — refer to the scene ONLY via the '{{murder_location}}' placeholder, exactly once, with no other descriptor of what kind of room or building it is. Likewise do not invent a synonym for the weapon; refer to it ONLY via '{{WEAPON_NAME}}'.

Format the output strictly as a JSON object matching the required schema."""}
    ]
    
    try:
        plot_plan = client.generate_chat(messages=messages, schema=PlotOutlinePlan, temperature=0.8)
        messages.append({"role": "assistant", "content": plot_plan.model_dump_json()})
    except Exception as e:
        logger.error(f"LLM plot generation failed: {e}")
        return None, "provider_error", 0

    # Phase 2: Clue Plans
    messages.append({"role": "user", "content": f"""Based on the plot outline, generate 5 clue plans.
Allowed roles to reference: {allowed_roles_str}
Allowed clue types: document, physical_evidence, observation, witness_statement, confession, object_trail
Allowed discovery methods: inspect, observation, interview

Rules:
1. Every critical conclusion (motive, means, opportunity) needs discoverable clues.
2. Every red herring needs an innocence anchor.
3. Keep clue text and descriptions player-facing and relatively ambiguous (do not reveal the murder outright).

Format the output strictly as a JSON object matching the required schema."""})
    
    try:
        clues_plan = client.generate_chat(messages=messages, schema=CluesPlan, temperature=0.7)
        messages.append({"role": "assistant", "content": clues_plan.model_dump_json()})
    except Exception as e:
        logger.error(f"LLM clues generation failed: {e}")
        return None, "provider_error", 0

    # Phase 3: Seeded Memories and Witness Fragments
    messages.append({"role": "user", "content": f"""Based on the plot and clue plans, generate the seeded memories and witness fragments.

CRITICAL RULES FOR MEMORIES:
1. The killer suspect ({{KILLER_ID}}) MUST have exactly three memories assigned with these case_function values:
   - "killer_motive": The memory establishing the true motive.
   - "opportunity_setup": The memory establishing how/when they entered the scene or opportunity.
   - "false_alibi_reason": The memory establishing their false alibi or why they lied about their whereabouts.
2. Other suspects/roles (e.g. {{RH1_ID}}, {{RH2_ID}}) can have memories with these case_function values:
   - "red_herring_motive", "innocence_anchor", "clue_support", "false_alibi_support", "victim_trigger", "killer_trigger".
3. memory_type must be one of: "private_secret", "shared_secret", "rumour", "witness_fragment", "false_belief", "deliberate_lie", "innocent_secret", "observed", "cover_story".
4. truth_status must be one of: "true", "false", "mistaken", "rumour", "unknown".

Ensure only allowed roles ({allowed_roles_str}) are referenced.

Format the output strictly as a JSON object matching the required schema."""})

    try:
        memories_plan = client.generate_chat(messages=messages, schema=MemoriesPlan, temperature=0.7)
    except Exception as e:
        logger.error(f"LLM memories generation failed: {e}")
        return None, "provider_error", 0

    # Phase 4: Interview Flavour and Reveal Narration
    flavour_messages = [
        {"role": "system", "content": "You are a creative murder mystery architect writing a case for a detective game."},
        {"role": "user", "content": f"""We have the following plot outline:
{plot_plan.model_dump_json()}

Generate the interview flavour and final reveal narration.
Allowed roles: {allowed_roles_str}

Rules:
1. interview_flavour maps suspect roles (e.g. {{KILLER_ID}}) to a dict containing a 'general' key with a string value describing their attitude/relationship.
2. The values under each role in interview_flavour MUST be simple string values (e.g. 'general': 'text'). Do NOT use lists for values.
3. reveal_narration is a paragraph describing how the mystery is resolved upon accusation.

Format the output strictly as a JSON object matching the required schema."""}
    ]
    try:
        flavour_plan = client.generate_chat(messages=flavour_messages, schema=FlavourPlan, temperature=0.5)
    except Exception as e:
        logger.error(f"LLM flavour generation failed: {e}")
        return None, "provider_error", 0

    try:
        merged_dict = {
            "case_type": case_type,
            "title": plot_plan.title,
            "motive_variant": plot_plan.motive_variant,
            "victim_rationale": plot_plan.victim_rationale,
            "killer_rationale": plot_plan.killer_rationale,
            "red_herring_rationales": plot_plan.red_herring_rationales,
            "scene_description": plot_plan.scene_description,
            "clue_plans": [c.model_dump() for c in clues_plan.clue_plans],
            "seeded_memories": [m.model_dump() for m in memories_plan.seeded_memories],
            "witness_fragments": [w.model_dump() for w in memories_plan.witness_fragments],
            "interview_flavour": flavour_plan.interview_flavour,
            "reveal_narration": flavour_plan.reveal_narration
        }
        plan = CasePlan.model_validate(merged_dict)
    except Exception as e:
        logger.error(f"CasePlan validation failed on merged dictionary: {e}")
        return None, "validation_failed", 0


        
    for attempt in range(MAX_LLM_REPAIR_ATTEMPTS + 1):
        # Assemble
        assembled_case = assemble_case(plan, base_case_data, roles, seed)
        
        # Validate
        val_result = validate_case(assembled_case)
        if val_result["valid"]:
            return assembled_case, None, attempt
            
        logger.warning(f"LLM Case validation failed on attempt {attempt}: {val_result['errors']}")
        
        if attempt == MAX_LLM_REPAIR_ATTEMPTS:
            return None, "repair_exhausted", attempt
            
        # Repair
        repair_sys = load_prompt("repair_system")
        repair_user = load_prompt("repair_user").format(
            errors=json.dumps(val_result["errors"], indent=2),
            original_plan=plan.model_dump_json(indent=2),
            VICTIM_ID="{VICTIM_ID}",
            KILLER_ID="{KILLER_ID}",
            RH1_ID="{RH1_ID}",
            RH2_ID="{RH2_ID}",
            WITNESS1_ID="{WITNESS1_ID}",
            WITNESS2_ID="{WITNESS2_ID}",
            WITNESS3_ID="{WITNESS3_ID}",
            WITNESS4_ID="{WITNESS4_ID}"
        )
        
        try:
            plan = client.generate_json(
                system_prompt=repair_sys,
                user_prompt=repair_user,
                schema=CasePlan,
                temperature=0.2
            )
        except Exception as e:
            logger.error(f"LLM repair failed: {e}")
            return None, "provider_error", attempt
        
    return None, "repair_exhausted", MAX_LLM_REPAIR_ATTEMPTS
