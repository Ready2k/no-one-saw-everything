from fastapi.testclient import TestClient
from app.main import app
from app.generator import generate_case

client = TestClient(app)

def test_deterministic_rejects_creative_options():
    # 1. Custom theme
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "custom_theme": "Space Station"
    })
    assert r.status_code == 400
    assert "Creative options" in r.json()["detail"]

    # 2. Non-standard tone
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "tone": "dark_noir"
    })
    assert r.status_code == 400
    assert "Creative options" in r.json()["detail"]

    # 3. LLM notes
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "llm_notes": "The killer should be Owen."
    })
    assert r.status_code == 400
    assert "Creative options" in r.json()["detail"]

def test_minimum_case_shape():
    # Minimum shape: 3 suspects, 3 locations
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "num_suspects": 3,
        "num_locations": 3,
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    assert data["validation"]["valid"] is True
    
    # Fetch details of active case
    agents_resp = client.get("/api/agents").json()
    # 3 suspects + 1 victim = 4 agents total
    assert len(agents_resp) == 4
    
    # Check killer and victim are present
    case_resp = client.get("/api/case").json()
    victim_id = case_resp["victim"]["agent_id"]
    
    # Confirm exactly 4 agents
    assert any(a["agent_id"] == victim_id for a in agents_resp)
    
    # Fetch locations
    locations_resp = client.get("/api/locations").json()
    assert len(locations_resp) == 3
    
    # Verify no dangling references in events
    events_resp = client.get("/api/events").json()
    for e in events_resp:
        assert e["location_id"] in [l["location_id"] for l in locations_resp]
        for aid in e["agent_ids"]:
            assert any(a["agent_id"] == aid for a in agents_resp)

def test_maximum_case_shape():
    # Maximum shape: 7 suspects, 8 locations
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "num_suspects": 7,
        "num_locations": 8,
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    assert data["validation"]["valid"] is True
    
    agents_resp = client.get("/api/agents").json()
    assert len(agents_resp) == 8 # 7 suspects + 1 victim = 8 agents
    
    locations_resp = client.get("/api/locations").json()
    assert len(locations_resp) == 8

def test_llm_mode_accepts_creative_options():
    # LLM assisted mode should accept custom theme, tone, and notes
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "llm_assisted",
        "custom_theme": "Cyberpunk Space Station",
        "tone": "dark_noir",
        "llm_notes": "The murder was clean.",
        "fallback_allowed": False
    })
    assert r.status_code == 200
    data = r.json()
    assert data["validation"]["valid"] is True
    assert data["fallback_used"] is False

def test_compaction_leaves_no_removed_agent_names_in_text_fields():
    # Generate a case with 4 suspects. This will prune 3 of the 7 witnesses.
    # Verify that the pruned agents' names (first/full) do not appear in any text field of the case data.
    from app.case_store import get_case
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "num_suspects": 4,
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    meta = data["generation_metadata"]
    pruned_agents = meta["pruned_agents"]
    assert len(pruned_agents) > 0

    # Get the actual CaseData object from backend to verify internal text fields
    case_data = get_case(data["case_id"])
    
    # Get original base agents from agents.json or case store to find their names
    import json
    from pathlib import Path
    with open(Path(__file__).parent.parent / "app/data/case_001/agents.json") as f:
        all_base_agents = json.load(f)
    
    pruned_names = []
    for aid in pruned_agents:
        agent_info = next(a for a in all_base_agents if a["agent_id"] == aid)
        pruned_names.append(agent_info["full_name"])
        pruned_names.append(agent_info["full_name"].split()[0]) # first name

    # Search all text fields in case_data for pruned names
    def assert_no_leak(text: str):
        if not text:
            return
        for name in pruned_names:
            assert name.lower() not in text.lower(), f"Leaked pruned agent name '{name}' in text: {text}"

    # Check overview, scene desc, etc.
    assert_no_leak(case_data.case.overview_text)
    assert_no_leak(case_data.case.scene_description)
    assert_no_leak(case_data.case.motive_summary)
    assert_no_leak(case_data.solution.explanation)
    assert_no_leak(case_data.solution.motive.canonical)

    for agent in case_data.agents:
        assert_no_leak(agent.routine_summary)
        assert_no_leak(agent.voice_card)

    for clue in case_data.clues:
        assert_no_leak(clue.title)
        assert_no_leak(clue.description)
        if clue.discoverability and clue.discoverability.discovery_text:
            assert_no_leak(clue.discoverability.discovery_text)

    for event in case_data.events:
        assert_no_leak(event.truth_description)
        assert_no_leak(event.player_description)

    for m in case_data.memories:
        assert_no_leak(m.summary)

    for pack in case_data.interview_packs:
        for rule in pack.rules:
            assert_no_leak(rule.answer_text)

def test_compaction_leaves_no_removed_location_names_in_text_fields():
    # Generate a case with 4 locations. Prunes some locations.
    # Verify that the name of the pruned locations do not appear in text fields.
    from app.case_store import get_case
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "num_locations": 4,
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    meta = data["generation_metadata"]
    remapped = meta["remapped_locations"]
    assert len(remapped) > 0

    case_data = get_case(data["case_id"])

    # Load original locations to find names of pruned locations
    import json
    from pathlib import Path
    with open(Path(__file__).parent.parent / "app/data/case_001/locations.json") as f:
        all_locations = json.load(f)

    pruned_location_names = []
    for old_loc_id in remapped.keys():
        loc_info = next(l for l in all_locations if l["location_id"] == old_loc_id)
        pruned_location_names.append(loc_info["name"])

    def assert_no_leak(text: str):
        if not text:
            return
        for name in pruned_location_names:
            assert name.lower() not in text.lower(), f"Leaked pruned location name '{name}' in text: {text}"

    assert_no_leak(case_data.case.overview_text)
    assert_no_leak(case_data.case.scene_description)
    for clue in case_data.clues:
        assert_no_leak(clue.title)
        assert_no_leak(clue.description)
    for event in case_data.events:
        assert_no_leak(event.truth_description)
        assert_no_leak(event.player_description)

def test_each_living_suspect_has_interview_pack():
    # Verify that every suspect (living member of village, excluding victim) has an interview pack
    # after compaction.
    from app.case_store import get_case
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "num_suspects": 4,
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    case_data = get_case(data["case_id"])
    
    living_suspects = [a.agent_id for a in case_data.agents if not a.is_victim]
    interview_agent_ids = [p.agent_id for p in case_data.interview_packs]
    
    for agent_id in living_suspects:
        assert agent_id in interview_agent_ids, f"Agent {agent_id} has no interview pack"

def test_each_living_suspect_has_at_least_one_suspicion_hook():
    # Every living suspect must have at least one conclusion/suspicion hook pointing to them.
    from app.case_store import get_case
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "num_suspects": 4,
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    case_data = get_case(data["case_id"])
    
    killer_id = case_data.case.killer_id
    target_agents_in_conclusions = {c.target_agent_id for c in case_data.conclusions}
    
    # Verify killer has suspicion hooks pointing to them
    assert killer_id in target_agents_in_conclusions
    
    # Verify at least the red herrings are targeted too
    non_killer_targeted = {c.target_agent_id for c in case_data.conclusions if c.target_agent_id != killer_id}
    assert len(non_killer_targeted) >= 2

def test_killer_has_means_motive_opportunity_after_compaction():
    # Verify the killer has conclusions/clues supporting means, motive, and opportunity after compaction.
    from app.case_store import get_case
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "num_suspects": 4,
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    case_data = get_case(data["case_id"])
    
    killer_id = case_data.case.killer_id
    killer_conclusions = [c for c in case_data.conclusions if c.target_agent_id == killer_id]
    
    types = [c.type for c in killer_conclusions]
    assert "motive" in types
    assert "opportunity" in types
    assert "means" in types

def test_red_herrings_have_distinct_false_suspicion_paths():
    # Verify that red herrings have conclusions pointing to them (so they have false paths)
    from app.case_store import get_case
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "num_suspects": 4,
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    case_data = get_case(data["case_id"])
    
    # Re-derive Red Herrings based on seed 42
    import random
    import json
    from pathlib import Path
    with open(Path(__file__).parent.parent / "app/data/case_001/agents.json") as f:
        base_agents = json.load(f)
    rng = random.Random(42)
    rng.shuffle(base_agents)
    rh1_id = base_agents[2]["agent_id"]
    rh2_id = base_agents[3]["agent_id"]
    red_herrings = [rh1_id, rh2_id]
    
    for rh in red_herrings:
        rh_conclusions = [c for c in case_data.conclusions if c.target_agent_id == rh]
        assert len(rh_conclusions) > 0, f"Red herring {rh} has no suspicion paths"

def test_family_friendly_prompt_excludes_dark_noir_language():
    from unittest.mock import patch, MagicMock
    with patch("app.llm.mystery_architect.get_llm_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        from app.llm.client import VALID_FAKE_PLAN
        def side_effect(*args, **kwargs):
            schema = kwargs.get("schema")
            if schema.__name__ == "PlotOutlinePlan":
                return schema.model_validate({
                    "title": "The Fake Planner Murder",
                    "motive_variant": "The victim was blackmailed.",
                    "victim_rationale": "Victim was angry.",
                    "killer_rationale": "Killer had enough.",
                    "red_herring_rationales": {
                        "{RH1_ID}": "Has a dark secret.",
                        "{RH2_ID}": "Wanted the victim dead too."
                    },
                    "scene_description": "The fake murder scene description."
                })
            elif schema.__name__ == "CluesPlan":
                return schema.model_validate({"clue_plans": VALID_FAKE_PLAN["clue_plans"]})
            elif schema.__name__ == "MemoriesPlan":
                return schema.model_validate({
                    "seeded_memories": VALID_FAKE_PLAN["seeded_memories"],
                    "witness_fragments": VALID_FAKE_PLAN["witness_fragments"]
                })
            elif schema.__name__ == "RoleMemoriesPlan":
                last_message = kwargs.get("messages", [])[-1]["content"] if kwargs.get("messages") else ""
                if "{KILLER_ID}" in last_message:
                    return schema.model_validate({"memories": VALID_FAKE_PLAN["seeded_memories"]})
                return schema.model_validate({"memories": []})
            elif schema.__name__ == "WitnessFragmentsPlan":
                return schema.model_validate({"witness_fragments": VALID_FAKE_PLAN["witness_fragments"]})
            elif schema.__name__ == "FlavourPlan":
                return schema.model_validate({
                    "interview_flavour": VALID_FAKE_PLAN["interview_flavour"],
                    "reveal_narration": VALID_FAKE_PLAN["reveal_narration"]
                })
            return MagicMock()

        mock_client.generate_chat.side_effect = side_effect
        
        client.post("/api/cases/generate", json={
            "case_type": "blackmail",
            "difficulty": "standard",
            "seed": 42,
            "mode": "llm_assisted",
            "tone": "family_friendly",
            "fallback_allowed": False
        })
        
        assert mock_client.generate_chat.called
        combined = ""
        for call in mock_client.generate_chat.call_args_list:
            messages = call[1]["messages"]
            combined += " ".join(msg["content"] for msg in messages) + " "
            
        combined = combined.lower()
        # Verify tone instruction exists
        assert "family_friendly" in combined or "cozy" in combined
        assert "dark_noir" not in combined

def test_dark_noir_prompt_does_not_include_explicit_gore_or_sexual_content():
    from unittest.mock import patch, MagicMock
    with patch("app.llm.mystery_architect.get_llm_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        from app.llm.client import VALID_FAKE_PLAN
        def side_effect(*args, **kwargs):
            schema = kwargs.get("schema")
            if schema.__name__ == "PlotOutlinePlan":
                return schema.model_validate({
                    "title": "The Fake Planner Murder",
                    "motive_variant": "The victim was blackmailed.",
                    "victim_rationale": "Victim was angry.",
                    "killer_rationale": "Killer had enough.",
                    "red_herring_rationales": {
                        "{RH1_ID}": "Has a dark secret.",
                        "{RH2_ID}": "Wanted the victim dead too."
                    },
                    "scene_description": "The fake murder scene description."
                })
            elif schema.__name__ == "CluesPlan":
                return schema.model_validate({"clue_plans": VALID_FAKE_PLAN["clue_plans"]})
            elif schema.__name__ == "MemoriesPlan":
                return schema.model_validate({
                    "seeded_memories": VALID_FAKE_PLAN["seeded_memories"],
                    "witness_fragments": VALID_FAKE_PLAN["witness_fragments"]
                })
            elif schema.__name__ == "RoleMemoriesPlan":
                last_message = kwargs.get("messages", [])[-1]["content"] if kwargs.get("messages") else ""
                if "{KILLER_ID}" in last_message:
                    return schema.model_validate({"memories": VALID_FAKE_PLAN["seeded_memories"]})
                return schema.model_validate({"memories": []})
            elif schema.__name__ == "WitnessFragmentsPlan":
                return schema.model_validate({"witness_fragments": VALID_FAKE_PLAN["witness_fragments"]})
            elif schema.__name__ == "FlavourPlan":
                return schema.model_validate({
                    "interview_flavour": VALID_FAKE_PLAN["interview_flavour"],
                    "reveal_narration": VALID_FAKE_PLAN["reveal_narration"]
                })
            return MagicMock()

        mock_client.generate_chat.side_effect = side_effect
        
        client.post("/api/cases/generate", json={
            "case_type": "blackmail",
            "difficulty": "standard",
            "seed": 42,
            "mode": "llm_assisted",
            "tone": "dark_noir",
            "fallback_allowed": False
        })
        
        assert mock_client.generate_chat.called
        combined = ""
        for call in mock_client.generate_chat.call_args_list:
            messages = call[1]["messages"]
            combined += " ".join(msg["content"] for msg in messages) + " "
            
        combined = combined.lower()
        assert "dark_noir" in combined or "gritty" in combined
        assert "sexual" in combined or "gore" in combined or "explicit" in combined or "inappropriate" in combined

def test_quality_scoring_balanced_case():
    from app.case_store import get_case
    from app.quality import score_case_quality
    
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    case_data = get_case(data["case_id"])
    
    report = score_case_quality(case_data)
    assert report.overall_score >= 4.0
    assert 0.0 <= report.overall_score <= 5.0
    assert len(report.warnings) <= 3

def test_quality_scoring_clue_concentration():
    from app.case_store import get_case
    from app.quality import score_case_quality
    import copy
    
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    case_data = copy.deepcopy(get_case(data["case_id"]))
    
    # Concentrate all clues in one location
    for c in case_data.clues:
        c.discoverability.location_id = "loc_rear_alley"
        
    report = score_case_quality(case_data)
    assert report.clue_distribution < 4.0
    assert any("highly concentrated" in w.lower() for w in report.warnings)
    assert 0.0 <= report.overall_score <= 5.0

def test_quality_scoring_weak_red_herring():
    from app.case_store import get_case
    from app.quality import score_case_quality
    import copy
    import random
    import json
    from pathlib import Path
    
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    case_data = copy.deepcopy(get_case(data["case_id"]))
    
    # Load original red herring ID
    with open(Path(__file__).parent.parent / "app/data/case_001/agents.json") as f:
        base_agents = json.load(f)
    rng = random.Random(42)
    rng.shuffle(base_agents)
    rh1_id = base_agents[2]["agent_id"]
    
    # Remove conclusions targeting red herring 1
    case_data.conclusions = [c for c in case_data.conclusions if c.target_agent_id != rh1_id]
    
    report = score_case_quality(case_data)
    assert report.red_herring_strength < 4.0
    assert any("no suspicion paths" in w.lower() for w in report.warnings)
    assert 0.0 <= report.overall_score <= 5.0

def test_quality_scoring_missing_suspicion_hooks():
    from app.case_store import get_case
    from app.quality import score_case_quality
    import copy
    
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "activate": True
    })
    assert r.status_code == 200
    data = r.json()
    case_data = copy.deepcopy(get_case(data["case_id"]))
    
    # Remove all conclusions except those targeting the killer
    killer_id = case_data.case.killer_id
    case_data.conclusions = [c for c in case_data.conclusions if c.target_agent_id == killer_id]
    
    report = score_case_quality(case_data)
    assert any("no suspicion paths" in w.lower() for w in report.warnings)
    assert 0.0 <= report.overall_score <= 5.0

def test_candidate_count_boundaries():
    # 0 should fail pydantic validation (or be clipped, but since we set ge=1 it fails validation)
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "candidate_count": 0
    })
    assert r.status_code == 422 # Unprocessable Entity
    
    # 6 should fail Pydantic validation (max 5)
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "candidate_count": 6
    })
    assert r.status_code == 422 # Unprocessable Entity

def test_best_of_n_selects_highest_score():
    from unittest.mock import patch
    from app.models import CaseQualityReport
    
    with patch("app.quality.score_case_quality") as mock_score:
        # Mock score for seed 42, 43, 44
        reports = {
            42: CaseQualityReport(suspect_distinctiveness=3.0, motive_clarity=3.0, red_herring_strength=3.0, clue_distribution=3.0, location_usage_balance=3.0, timeline_density=3.0, solution_fairness=3.0, theme_adherence=3.0, tone_consistency=3.0, overall_score=3.0),
            43: CaseQualityReport(suspect_distinctiveness=4.5, motive_clarity=4.5, red_herring_strength=4.5, clue_distribution=4.5, location_usage_balance=4.5, timeline_density=4.5, solution_fairness=4.5, theme_adherence=4.5, tone_consistency=4.5, overall_score=4.5),
            44: CaseQualityReport(suspect_distinctiveness=2.0, motive_clarity=2.0, red_herring_strength=2.0, clue_distribution=2.0, location_usage_balance=2.0, timeline_density=2.0, solution_fairness=2.0, theme_adherence=2.0, tone_consistency=2.0, overall_score=2.0)
        }
        def side_effect(case_data):
            seed = case_data.metadata.get("seed")
            return reports.get(seed, reports[42])
            
        mock_score.side_effect = side_effect
        
        r = client.post("/api/cases/generate", json={
            "case_type": "blackmail",
            "difficulty": "standard",
            "seed": 42,
            "mode": "deterministic",
            "candidate_count": 3
        })
        assert r.status_code == 200
        data = r.json()
        
        metadata = data["generation_metadata"]
        assert metadata["best_of_n_used"] is True
        assert metadata["selected_seed"] == 43
        assert metadata["quality_report"]["overall_score"] == 4.5
        
        scores = metadata["candidate_scores"]
        assert len(scores) == 3
        assert scores[0]["seed"] == 42
        assert scores[0]["overall_score"] == 3.0
        assert scores[1]["seed"] == 43
        assert scores[1]["overall_score"] == 4.5
        assert scores[2]["seed"] == 44
        assert scores[2]["overall_score"] == 2.0

def test_single_candidate_behavior_unchanged():
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "candidate_count": 1
    })
    assert r.status_code == 200
    data = r.json()
    metadata = data["generation_metadata"]
    assert metadata["best_of_n_used"] is False
    assert "candidate_scores" in metadata
    assert len(metadata["candidate_scores"]) == 1
    assert metadata["candidate_scores"][0]["seed"] == 42

def test_regenerate_uses_same_recipe_but_different_seed():
    recipe = {
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "num_suspects": 5,
        "num_locations": 5
    }
    r1 = client.post("/api/cases/generate", json=recipe)
    assert r1.status_code == 200
    d1 = r1.json()
    
    recipe_new_seed = {**recipe, "seed": 43}
    r2 = client.post("/api/cases/generate", json=recipe_new_seed)
    assert r2.status_code == 200
    d2 = r2.json()
    
    assert d1["case_id"] != d2["case_id"]
    assert d1["generation_metadata"]["num_suspects"] == d2["generation_metadata"]["num_suspects"]
    assert d1["generation_metadata"]["num_locations"] == d2["generation_metadata"]["num_locations"]

def test_red_herring_metadata_is_unique():
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic",
        "candidate_count": 1
    })
    assert r.status_code == 200
    data = r.json()
    metadata = data["generation_metadata"]
    assert "red_herrings" in metadata
    rhs = metadata["red_herrings"]
    assert len(rhs) == len(set(rhs))

def test_red_herring_strength_not_perfect_when_motive_warning_exists():
    from app.case_store import get_case
    from app.quality import score_case_quality
    import copy
    
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic"
    })
    assert r.status_code == 200
    data = r.json()
    case_data = copy.deepcopy(get_case(data["case_id"]))
    
    # Remove all motive conclusions for red herrings
    case_data.conclusions = [c for c in case_data.conclusions if not (c.target_agent_id in case_data.metadata["red_herrings"] and c.type == "motive")]
    
    report = score_case_quality(case_data)
    assert report.red_herring_strength < 5.0
    assert any("lacks a motive conclusion" in w or "lack motive conclusions" in w for w in report.warnings)

def test_remapped_locations_do_not_target_pruned_agent_private_locations():
    from app.generator import compact_case_data
    from app.case_store import get_case
    import copy
    
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic"
    })
    assert r.status_code == 200
    data = r.json()
    case_data = copy.deepcopy(get_case(data["case_id"]))
    
    compacted = compact_case_data(case_data, num_suspects=3, num_locations=4, seed=42, roles={})
    kept_locs = {l.location_id for l in compacted.locations}
    remapped = compacted.metadata.get("remapped_locations", {})
    
    for old_loc, new_loc in remapped.items():
        assert new_loc in kept_locs
        assert new_loc not in ["loc_priya_home", "loc_priya_work"]

def test_public_location_not_remapped_to_private_location_unless_allowed():
    from app.generator import compact_case_data
    from app.case_store import get_case
    import copy
    
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 42,
        "mode": "deterministic"
    })
    assert r.status_code == 200
    data = r.json()
    case_data = copy.deepcopy(get_case(data["case_id"]))
    
    for l in case_data.locations:
        if l.location_id in ["loc_village_square", "loc_rear_alley"]:
            l.location_type = "public"
            l.visibility_type = "public"
        else:
            l.location_type = "private"
            l.visibility_type = "private"
            
    compacted = compact_case_data(case_data, num_suspects=5, num_locations=4, seed=42, roles={})
    remapped = compacted.metadata.get("remapped_locations", {})
    if "loc_village_square" in remapped:
        assert remapped["loc_village_square"] == "loc_rear_alley"
