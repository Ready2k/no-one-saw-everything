import pytest
from pydantic import ValidationError

from app.llm.schemas import CasePlan, CluePlan
from app.llm.client import FakeLLMClient, VALID_FAKE_PLAN
from app.llm.case_assembler import assemble_case
from app.llm.mystery_architect import generate_llm_case
from app.generator import generate_case
from app.models import CaseData

def test_llm_case_plan_schema_valid():
    plan = CasePlan.model_validate(VALID_FAKE_PLAN)
    assert plan.case_type == "blackmail"
    assert plan.title == "The Fake Planner Murder"
    assert len(plan.clue_plans) == 3

def test_llm_case_plan_schema_invalid():
    with pytest.raises(ValidationError):
        # Missing required fields
        CasePlan.model_validate({"case_type": "invalid_type"})

def test_llm_case_assembler():
    plan = CasePlan.model_validate(VALID_FAKE_PLAN)
    # Get a base case deterministic output
    base_case, _, _, _ = generate_case("blackmail", "standard", 42, mode="deterministic")
    
    # We will simulate the roles that generate_case would have produced
    roles = {
        "{VICTIM_ID}": base_case.case.victim_id,
        "{KILLER_ID}": base_case.solution.killer_id,
        "{WITNESS1_ID}": base_case.agents[4].agent_id
    }
    
    assembled = assemble_case(plan, base_case, roles, 42)
    assert assembled.case.title == "The Fake Planner Murder"
    assert assembled.case.motive_summary == "The victim was blackmailed."
    
    # Check clues were added
    assert any("clue_llm" in c.clue_id for c in assembled.clues)

def test_llm_generation_pipeline_success(monkeypatch):
    # The default FakeLLMClient returns a VALID_FAKE_PLAN which should pass validation
    base_case, _, _, _ = generate_case("blackmail", "standard", 42, mode="deterministic")
    
    # Fake roles for testing
    roles = {
        "{VICTIM_ID}": base_case.case.victim_id,
        "{KILLER_ID}": base_case.solution.killer_id,
    }
    
    # Ensure FakeLLMClient is used (the default)
    case_data, reason, attempts = generate_llm_case(base_case, roles, "blackmail", "standard", 42)
    assert case_data is not None
    assert case_data.case.title == "The Fake Planner Murder"
    assert reason is None

def test_llm_fallback_behaviour_when_allowed(monkeypatch):
    def faulty_generate(*args, **kwargs):
        return None, "provider_timeout", 0
        
    monkeypatch.setattr("app.llm.mystery_architect.generate_llm_case", faulty_generate)
    
    case_data, fallback_used, reason, attempts = generate_case("blackmail", "standard", 42, mode="llm_assisted", fallback_allowed=True)
    assert fallback_used is True
    assert reason == "provider_timeout"
    assert case_data.case.title != "The Fake Planner Murder"  # It's the deterministic template title

def test_llm_fallback_behaviour_when_disallowed(monkeypatch):
    def faulty_generate(*args, **kwargs):
        return None, "provider_timeout", 0
        
    monkeypatch.setattr("app.llm.mystery_architect.generate_llm_case", faulty_generate)
    
    with pytest.raises(RuntimeError) as exc_info:
        generate_case("blackmail", "standard", 42, mode="llm_assisted", fallback_allowed=False)
    
    assert "LLM generation failed (provider_timeout) and fallback not allowed" in str(exc_info.value)

def test_api_fallback_safety():
    from fastapi.testclient import TestClient
    from app.main import app, ACTIVE_CASE_ID
    import app.main as main
    client = TestClient(app)
    
    initial_active_case = main.ACTIVE_CASE_ID
    
    # Ask for activate=false, and use a seed so we know it generates something new
    r = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 999,
        "activate": False,
        "mode": "llm_assisted",
        "fallback_allowed": True
    })
    
    # Should succeed, probably without fallback if FakeLLMClient works
    # Wait, FakeLLMClient might be configured. Let's assume it generated successfully or fell back safely.
    assert r.status_code == 200
    assert main.ACTIVE_CASE_ID == initial_active_case  # active case must NOT change!
    
    # Now simulate a failure with activate=True
    # Force a failure using a bad config
    import os
    os.environ["MYSTERY_LLM_PROVIDER"] = "openai_compatible"
    os.environ["MYSTERY_LLM_BASE_URL"] = "" # Invalid
    
    r2 = client.post("/api/cases/generate", json={
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 999,
        "activate": True,
        "mode": "llm_assisted",
        "fallback_allowed": True
    })
    
    assert r2.status_code == 200
    data = r2.json()
    assert data["fallback_used"] is True
    assert data["fallback_reason"] == "llm_not_configured"
    # Even though fallback was used, since the fallback is a VALID deterministic case, it should activate
    assert main.ACTIVE_CASE_ID == data["case_id"]
    assert data["case_id"] != initial_active_case
    
    # Clean up
    os.environ["MYSTERY_LLM_PROVIDER"] = "fake"
