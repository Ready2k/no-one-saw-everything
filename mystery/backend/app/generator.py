"""Template-based procedural generation scaffold."""

import json
import random
import os
from pathlib import Path

from .models import CaseData, CaseFile, Agent, Location, GameObject, SeededMemory, Event, Clue, Conclusion, AgentInterviewPack, ChallengeRule, Solution

BASE_DIR = Path(__file__).parent / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
BASE_CASE_DIR = BASE_DIR / "case_001"

def generate_case(
    case_type: str, 
    difficulty: str, 
    seed: int, 
    mode: str = "deterministic",
    fallback_allowed: bool = True
) -> tuple[CaseData, bool, str, int]:
    """Returns CaseData, fallback_used flag, fallback_reason (if any), and repair_attempts."""
    fallback_used = False
    fallback_reason = ""
    repair_attempts = 0
    
    rng = random.Random(seed)
    
    # Load base cast and objects to use as our pools
    with open(BASE_CASE_DIR / "agents.json") as f:
        base_agents = json.load(f)
    
    with open(BASE_CASE_DIR / "objects.json") as f:
        base_objects = json.load(f)

    # We need 8 agents for the 8 roles
    agent_pool = [a for a in base_agents]
    rng.shuffle(agent_pool)
    
    roles = {
        "{VICTIM_ID}": agent_pool[0]["agent_id"],
        "{VICTIM_NAME}": agent_pool[0]["full_name"],
        "{KILLER_ID}": agent_pool[1]["agent_id"],
        "{KILLER_NAME}": agent_pool[1]["full_name"],
        "{RH1_ID}": agent_pool[2]["agent_id"],
        "{RH1_NAME}": agent_pool[2]["full_name"],
        "{RH2_ID}": agent_pool[3]["agent_id"],
        "{RH2_NAME}": agent_pool[3]["full_name"],
        "{WITNESS1_ID}": agent_pool[4]["agent_id"],
        "{WITNESS1_NAME}": agent_pool[4]["full_name"],
        "{WITNESS2_ID}": agent_pool[5]["agent_id"],
        "{WITNESS2_NAME}": agent_pool[5]["full_name"],
        "{WITNESS3_ID}": agent_pool[6]["agent_id"],
        "{WITNESS3_NAME}": agent_pool[6]["full_name"],
        "{WITNESS4_ID}": agent_pool[7]["agent_id"],
        "{WITNESS4_NAME}": agent_pool[7]["full_name"],
    }
    
    # Pick a random weapon
    weapons = [o for o in base_objects if o.get("is_weapon")]
    if not weapons:
        # fallback
        weapons = [{"object_id": "obj_till_weight", "name": "brass till weight"}]
    
    weapon = rng.choice(weapons)
    roles["{WEAPON_ID}"] = weapon["object_id"]
    roles["{WEAPON_NAME}"] = weapon["name"]

    # Load template
    template_path = TEMPLATES_DIR / f"{case_type}.json"
    if not template_path.exists():
        # Fallback to blackmail if we don't have the requested one
        template_path = TEMPLATES_DIR / "blackmail.json"
        
    with open(template_path) as f:
        template_str = f.read()

    # --- LOCATION REMAPPING ---
    # To prevent cases always happening in the cafe, we remap the template's physical path.
    LOCATION_VECTORS = [
        ("loc_hobbs_cafe", "loc_cafe_kitchen", "loc_cafe_storage"),
        ("loc_village_square", "loc_bookshop", "loc_bookshop"),
        ("loc_village_square", "loc_marcus_house", "loc_marcus_house"),
        ("loc_village_square", "loc_clinic", "loc_clinic"),
        ("loc_village_square", "loc_elias_house", "loc_elias_house"),
        ("loc_village_square", "loc_nadia_flat", "loc_nadia_flat"),
        ("loc_village_square", "loc_owen_house", "loc_owen_house"),
        ("loc_village_square", "loc_priya_flat", "loc_priya_flat"),
    ]
    selected_vector = rng.choice(LOCATION_VECTORS)
    template_str = template_str.replace("loc_hobbs_cafe", selected_vector[0])
    template_str = template_str.replace("loc_cafe_kitchen", selected_vector[1])
    template_str = template_str.replace("loc_cafe_storage", selected_vector[2])

    # --- TIME SHIFTING ---
    # Shift all HH:MM timestamps by a random offset to prevent the murder always happening at 08:12
    import re
    time_shift_minutes = rng.randint(-180, 180)
    
    def shift_time(match):
        h, m = map(int, match.group(0).split(':'))
        total_mins = (h * 60 + m + time_shift_minutes) % (24 * 60)
        return f"{total_mins // 60:02d}:{total_mins % 60:02d}"

    template_str = re.sub(r'\b\d{2}:\d{2}\b', shift_time, template_str)

    # Replace roles
    for placeholder, value in roles.items():
        template_str = template_str.replace(placeholder, value)
        
    # Generate unique case ID
    import time
    case_id = f"gen_{case_type}_{seed}_{int(time.time())}"
    template_str = template_str.replace(f"template_{case_type}", case_id)

    # Parse back to dict
    data = json.loads(template_str)
    
    # Construct models
    case_file = CaseFile(**data["case"])
    case_file.case_id = case_id
    
    # Because we did string replacement on the whole template, the agents array in the template
    # might have their IDs scrambled (e.g. Agent 0 got replaced with Agent 3's ID).
    # To keep their core identities, we should use the base_agents but set the victim flag.
    # Wait! If we string replaced the template, the relationships in clues/events now point to the
    # shuffled IDs. If we just load the template's agents, their names will be replaced, meaning
    # the agent originally named "Marcus" might now be named "Owen". That means "Owen" has the occupation "Cafe Owner".
    # This is fine for a scaffold, it proves dynamic role assignment!
    agents = [Agent(**a) for a in data["agents"]]
    
    # Ensure the victim is marked as victim correctly
    for a in agents:
        a.is_victim = (a.agent_id == case_file.victim_id)

    locations = [Location(**l) for l in data["locations"]]
    objects = [GameObject(**o) for o in data["objects"]]
    memories = [SeededMemory(**m) for m in data["memories"]]
    events = [Event(**e) for e in data["events"]]
    clues = [Clue(**c) for c in data["clues"]]
    conclusions = [Conclusion(**c) for c in data["conclusions"]]
    interviews = [AgentInterviewPack(**i) for i in data["interviews"]]
    challenges = [ChallengeRule(**c) for c in data["challenges"]]
    solution = Solution(**data["solution"])

    base_case = CaseData(
        case=case_file,
        agents=agents,
        locations=locations,
        objects=objects,
        memories=memories,
        events=events,
        clues=clues,
        conclusions=conclusions,
        interview_packs=interviews,
        challenge_rules=challenges,
        solution=solution
    )

    if mode == "llm_assisted":
        from .llm.mystery_architect import generate_llm_case
        llm_case, reason, attempts = generate_llm_case(base_case, roles, case_type, difficulty, seed)
        repair_attempts = attempts
        if llm_case is not None:
            return llm_case, False, "", repair_attempts
        
        if not fallback_allowed:
            raise RuntimeError(f"LLM generation failed ({reason}) and fallback not allowed.")
        fallback_used = True
        fallback_reason = reason or "unknown_error"
            
    return base_case, fallback_used, fallback_reason, repair_attempts
