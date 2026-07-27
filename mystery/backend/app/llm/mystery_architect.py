"""Orchestrates LLM generation, assembly, validation, and repair."""

import json
import logging
from pathlib import Path

from ..models import CaseData
from .schemas import CasePlan, PlotOutlinePlan, CluesPlan, MemoriesPlan, RoleMemoriesPlan, WitnessFragmentsPlan, FlavourPlan, CharacterIdentitiesPlan, TimelinePlan
from .client import get_llm_client
from .case_assembler import assemble_case
from .reference_scenarios import REFERENCE_SCENARIOS, format_reference_scenarios
from ..validator import validate_case

logger = logging.getLogger(__name__)

MAX_LLM_REPAIR_ATTEMPTS = 3
MAX_LLM_CALL_RETRIES = 2  # extra attempts beyond the first, for transient truncated/malformed JSON

PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text()

def _part_of_day(hhmm: str) -> str:
    """Which part of the day a case runs in, from its sim_start_time.

    Cases are not all mornings: case_004 starts at 22:00, case_006 at 18:00. The timeline
    prompt is written around this so the LLM stops authoring breakfast beats into a midnight
    case (and witnesses stop saying "this morning" after a murder at 23:14).
    """
    try:
        hour = int(hhmm.split(":")[0])
    except (ValueError, IndexError):
        return "morning"
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def _condensed_plot_summary(plot_plan: PlotOutlinePlan) -> dict:
    """Trimmed recap of the plot phase to carry into later prompts.
    Drops scene_description (long narrative prose not needed for
    memory/clue consistency) to keep the growing conversation within the
    context budget of small local models."""
    return {
        "title": plot_plan.title,
        "motive_variant": plot_plan.motive_variant,
        "victim_rationale": plot_plan.victim_rationale,
        "killer_rationale": plot_plan.killer_rationale,
        "red_herring_rationales": plot_plan.red_herring_rationales,
    }


def _condensed_clues_summary(clues_plan: CluesPlan) -> list[dict]:
    """Trimmed recap of the clue phase to carry into later prompts.
    Drops player_facing_description and ambiguity_level (prose fields not
    needed for memory generation) so the memories phase — the largest and
    most context-hungry call — has more room left in the model's context
    window for its own output."""
    return [
        {
            "linked_role": c.linked_role,
            "clue_type": c.clue_type,
            "supports_conclusion_type": c.supports_conclusion_type,
            "discovery_method": c.discovery_method,
        }
        for c in clues_plan.clue_plans
    ]


def call_with_retry(client, *, messages, schema, temperature, phase: str):
    """Local/small LLMs occasionally return truncated or schema-incomplete JSON
    (observed: EOF mid-string, missing required fields on later array items).
    A single retry with an identical request usually succeeds, so retry a few
    times before letting the caller fall back to the deterministic template."""
    last_error: Exception | None = None
    for attempt in range(MAX_LLM_CALL_RETRIES + 1):
        try:
            return client.generate_chat(messages=messages, schema=schema, temperature=temperature)
        except Exception as e:
            last_error = e
            if attempt < MAX_LLM_CALL_RETRIES:
                logger.warning(f"LLM {phase} generation attempt {attempt + 1} failed, retrying: {e}")
    raise last_error

IDENTITY_ROLE_NAMES = ["VICTIM", "KILLER", "RH1", "RH2", "WITNESS1", "WITNESS2", "WITNESS3", "WITNESS4"]


def generate_character_identities(
    case_type: str,
    seed: int,
    custom_theme: str | None = None,
    tone: str | None = None,
) -> dict[str, "CharacterIdentity"] | None:
    """Best-effort cast generation, called before the deterministic template
    is filled in so a fresh name/occupation per role threads through every
    mention in the case (interviews, memories, events) rather than only the
    handful of fields the later CasePlan phases rewrite. Returns None on any
    failure — the caller falls back to the fixed case_001 cast, since a
    generic cast is a cosmetic degradation, not worth failing generation over."""
    from .config import get_llm_config
    config = get_llm_config()
    if not config.configured:
        return None

    client = get_llm_client()
    theme = custom_theme.strip() if custom_theme and custom_theme.strip() else case_type
    roles_str = ", ".join(IDENTITY_ROLE_NAMES)

    messages = [
        {"role": "system", "content": "You are a creative murder mystery architect writing a case for a detective game."},
        {"role": "user", "content": f"""Invent a fresh cast of 8 distinct characters for a murder mystery of type '{case_type}' (theme: '{theme}').

Roles: {roles_str}. VICTIM is the murder victim, KILLER is the murderer, RH1/RH2 are innocent red herring suspects, WITNESS1-4 are witnesses/bystanders.

For each role, invent a full_name (first and last name, no two characters sharing a last name) and an occupation appropriate to a small-town murder mystery. Do not reuse names from any other well-known story.

Format the output strictly as a JSON object matching the required schema, with an "identities" field mapping each role name (e.g. "VICTIM") to {{"full_name": ..., "occupation": ...}}."""}
    ]

    try:
        plan = call_with_retry(client, messages=messages, schema=CharacterIdentitiesPlan, temperature=0.9, phase="identities")
        return plan.identities
    except Exception as e:
        logger.warning(f"LLM character identity generation failed, using default cast: {e}")
        return None


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
    reference_scenarios_block = format_reference_scenarios(case_type)

    messages = [
        {"role": "system", "content": "You are a creative murder mystery architect writing a case for a detective game."},
        {"role": "user", "content": f"""Generate a murder mystery plot outline of type '{case_type}' and difficulty '{difficulty}'.
The core motive and plot MUST revolve around this theme: '{theme}'.

Below are {len(REFERENCE_SCENARIOS.get(case_type, REFERENCE_SCENARIOS['blackmail']))} reference scenarios showing different shapes a '{case_type}' plot can take. They are INSPIRATION ONLY — do not copy their titles, names, or exact wording. Invent your own fresh scenario that fits the '{case_type}' spirit but differs from all of them in its specifics:

{reference_scenarios_block}

{tone_instruction}

{loc_instruction}

{notes_instruction}

Allowed roles to reference: {allowed_roles_str}.
Do NOT reference or assign alibis/memories to roles outside this list.

Define the following outline details in a JSON response:
- title: A fitting title for the mystery.
- weather: Choose exactly one renderable case condition: clear, overcast, rain, fog, wind, storm, snow, or slush. It must be plausible for the timeline and may influence only believable observations (visibility, wet surfaces, drifting papers, footprints, etc.).
- weather_intensity: light, moderate, or heavy.
- wind: calm, breezy, or strong. Use calm for snow/slush unless the scene genuinely requires otherwise.
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
        plot_plan = call_with_retry(client, messages=messages, schema=PlotOutlinePlan, temperature=0.8, phase="plot")
        messages.append({"role": "assistant", "content": json.dumps(_condensed_plot_summary(plot_plan))})
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
        clues_plan = call_with_retry(client, messages=messages, schema=CluesPlan, temperature=0.7, phase="clues")
        messages.append({"role": "assistant", "content": json.dumps(_condensed_clues_summary(clues_plan))})
    except Exception as e:
        logger.error(f"LLM clues generation failed: {e}")
        return None, "provider_error", 0

    # Phase 3: Seeded Memories — generated one suspect role at a time rather
    # than all roles in a single call. A combined call's required output
    # size scales with num_suspects (up to 7), which reliably overflows
    # small local models' context/output budget for larger casts even after
    # trimming the input history above; per-role calls keep each response
    # small regardless of cast size.
    memory_roles = [r for r in allowed_roles if r != "{VICTIM_ID}"]
    seeded_memories: list = []
    for role in memory_roles:
        if role == "{KILLER_ID}":
            role_rules = (
                "This role is the KILLER. You MUST provide exactly three memories with these "
                "case_function values:\n"
                "   - \"killer_motive\": The memory establishing the true motive.\n"
                "   - \"opportunity_setup\": The memory establishing how/when they entered the scene or opportunity.\n"
                "   - \"false_alibi_reason\": The memory establishing their false alibi or why they lied about their whereabouts."
            )
        elif role in ("{RH1_ID}", "{RH2_ID}"):
            role_rules = (
                "This role is a RED HERRING suspect. Provide 1-2 memories using case_function values "
                "such as \"red_herring_motive\", \"innocence_anchor\", \"clue_support\", \"false_alibi_support\"."
            )
        else:
            role_rules = (
                "This role is a WITNESS. Provide 1-2 memories using case_function values such as "
                "\"clue_support\", \"victim_trigger\", \"killer_trigger\", or another applicable non-killer value."
            )

        role_messages = messages + [{"role": "user", "content": f"""Based on the plot and clue plans, generate the seeded memories for ONLY the role {role}.

{role_rules}

memory_type must be one of: "private_secret", "shared_secret", "rumour", "witness_fragment", "false_belief", "deliberate_lie", "innocent_secret", "observed", "cover_story".
truth_status must be one of: "true", "false", "mistaken", "rumour", "unknown".
owner_role must be exactly "{role}". known_by_roles may only reference roles from: {allowed_roles_str}.

Format the output strictly as a JSON object matching the required schema."""}]

        try:
            role_plan = call_with_retry(client, messages=role_messages, schema=RoleMemoriesPlan, temperature=0.7, phase=f"memories:{role}")
            seeded_memories.extend(role_plan.memories)
        except Exception as e:
            logger.error(f"LLM memories generation failed for {role}: {e}")
            return None, "provider_error", 0

    # Witness fragments, still a single call — bounded by num witness roles
    # (0-4) rather than the full suspect cast, so it stays small.
    messages.append({"role": "user", "content": f"""Based on the plot and clue plans, generate witness fragments.
Allowed roles to reference: {allowed_roles_str}

Format the output strictly as a JSON object matching the required schema."""})
    try:
        witness_plan = call_with_retry(client, messages=messages, schema=WitnessFragmentsPlan, temperature=0.7, phase="witness_fragments")
    except Exception as e:
        logger.error(f"LLM witness fragments generation failed: {e}")
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
        flavour_plan = call_with_retry(client, messages=flavour_messages, schema=FlavourPlan, temperature=0.5, phase="flavour")
    except Exception as e:
        logger.error(f"LLM flavour generation failed: {e}")
        return None, "provider_error", 0

    # Phase 5: Timeline — a fresh morning (ambient beats + per-agent routines).
    # Best-effort, like character identities: a timeline failure must NOT sink
    # an otherwise-good case, so on any error we proceed with timeline=None and
    # the assembler keeps the template events/routines (safe fallback). The
    # murder and its discovery are deliberately NOT requested here — the
    # deterministic compiler synthesises those from the fixed timing so they can
    # never be mis-timed or leaked.
    timeline_plan = None
    try:
        bc = base_case_data.case
        cast_lines = "\n".join(
            f"  {r} = {roles.get(r + '_NAME', roles.get('{' + r.strip('{}') + '_NAME}', ''))}"
            for r in allowed_roles
        )
        # Cases do not all happen in the morning (case_004 runs 22:00-23:45, case_006 18:00-23:00).
        # The prompt used to hardcode "MORNING", which is how generated cases ended up with
        # witnesses saying "twenty to nine" at lunchtime and "this morning" at midnight.
        part_of_day = _part_of_day(bc.sim_start_time)
        timeline_messages = [
            {"role": "system", "content": "You are a creative murder mystery architect writing a case for a detective game."},
            {"role": "user", "content": f"""Author the {part_of_day.upper()} TIMELINE for this mystery — the ordinary comings and goings the player watches when they rewind the day. Plot recap:
{json.dumps(_condensed_plot_summary(plot_plan))}

Cast (role = name):
{cast_lines}

Fixed timing (do not contradict): the day starts at {bc.sim_start_time}; the murder happens between {bc.murder_window[0]} and {bc.murder_window[1]}; the body is found at {bc.discovery_time}. DO NOT author the murder itself or the discovery of the body — those are handled for you. Author only the ordinary/suspicious activity BEFORE roughly {bc.murder_window[0]}.

WEATHER — the locked case conditions are {plot_plan.weather} ({plot_plan.weather_intensity}, wind: {plot_plan.wind}). Let ordinary outdoor activity acknowledge them naturally when relevant, but do not invent weather-based evidence, hide required facts behind visibility, or claim weather changed during the replay.

TIME OF DAY — this case takes place in the {part_of_day}, starting at {bc.sim_start_time}. Every beat and every routine must make sense at that hour. Do not write breakfast, opening-up or milk-round activity into an evening case, or pub closing-time into a morning one. Never use a clock phrase that contradicts the hours above (no "this morning" in a case that happens at night).

Produce:
1. beats: a list of short story beats. Each beat: role (from the list above), location_role (one of: "public", "victim_home", "killer_home", "role_home", "witness_spot"), action_summary (what they do), public_summary (what a passer-by would see, or null if unobserved), visibility ("public", "public_partial", or "private"), beat_kind ("routine", "approach", "suspicious", "sighting", or "cover"), order_hint (integer ordering, low = earlier). Give every listed role at least one beat so the village feels alive. Do NOT reveal who the killer is or state that a murder occurred.
2. routines: for EACH role, a one-sentence routine_summary describing what that character does on an ORDINARY {part_of_day} — their standing habits, not the events of the day of the murder.

CRITICAL — routine_summary is shown to the player on the Suspects screen BEFORE they have discovered a single clue. It is not a private author note. A routine_summary MUST NOT:
  * say what the character did on the night/day of the murder ("that night he went to the square...")
  * reveal any secret, lie or motive ("secretly owed him money", "she lied to protect him")
  * state that an alibi is false, or that anything "will be" discovered, proven or dismantled
  * disclose another character's secret ("dimly recalls her maiden name was Bell")
  * hint at what the player is supposed to deduce ("will have seen something crucial")
Write it as a neighbour would describe them: "Opens the bookshop at nine; mornings are for paperwork and coffee at Hobbs." Give it a habit, a preference or an opinion — never a plot point.

Format the output strictly as a JSON object matching the required schema."""}
        ]
        timeline_plan = call_with_retry(client, messages=timeline_messages, schema=TimelinePlan, temperature=0.8, phase="timeline")
        if not isinstance(timeline_plan, TimelinePlan):
            timeline_plan = None
    except Exception as e:
        logger.warning(f"LLM timeline generation failed, keeping template timeline: {e}")
        timeline_plan = None

    try:
        merged_dict = {
            "case_type": case_type,
            "title": plot_plan.title,
            "weather": plot_plan.weather,
            "weather_intensity": plot_plan.weather_intensity,
            "wind": plot_plan.wind,
            "motive_variant": plot_plan.motive_variant,
            "victim_rationale": plot_plan.victim_rationale,
            "killer_rationale": plot_plan.killer_rationale,
            "red_herring_rationales": plot_plan.red_herring_rationales,
            "scene_description": plot_plan.scene_description,
            "clue_plans": [c.model_dump() for c in clues_plan.clue_plans],
            "seeded_memories": [m.model_dump() for m in seeded_memories],
            "witness_fragments": [w.model_dump() for w in witness_plan.witness_fragments],
            "interview_flavour": flavour_plan.interview_flavour,
            "reveal_narration": flavour_plan.reveal_narration,
            "timeline": timeline_plan.model_dump() if timeline_plan is not None else None,
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
            repaired = client.generate_json(
                system_prompt=repair_sys,
                user_prompt=repair_user,
                schema=CasePlan,
                temperature=0.2
            )
            # The repair prompt targets clue/memory validity and may drop the
            # timeline; carry the original forward so we don't silently revert
            # to the template morning on an otherwise-successful repair.
            if repaired.timeline is None:
                repaired.timeline = plan.timeline
            plan = repaired
        except Exception as e:
            logger.error(f"LLM repair failed: {e}")
            return None, "provider_error", attempt
        
    return None, "repair_exhausted", MAX_LLM_REPAIR_ATTEMPTS
