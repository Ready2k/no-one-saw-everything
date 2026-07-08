from typing import Any
from .models import CaseData, CaseQualityReport

def score_case_quality(case_data: CaseData) -> CaseQualityReport:
    warnings = []
    suggested_improvements = []

    # Helper to resolve agent full name
    def get_agent_name(aid: str) -> str:
        for a in case_data.agents:
            if a.agent_id == aid:
                return a.full_name
        return aid

    # Helper to resolve location name
    def get_location_name(lid: str) -> str:
        for l in case_data.locations:
            if l.location_id == lid:
                return l.name
        return lid

    # Living suspects excluding victim and ambient background NPCs
    living_suspects = [a.agent_id for a in case_data.agents if not a.is_victim and not a.is_background]
    killer_id = case_data.case.killer_id

    # 1. Suspect Distinctiveness
    suspect_distinctiveness = 5.0
    for suspect_id in living_suspects:
        # Relationships check
        agent_obj = next((a for a in case_data.agents if a.agent_id == suspect_id), None)
        if agent_obj and len(agent_obj.relationships) < 2:
            suspect_distinctiveness -= 0.5
        # Memories check
        memories = [m for m in case_data.memories if m.owner_agent_id == suspect_id]
        if len(memories) < 2:
            suspect_distinctiveness -= 0.5
    suspect_distinctiveness = max(0.0, min(5.0, suspect_distinctiveness))

    # 2. Motive Clarity
    motive_clarity = 5.0
    killer_motive = [c for c in case_data.conclusions if c.target_agent_id == killer_id and c.type == "motive"]
    if not killer_motive:
        motive_clarity -= 3.0
        warnings.append("Killer has no motive conclusion")
        suggested_improvements.append("Add a clear motive conclusion linking the killer to the victim")

    # Find Red Herrings (living suspects that are not the killer)
    red_herrings = None
    if case_data.metadata and "red_herrings" in case_data.metadata:
        red_herrings = [rh for rh in case_data.metadata["red_herrings"] if rh in living_suspects]
    if red_herrings is None:
        red_herrings = [rh for rh in living_suspects if rh != killer_id]
    if red_herrings:
        rh_missing_motive = False
        for rh in red_herrings:
            rh_motive = [c for c in case_data.conclusions if c.target_agent_id == rh and c.type == "motive"]
            if not rh_motive:
                rh_missing_motive = True
        if rh_missing_motive:
            motive_clarity -= 1.0
            warnings.append("Some red herrings lack motive conclusions")
            suggested_improvements.append("Give all red herrings a plausible motive to increase complexity")
    motive_clarity = max(0.0, min(5.0, motive_clarity))

    # 3. Red Herring Strength
    red_herring_strength = 5.0
    if not red_herrings:
        red_herring_strength -= 3.0
        warnings.append("No red herrings found in the case")
        suggested_improvements.append("Add at least one or two red herring suspects to make the mystery interesting")
    else:
        for rh in red_herrings:
            rh_conclusions = [c for c in case_data.conclusions if c.target_agent_id == rh]
            if not rh_conclusions:
                red_herring_strength -= 3.0
                warnings.append(f"Red herring {get_agent_name(rh)} has no suspicion paths")
                suggested_improvements.append(f"Add false alibis or suspicion conclusions targeting {get_agent_name(rh)}")
            else:
                # Count clues supporting these conclusions
                supported_clues = set()
                for c in rh_conclusions:
                    supported_clues.update(c.supported_by_clue_ids)
                if len(supported_clues) < 2:
                    red_herring_strength -= 1.5
                    warnings.append(f"Red herring {get_agent_name(rh)} has very weak evidence paths")
                    suggested_improvements.append(f"Link more false clues to red herring {get_agent_name(rh)}")

        # Motive check for capping
        lack_motive_count = 0
        for rh in red_herrings:
            rh_motive = [c for c in case_data.conclusions if c.target_agent_id == rh and c.type == "motive"]
            if not rh_motive:
                lack_motive_count += 1
                warnings.append(f"Red herring {get_agent_name(rh)} lacks a motive conclusion")
                suggested_improvements.append(f"Add a motive conclusion for red herring {get_agent_name(rh)}")

        if lack_motive_count == 1:
            red_herring_strength = min(red_herring_strength, 4.0)
        elif lack_motive_count > 1:
            red_herring_strength = min(red_herring_strength, 3.0)

    # Ensure a warning cannot coexist with a perfect red_herring_strength score unless the warning is informational only.
    has_rh_warning = any(
        "red herring" in w.lower() or "suspicion path" in w.lower() or "evidence path" in w.lower()
        for w in warnings
    )
    if has_rh_warning:
        red_herring_strength = min(red_herring_strength, 4.5)

    red_herring_strength = max(0.0, min(5.0, red_herring_strength))

    # 4. Clue Distribution
    clue_distribution = 5.0
    # Clue concentration per location
    clues_per_loc = {}
    for c in case_data.clues:
        lid = c.discoverability.location_id
        if lid:
            clues_per_loc[lid] = clues_per_loc.get(lid, 0) + 1

    total_clues = len(case_data.clues)
    if total_clues > 0:
        for lid, count in clues_per_loc.items():
            if count / total_clues > 0.5:
                clue_distribution -= 2.0
                warnings.append(f"Clues are highly concentrated at {get_location_name(lid)}")
                suggested_improvements.append(f"Distribute clues away from {get_location_name(lid)} to encourage player exploration")

    # Clues per suspect check
    for suspect_id in living_suspects:
        # Check if suspect has discoverable clues
        sus_clues = [c for c in case_data.clues if c.discoverability.agent_id == suspect_id or suspect_id in c.linked_agent_ids]
        if not sus_clues:
            clue_distribution -= 1.5
            warnings.append(f"Suspect {get_agent_name(suspect_id)} has no discoverable clues linked to them")
            suggested_improvements.append(f"Link clues or add interview rules to suspect {get_agent_name(suspect_id)}")
    clue_distribution = max(0.0, min(5.0, clue_distribution))

    # 5. Location Usage Balance
    location_usage_balance = 5.0
    # Check event remapping concentration (more than 40% of non-murder events in same location)
    non_murder_events = [e for e in case_data.events if e.event_type != "murder"]
    total_non_murder = len(non_murder_events)
    if total_non_murder > 0:
        events_per_loc = {}
        for e in non_murder_events:
            events_per_loc[e.location_id] = events_per_loc.get(e.location_id, 0) + 1
        for lid, count in events_per_loc.items():
            if count / total_non_murder > 0.50:
                location_usage_balance -= 1.5
                warnings.append(f"High concentration of alibi events remapped to {get_location_name(lid)}")
                suggested_improvements.append(f"Balance alibi routines across a wider set of locations instead of {get_location_name(lid)}")

    # Check fraction of active locations used
    used_locations = set(e.location_id for e in case_data.events) | set(c.discoverability.location_id for c in case_data.clues if c.discoverability.location_id)
    active_locs_count = len(case_data.locations)
    if active_locs_count > 0:
        used_ratio = len(used_locations) / active_locs_count
        if used_ratio < 0.5:
            location_usage_balance -= 1.5
            warnings.append("Less than half of the active locations are used")
            suggested_improvements.append("Place clues or schedule events in unused locations to make full use of the map")
    location_usage_balance = max(0.0, min(5.0, location_usage_balance))

    # 6. Timeline Density
    timeline_density = 5.0
    total_events = len(case_data.events)
    if total_events < 6:
        timeline_density -= 2.0
        warnings.append("Timeline is very sparse (under 6 events)")
        suggested_improvements.append("Add more timeline events to flesh out character routines and build better alibis")
    elif total_events > 15:
        timeline_density -= 0.5
    timeline_density = max(0.0, min(5.0, timeline_density))

    # 7. Solution Fairness
    solution_fairness = 5.0
    # Killer means, motive, opportunity check
    killer_conclusions = [c for c in case_data.conclusions if c.target_agent_id == killer_id]
    k_types = [c.type for c in killer_conclusions]
    if not ("motive" in k_types and "opportunity" in k_types and "means" in k_types):
        solution_fairness -= 3.0
        warnings.append("Killer is missing means, motive, or opportunity conclusions")
        suggested_improvements.append("Ensure the killer's path has clear conclusions for means, motive, and opportunity")

    if not case_data.solution.key_clue_ids:
        solution_fairness -= 2.0
        warnings.append("No key clues are specified in the solution")
        suggested_improvements.append("Define key_clue_ids in the solution block so the judge knows what evidence is vital")
    solution_fairness = max(0.0, min(5.0, solution_fairness))

    # 8. Theme Adherence
    theme_adherence = 5.0
    # Make a simple check: if theme is custom, do we mention it in title or overview?
    custom_theme = case_data.metadata.get("theme_preset") if case_data.metadata else None
    if custom_theme and custom_theme not in ["blackmail", "debt", "betrayal"]:
        combined_text = (case_data.case.overview_text + " " + case_data.case.title).lower()
        # check if any word from custom_theme is in combined_text
        words = [w.strip(".,'\"()").lower() for w in custom_theme.split() if len(w) > 3]
        if words and not any(w in combined_text for w in words):
            theme_adherence -= 1.0
            warnings.append(f"Prose does not strongly match the custom theme '{custom_theme}'")
            suggested_improvements.append(f"Rewrite overview or title to integrate the theme '{custom_theme}'")
    theme_adherence = max(0.0, min(5.0, theme_adherence))

    # 9. Tone Consistency
    tone_consistency = 5.0
    tone = case_data.metadata.get("tone") if case_data.metadata else "standard"
    if tone == "family_friendly":
        # Check for violent terms
        dark_words = ["blood", "stab", "gore", "shoot", "mutilated", "strangle", "slashed"]
        combined_text = (case_data.case.overview_text + " " + case_data.case.scene_description).lower()
        for c in case_data.clues:
            combined_text += " " + c.description.lower()
        found_dark = [w for w in dark_words if w in combined_text]
        if found_dark:
            tone_consistency -= 1.5
            warnings.append(f"Family-friendly case contains mature/violent language: {found_dark}")
            suggested_improvements.append("Remove violent or graphic references to keep the tone family-friendly")
    tone_consistency = max(0.0, min(5.0, tone_consistency))

    # Calculate overall score as the average
    scores = [
        suspect_distinctiveness, motive_clarity, red_herring_strength,
        clue_distribution, location_usage_balance, timeline_density,
        solution_fairness, theme_adherence, tone_consistency
    ]
    overall_score = round(sum(scores) / len(scores), 2)

    return CaseQualityReport(
        suspect_distinctiveness=suspect_distinctiveness,
        motive_clarity=motive_clarity,
        red_herring_strength=red_herring_strength,
        clue_distribution=clue_distribution,
        location_usage_balance=location_usage_balance,
        timeline_density=timeline_density,
        solution_fairness=solution_fairness,
        theme_adherence=theme_adherence,
        tone_consistency=tone_consistency,
        overall_score=overall_score,
        warnings=warnings,
        suggested_improvements=suggested_improvements
    )
