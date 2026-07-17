"""Template-based procedural generation scaffold."""

import json
import random
import os
import re
from pathlib import Path

from .models import CaseData, CaseFile, Agent, Location, GameObject, SeededMemory, Event, Clue, Conclusion, AgentInterviewPack, ChallengeRule, Solution
from .background_npcs import add_background_npcs

BASE_DIR = Path(__file__).parent / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
BASE_CASE_DIR = BASE_DIR / "case_001"

ROLE_NAMES = ["VICTIM", "KILLER", "RH1", "RH2", "WITNESS1", "WITNESS2", "WITNESS3", "WITNESS4"]

# Grammatical forms for each pronoun set, keyed by the same slot names used
# by the {ROLE_SLOT} placeholders baked into the templates (see
# data/templates/*.json, tagged via a one-off script against each agent's
# "pronoun" field in case_001/agents.json).
PRONOUN_FORMS = {
    "he": {"SUBJ": "he", "OBJ": "him", "DET": "his", "POSS": "his", "REFL": "himself"},
    "she": {"SUBJ": "she", "OBJ": "her", "DET": "her", "POSS": "hers", "REFL": "herself"},
    "they": {"SUBJ": "they", "OBJ": "them", "DET": "their", "POSS": "theirs", "REFL": "themselves"},
}

_BARE_PRONOUN_RE = re.compile(r'\b(he|him|his|himself|she|her|hers|herself)\b', re.IGNORECASE)


def _classify_pronoun_slot(word: str, text: str, end_pos: int) -> str:
    w = word.lower()
    if w in ("he", "she"):
        return "SUBJ"
    if w == "him":
        return "OBJ"
    if w == "hers":
        return "POSS"
    if w in ("himself", "herself"):
        return "REFL"
    # "his"/"her": determiner ("his study") vs standalone object/possessive.
    # Immediately followed by another word => treat as a determiner (the
    # dominant pattern in this prose).
    if re.match(r"\s+[A-Za-z']", text[end_pos:end_pos + 3]):
        return "DET"
    return "POSS" if w == "his" else "OBJ"


def neutralize_leftover_pronouns(text: str) -> str:
    """Safety net for prose the role-tagging pass couldn't attribute (no
    role name mentioned in the same sentence to anchor it to, e.g. a first
    person interview answer that just says "he was here first thing").
    Swapping a stray gendered pronoun to they/them/their/theirs/themselves
    is always safe; leaving it as-is risks shipping the wrong gender for
    whichever agent got shuffled into that role."""
    def repl(m):
        word = m.group(1)
        slot = _classify_pronoun_slot(word, text, m.end())
        neutral = PRONOUN_FORMS["they"][slot]
        return neutral.capitalize() if word[0].isupper() else neutral
    return _BARE_PRONOUN_RE.sub(repl, text)

def generate_case(
    case_type: str, 
    difficulty: str, 
    seed: int, 
    mode: str = "deterministic",
    fallback_allowed: bool = True,
    num_suspects: int | None = None,
    num_locations: int | None = None,
    custom_theme: str | None = None,
    tone: str | None = None,
    llm_notes: str | None = None
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

    # Canonical location names/descriptions (case_001), used below to give
    # remap targets that don't exist in the templates (e.g. loc_priya_flat)
    # their real identity instead of leftover cafe flavour text.
    with open(BASE_CASE_DIR / "locations.json") as f:
        canonical_locations = {l["location_id"]: l for l in json.load(f)}

    # We need 8 agents for the 8 roles. Background/ambient characters (e.g.
    # case_001's wandering NPCs) aren't part of the mystery and must never be
    # shuffled into a suspect/victim role.
    agent_pool = [a for a in base_agents if not a.get("is_background")]
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

    # Pronoun placeholders (e.g. {VICTIM_SUBJ}, {VICTIM_DET_CAP}) so the
    # role-tagged prose in the templates resolves to whichever pronoun
    # matches the agent actually shuffled into each role, instead of the
    # template's original hardcoded gender.
    for i, role in enumerate(ROLE_NAMES):
        pronoun = agent_pool[i].get("pronoun", "they")
        forms = PRONOUN_FORMS.get(pronoun, PRONOUN_FORMS["they"])
        for slot, word in forms.items():
            roles[f"{{{role}_{slot}}}"] = word
            roles[f"{{{role}_{slot}_CAP}}"] = word.capitalize()

    # Character identities: by default every generated case draws its cast
    # from the same fixed case_001 roster (just reshuffled into different
    # roles), which reads as "case_001 with names swapped". In llm_assisted
    # mode, ask the LLM for a fresh name/occupation per role *before* the
    # template substitution below, so the new identity threads through every
    # mention in the case (interviews, memories, events) rather than just
    # the handful of fields later phases rewrite. Best-effort: any failure
    # (or deterministic mode) silently keeps the case_001 defaults already
    # in `roles`.
    default_occupations = {
        "VICTIM": "Owner of Hobbs Cafe",
        "KILLER": "Cafe manager",
        "RH1": "Builder",
        "RH2": "Bookshop owner",
        "WITNESS1": "Delivery driver",
        "WITNESS2": "Clinic nurse",
        "WITNESS3": "Retired schoolteacher",
        "WITNESS4": "Bookshop assistant",
    }
    if mode == "llm_assisted":
        from .llm.mystery_architect import generate_character_identities
        identities = generate_character_identities(case_type, seed, custom_theme=custom_theme, tone=tone)
        if identities:
            for raw_role, identity in identities.items():
                role = raw_role.strip("{}").removesuffix("_ID").removesuffix("_NAME")
                if role not in ROLE_NAMES:
                    continue
                if not identity.full_name or not identity.occupation:
                    continue
                roles[f"{{{role}_NAME}}"] = identity.full_name
                roles[f"{{{role}_OCCUPATION}}"] = identity.occupation
    for role, occupation in default_occupations.items():
        roles.setdefault(f"{{{role}_OCCUPATION}}", occupation)

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

    # Safety net: any pronoun the template's role-tagging pass couldn't
    # attribute to a role (no name mentioned in the same sentence) is still
    # bare text at this point — tagged ones are safely wrapped in
    # {ROLE_SLOT} placeholders, which don't match the bare-word regex, so
    # this only touches genuinely unresolved pronouns. Must run *before*
    # role substitution below, since afterwards a correctly resolved "her"
    # (from {VICTIM_DET}) is indistinguishable from a stray untagged "her".
    template_str = neutralize_leftover_pronouns(template_str)

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

    # Location remapping folds the cafe trio (indices 1-3 in every template:
    # hobbs_cafe/cafe_kitchen/cafe_storage) onto another location id, which
    # leaves duplicate entries under the same id. Naively keeping the first
    # duplicate kept the *generic cafe* entry (since it's always earlier in
    # the template) and discarded the real, correctly-named target — so
    # every generated case displayed as "Cafe Kitchen"/"Cafe Storage Room"
    # regardless of where the murder was actually remapped to. Instead,
    # prefer the authored (non-cafe-trio) entry for display fields, and
    # only borrow `murder_suitable` from the folded-in cafe entry. If the
    # remap target has no authored template entry at all (e.g. loc_priya_flat,
    # loc_nadia_flat, loc_elias_house — flats that only exist in case_001),
    # synthesize one from the canonical case_001 location of the same id.
    GENERIC_TRIO_INDICES = {1, 2, 3}
    raw_locations = data["locations"]
    order: list[str] = []
    authored_by_id: dict[str, dict] = {}
    generic_by_id: dict[str, dict] = {}
    murder_suitable_by_id: dict[str, bool] = {}
    for idx, l in enumerate(raw_locations):
        lid = l["location_id"]
        if lid not in order:
            order.append(lid)
        if idx in GENERIC_TRIO_INDICES:
            generic_by_id.setdefault(lid, l)
            if l.get("murder_suitable"):
                murder_suitable_by_id[lid] = True
        else:
            authored_by_id.setdefault(lid, l)

    locations = []
    for lid in order:
        base = authored_by_id.get(lid)
        if base is not None:
            merged = dict(base)
        else:
            merged = dict(generic_by_id[lid])
            canonical = canonical_locations.get(lid)
            if canonical:
                merged["name"] = canonical["name"]
                merged["description"] = canonical["description"]
                merged["illustration"] = canonical.get("illustration")
        if murder_suitable_by_id.get(lid):
            merged["murder_suitable"] = True
        locations.append(Location(**merged))

    # The template's overview_text hardcodes "owner of Hobbs Cafe, found
    # dead in the cafe storage room" prose that ignores where the location
    # remap above actually placed the murder — every generated case read
    # as case_001 with names swapped. Rebuild it from the resolved murder
    # location instead.
    murder_loc = next((l for l in locations if l.location_id == case_file.murder_location_id), None)
    discoverer = next((a for a in agents if a.agent_id == case_file.discovered_by), None)
    victim = next((a for a in agents if a.agent_id == case_file.victim_id), None)
    if murder_loc is not None and discoverer is not None and victim is not None:
        case_file.overview_text = (
            f"{case_file.discovery_time} — {victim.full_name} found dead in "
            f"{murder_loc.name} by {discoverer.full_name}. "
            f"Several villagers passed nearby around that time; no one claims to "
            f"have seen what happened. The morning can be rewound from {case_file.sim_start_time}."
        )
        if not case_file.scene_description:
            case_file.scene_description = case_file.overview_text

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
    from datetime import datetime
    created_at_str = datetime.now().isoformat() + "Z"

    base_case.metadata = {
        "metadata_version": 1,
        "mode": mode,
        "seed": seed,
        "theme_preset": custom_theme if custom_theme else case_type,
        "tone": tone or "standard",
        "fallback_used": False,
        "repair_attempts": 0,
        "compaction_applied": num_suspects is not None or num_locations is not None,
        "pruned_agents": [],
        "remapped_locations": {},
        "red_herrings": list(dict.fromkeys(filter(None, [roles.get("{RH1_ID}"), roles.get("{RH2_ID}")])))
    }
    # Set created_at inside base_case.metadata
    base_case.metadata["created_at"] = created_at_str

    if mode == "llm_assisted":
        from .llm.mystery_architect import generate_llm_case
        llm_case, reason, attempts = generate_llm_case(
            base_case, roles, case_type, difficulty, seed,
            custom_theme=custom_theme, tone=tone, llm_notes=llm_notes,
            num_suspects=num_suspects, num_locations=num_locations
        )
        repair_attempts = attempts
        if llm_case is not None:
            llm_case.metadata = {
                "metadata_version": 1,
                "mode": "llm_assisted",
                "seed": seed,
                "theme_preset": custom_theme if custom_theme else case_type,
                "tone": tone or "standard",
                "fallback_used": False,
                "repair_attempts": repair_attempts,
                "compaction_applied": num_suspects is not None or num_locations is not None,
                "pruned_agents": [],
                "remapped_locations": {},
                "red_herrings": list(dict.fromkeys(filter(None, [c.target_agent_id for c in llm_case.conclusions if c.target_agent_id != llm_case.case.killer_id and c.target_agent_id != llm_case.case.victim_id])))
            }
            llm_case.metadata["created_at"] = created_at_str
            if num_suspects is not None or num_locations is not None:
                llm_case = compact_case_data(llm_case, num_suspects, num_locations, seed, roles)
            add_background_npcs(llm_case, rng)
            living_suspects = [a.agent_id for a in llm_case.agents if not a.is_victim and not a.is_background]
            llm_case.metadata["num_suspects"] = len(living_suspects)
            llm_case.metadata["num_locations"] = len(llm_case.locations)
            return llm_case, False, "", repair_attempts
        
        if not fallback_allowed:
            raise RuntimeError(f"LLM generation failed ({reason}) and fallback not allowed.")
        fallback_used = True
        fallback_reason = reason or "unknown_error"
        
        # update base_case fallback metadata
        base_case.metadata["fallback_used"] = True
        base_case.metadata["fallback_reason"] = fallback_reason

    if num_suspects is not None or num_locations is not None:
        base_case = compact_case_data(base_case, num_suspects, num_locations, seed, roles)

    add_background_npcs(base_case, rng)

    # Final metadata override / update
    if base_case.metadata:
        living_suspects = [a.agent_id for a in base_case.agents if not a.is_victim and not a.is_background]
        base_case.metadata["num_suspects"] = len(living_suspects)
        base_case.metadata["num_locations"] = len(base_case.locations)

    return base_case, fallback_used, fallback_reason, repair_attempts


def compact_case_data(
    case_data: CaseData,
    num_suspects: int | None,
    num_locations: int | None,
    seed: int,
    roles: dict[str, str]
) -> CaseData:
    """Selects and compacts the template (or LLM generated case) based on target counts."""
    import random
    rng = random.Random(seed)

    victim_id = case_data.case.victim_id
    killer_id = case_data.case.killer_id
    rh1_id = roles.get("{RH1_ID}")
    rh2_id = roles.get("{RH2_ID}")

    original_locations = list(case_data.locations)
    remapped_locations_metadata = {}

    # --- 1. DETERMINE KEPT AGENTS ---
    kept_agent_ids = {a.agent_id for a in case_data.agents}
    if num_suspects is not None:
        num_suspects = max(3, min(7, num_suspects))
        
        # Required agents
        required_agent_ids = {victim_id, killer_id}
        if rh1_id:
            required_agent_ids.add(rh1_id)
        if rh2_id:
            required_agent_ids.add(rh2_id)
            
        # Optional witnesses
        optional_witness_ids = [
            roles.get("{WITNESS1_ID}"),
            roles.get("{WITNESS2_ID}"),
            roles.get("{WITNESS3_ID}"),
            roles.get("{WITNESS4_ID}")
        ]
        optional_witness_ids = [wid for wid in optional_witness_ids if wid is not None and wid not in required_agent_ids]

        # Rank optional witnesses by usefulness (clues & conclusions supported)
        witness_scores = {}
        for wid in optional_witness_ids:
            score = 0
            # Count clues revealed by this witness
            clues_for_wid = []
            for clue in case_data.clues:
                if clue.discoverability.method == "interview" and clue.discoverability.agent_id == wid:
                    score += 1
                    clues_for_wid.append(clue.clue_id)
            # Count conclusions supported by these clues
            for conc in case_data.conclusions:
                if set(conc.supported_by_clue_ids) & set(clues_for_wid):
                    score += 2
            witness_scores[wid] = score

        # Sort optional witnesses: highest score first
        ranked_witnesses = sorted(optional_witness_ids, key=lambda wid: witness_scores.get(wid, 0), reverse=True)

        # Keep top N witnesses
        needed_witnesses = max(0, num_suspects - 3) # suspects list excludes victim, includes killer + 2 red herrings = 3 suspects.
        kept_witnesses = ranked_witnesses[:needed_witnesses]

        kept_agent_ids = required_agent_ids | set(kept_witnesses)

    # Gather pruned agents details before filtering them
    pruned_agents = {a.agent_id for a in case_data.agents} - kept_agent_ids
    pruned_agents_info = []
    for a in case_data.agents:
        if a.agent_id in pruned_agents:
            first_name = a.full_name.split()[0]
            pruned_agents_info.append((a.full_name, first_name))

    # --- 2. DETERMINE KEPT LOCATIONS ---
    kept_location_ids = {l.location_id for l in case_data.locations}
    default_loc_id = "loc_village_square"

    if num_locations is not None:
        num_locations = max(3, min(8, num_locations))
        
        murder_loc = case_data.case.murder_location_id
        discovery_loc = case_data.case.discovery_location_id

        loc_list = []
        if murder_loc:
            loc_list.append(murder_loc)
        if discovery_loc and discovery_loc not in loc_list:
            loc_list.append(discovery_loc)

        # Add home/work locations of kept agents
        for agent in case_data.agents:
            if agent.agent_id in kept_agent_ids:
                if agent.home_location_id and agent.home_location_id not in loc_list:
                    loc_list.append(agent.home_location_id)
                if agent.work_location_id and agent.work_location_id not in loc_list:
                    loc_list.append(agent.work_location_id)

        # If we need more to reach num_locations, add from the remaining locations in the case
        all_locs = [l.location_id for l in case_data.locations]
        for lid in all_locs:
            if len(loc_list) >= num_locations:
                break
            if lid not in loc_list:
                loc_list.append(lid)

        # Truncate if we have more than num_locations
        if len(loc_list) > num_locations:
            # Make sure we don't prune murder or discovery locations
            loc_list = loc_list[:num_locations]

        kept_location_ids = set(loc_list)
        if default_loc_id not in kept_location_ids and loc_list:
            default_loc_id = loc_list[0]

    # --- Helper function for location remapping ---
    pruned_agents = set(a.agent_id for a in case_data.agents) - kept_agent_ids
    pruned_private_locations = set()
    for a in case_data.agents:
        if a.agent_id in pruned_agents:
            if a.home_location_id:
                pruned_private_locations.add(a.home_location_id)
            if a.work_location_id:
                pruned_private_locations.add(a.work_location_id)

    location_map = {l.location_id: l for l in case_data.locations}

    def is_location_public(lid: str) -> bool:
        loc = location_map.get(lid)
        if not loc:
            return True
        if loc.location_type in ["public", "neutral", "crime_scene"]:
            return True
        if loc.visibility_type == "public":
            return True
        return False

    def get_best_location(agent_id, original_location_id=None):
        orig_is_public = False
        if original_location_id:
            orig_is_public = is_location_public(original_location_id)

        agent = next((a for a in case_data.agents if a.agent_id == agent_id), None)
        if agent and agent_id in kept_agent_ids:
            if not orig_is_public or (orig_is_public and not agent.home_location_id):
                if agent.home_location_id in kept_location_ids and agent.home_location_id not in pruned_private_locations:
                    if not orig_is_public or is_location_public(agent.home_location_id):
                        return agent.home_location_id
                if agent.work_location_id in kept_location_ids and agent.work_location_id not in pruned_private_locations:
                    if not orig_is_public or is_location_public(agent.work_location_id):
                        return agent.work_location_id

        candidates = [l for l in kept_location_ids if l not in pruned_private_locations]
        if not candidates:
            candidates = list(kept_location_ids)

        if orig_is_public:
            public_candidates = [l for l in candidates if is_location_public(l)]
            if public_candidates:
                candidates = public_candidates

        non_murder_candidates = [l for l in candidates if l != case_data.case.murder_location_id]
        if non_murder_candidates:
            candidates = non_murder_candidates

        if candidates:
            return candidates[hash(agent_id or "") % len(candidates)]
        return default_loc_id

    def remap_location(old_id, agent_id=None):
        """Resolve a pruned location to its replacement, memoized by the
        original id. get_best_location() picks a target by hashing the
        *asking* agent, so without this cache the same pruned physical
        location (e.g. "the cafe storage room") could get remapped to a
        different surviving location for each agent/event/clue that
        referenced it — scattering one scene across several location labels
        in the timeline. Memoizing means the first reference decides, and
        every later reference to the same original location reuses it."""
        if not old_id:
            return default_loc_id
        if old_id in remapped_locations_metadata:
            return remapped_locations_metadata[old_id]
        new_id = get_best_location(agent_id, old_id)
        remapped_locations_metadata[old_id] = new_id
        return new_id

    # --- 3. FILTER AGENTS & REMAP THEIR HOME/WORK ---
    case_data.agents = [a for a in case_data.agents if a.agent_id in kept_agent_ids]
    for agent in case_data.agents:
        agent.relationships = [r for r in agent.relationships if r.target_agent_id in kept_agent_ids]
        if agent.home_location_id not in kept_location_ids:
            agent.home_location_id = remap_location(agent.home_location_id, agent.agent_id)
        if agent.work_location_id not in kept_location_ids:
            agent.work_location_id = remap_location(agent.work_location_id, agent.agent_id)

    # --- 4. FILTER LOCATIONS ---
    case_data.locations = [l for l in case_data.locations if l.location_id in kept_location_ids]
    for loc in case_data.locations:
        loc.connected_location_ids = [lid for lid in loc.connected_location_ids if lid in kept_location_ids]

    # --- 5. FILTER & REMAP EVENTS ---
    filtered_events = []
    for event in case_data.events:
        had_agents = len(event.agent_ids) > 0
        # Filter agent ids
        event.agent_ids = [aid for aid in event.agent_ids if aid in kept_agent_ids]
        
        # Remap location if pruned
        if event.location_id not in kept_location_ids:
            event.location_id = remap_location(
                event.location_id,
                event.agent_ids[0] if event.agent_ids else None
            )


        if event.event_type == "murder" or len(event.agent_ids) > 0 or not had_agents:
            filtered_events.append(event)
            
    case_data.events = filtered_events
    kept_event_ids = {e.event_id for e in case_data.events}

    # --- 5b. REMAP OBJECT LOCATIONS ---
    # Object locations feed both clue inspection text and visual anchors. If a
    # compact generated case drops the original room, keep the object in the
    # same remapped scene as any event/clue that referred to that room.
    for obj in case_data.objects:
        if obj.normal_location_id and obj.normal_location_id not in kept_location_ids:
            obj.normal_location_id = remap_location(
                obj.normal_location_id,
                obj.touched_by_agent_ids[0] if obj.touched_by_agent_ids else None,
            )
        if obj.final_location_id and obj.final_location_id not in kept_location_ids:
            obj.final_location_id = remap_location(
                obj.final_location_id,
                obj.touched_by_agent_ids[0] if obj.touched_by_agent_ids else None,
            )

    # --- 6. FILTER CLUES & REMAP DISCOVERABILITY ---
    filtered_clues = []
    kept_clue_ids = set()
    
    for clue in case_data.clues:
        d = clue.discoverability
        
        clue.linked_agent_ids = [aid for aid in clue.linked_agent_ids if aid in kept_agent_ids]
        clue.linked_location_ids = [lid for lid in clue.linked_location_ids if lid in kept_location_ids]
        clue.linked_event_ids = [eid for eid in clue.linked_event_ids if eid in kept_event_ids]
        
        if d.location_id and d.location_id not in kept_location_ids:
            d.location_id = remap_location(
                d.location_id,
                clue.linked_agent_ids[0] if clue.linked_agent_ids else None
            )

        if d.method == "interview" and d.agent_id not in kept_agent_ids:
            d.method = "inspect"
            d.location_id = remap_location(d.location_id, d.agent_id)
            d.agent_id = None
            d.question_type = None
            
        filtered_clues.append(clue)
        
    case_data.clues = filtered_clues
    kept_clue_ids = {c.clue_id for c in case_data.clues}
    
    # Prune prior clue dependencies
    for clue in case_data.clues:
        clue.discoverability.required_prior_clue_ids = [
            pid for pid in clue.discoverability.required_prior_clue_ids if pid in kept_clue_ids
        ]

    # --- 7. FILTER CONCLUSIONS ---
    case_data.conclusions = [c for c in case_data.conclusions if c.target_agent_id in kept_agent_ids]
    for conc in case_data.conclusions:
        conc.supported_by_clue_ids = [cid for cid in conc.supported_by_clue_ids if cid in kept_clue_ids]

    # --- 8. FILTER SEEDED MEMORIES ---
    filtered_memories = []
    for m in case_data.memories:
        if m.owner_agent_id in kept_agent_ids:
            m.known_by_agent_ids = [r for r in m.known_by_agent_ids if r in kept_agent_ids]
            m.linked_clue_ids = [cid for cid in m.linked_clue_ids if cid in kept_clue_ids]
            filtered_memories.append(m)
    case_data.memories = filtered_memories

    # --- 9. FILTER INTERVIEW PACKS ---
    case_data.interview_packs = [p for p in case_data.interview_packs if p.agent_id in kept_agent_ids]
    for pack in case_data.interview_packs:
        pack.rules = [r for r in pack.rules if any(cid in kept_clue_ids for cid in r.reveals_clue_ids)]
        for r in pack.rules:
            r.reveals_clue_ids = [cid for cid in r.reveals_clue_ids if cid in kept_clue_ids]

    # --- 10. FILTER CHALLENGE RULES ---
    case_data.challenge_rules = [r for r in case_data.challenge_rules if r.target_agent_id in kept_agent_ids]
    for r in case_data.challenge_rules:
        r.evidence_clue_ids = [cid for cid in r.evidence_clue_ids if cid in kept_clue_ids]

    # --- 11. RESOLVE LOCATION NAMES TO CLEAN ---
    location_names_to_clean = []
    for old_id, new_id in remapped_locations_metadata.items():
        if old_id != new_id:
            old_loc = next((l for l in original_locations if l.location_id == old_id), None)
            new_loc = next((l for l in case_data.locations if l.location_id == new_id), None)
            if old_loc and new_loc:
                location_names_to_clean.append((old_loc.name, new_loc.name))

    # --- 12. CLEAN NARRATIVE CORPSE LEAKS FROM TEXT FIELDS ---
    def clean_text(text: str) -> str:
        if not text:
            return text
        for full_name, first_name in pruned_agents_info:
            # Replace possessives
            text = text.replace(full_name + "'s", "someone's")
            text = text.replace(full_name + "’s", "someone's")
            text = text.replace(first_name + "'s", "someone's")
            text = text.replace(first_name + "’s", "someone's")
            
            # Replace normal forms
            text = text.replace(full_name, "someone")
            text = text.replace(first_name, "someone")
            
            # Case insensitive possessives
            text = text.replace(full_name.lower() + "'s", "someone's")
            text = text.replace(full_name.lower() + "’s", "someone's")
            text = text.replace(first_name.lower() + "'s", "someone's")
            text = text.replace(first_name.lower() + "’s", "someone's")
            
            # Case insensitive normal forms
            text = text.replace(full_name.lower(), "someone")
            text = text.replace(first_name.lower(), "someone")
            
        for old_name, new_name in location_names_to_clean:
            text = text.replace(old_name, new_name)
            text = text.replace(old_name.lower(), new_name.lower())
            
        return text

    case_data.case.overview_text = clean_text(case_data.case.overview_text)
    case_data.case.scene_description = clean_text(case_data.case.scene_description)
    case_data.case.motive_summary = clean_text(case_data.case.motive_summary)
    
    case_data.solution.explanation = clean_text(case_data.solution.explanation)
    case_data.solution.motive.canonical = clean_text(case_data.solution.motive.canonical)
    if case_data.solution.method and case_data.solution.method.canonical:
        case_data.solution.method.canonical = clean_text(case_data.solution.method.canonical)
    if case_data.solution.opportunity and case_data.solution.opportunity.canonical:
        case_data.solution.opportunity.canonical = clean_text(case_data.solution.opportunity.canonical)

    for agent in case_data.agents:
        agent.routine_summary = clean_text(agent.routine_summary)
        agent.voice_card = clean_text(agent.voice_card)

    for clue in case_data.clues:
        clue.title = clean_text(clue.title)
        clue.description = clean_text(clue.description)
        if clue.discoverability and clue.discoverability.discovery_text:
            clue.discoverability.discovery_text = clean_text(clue.discoverability.discovery_text)

    for event in case_data.events:
        event.truth_description = clean_text(event.truth_description)
        if event.player_description:
            event.player_description = clean_text(event.player_description)

    for m in case_data.memories:
        m.summary = clean_text(m.summary)

    for pack in case_data.interview_packs:
        for r in pack.rules:
            r.answer_text = clean_text(r.answer_text)

    for r in case_data.challenge_rules:
        r.response_text = clean_text(r.response_text)

    # --- 13. UPDATE METADATA ---
    if case_data.metadata:
        case_data.metadata["pruned_agents"] = list(pruned_agents)
        case_data.metadata["remapped_locations"] = remapped_locations_metadata
        case_data.metadata["compaction_applied"] = True
        if "red_herrings" in case_data.metadata:
            case_data.metadata["red_herrings"] = list(dict.fromkeys([rh for rh in case_data.metadata["red_herrings"] if rh in kept_agent_ids]))

    return case_data
