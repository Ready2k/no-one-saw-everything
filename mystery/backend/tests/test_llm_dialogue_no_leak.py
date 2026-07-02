"""Tests that the LLM dialogue rewriting module safely blocks leaks."""

import pytest
from app.llm.dialogue_rewriter import rewrite_interview_answer
from app.llm.client import FakeLLMClient
from app.models import CaseData, Agent
import app.llm.dialogue_rewriter as rewriter_module


from app.case_store import get_case

def test_dialogue_rejects_role_labels(monkeypatch):
    """Test that role labels like 'killer' are rejected."""
    
    test_case_data = get_case("case_001")
    
    def mock_get_llm_client():
        return FakeLLMClient(override_response={"rewritten_text": "I am the killer!"})
        
    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)
    agent = test_case_data.agents[0]
    
    result = rewrite_interview_answer(
        case=test_case_data,
        agent=agent,
        question_text="Where were you?",
        deterministic_text="I was at the fountain.",
        allowed_facts=["I was at the fountain."],
        pressure_level=0.5
    )
    
    # Must fallback
    assert result.rewritten_text == "I was at the fountain."
    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"


def test_dialogue_rejects_json_leak(monkeypatch):
    """Test that json syntax is rejected."""
    
    test_case_data = get_case("case_001")
    
    def mock_get_llm_client():
        return FakeLLMClient(override_response={"rewritten_text": "Here is the JSON: { \"killer\": \"Clara\" }"})
        
    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)
    agent = test_case_data.agents[0]
    
    result = rewrite_interview_answer(
        case=test_case_data,
        agent=agent,
        question_text="Where were you?",
        deterministic_text="I was at the fountain.",
        allowed_facts=["I was at the fountain."],
        pressure_level=0.5
    )
    
    # Must fallback
    assert result.rewritten_text == "I was at the fountain."
    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"


def test_dialogue_rejects_unsupported_facts(monkeypatch):
    """Test that unsupported facts like random names are rejected."""
    
    test_case_data = get_case("case_001")
    
    def mock_get_llm_client():
        return FakeLLMClient(override_response={"rewritten_text": "I was at the fountain with Priya."})
        
    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)
    agent = test_case_data.agents[0]
    
    result = rewrite_interview_answer(
        case=test_case_data,
        agent=agent,
        question_text="Where were you?",
        deterministic_text="I was at the fountain.",
        allowed_facts=["I was at the fountain."],
        pressure_level=0.5
    )
    
    # Must fallback because "Priya" is not in allowed facts and wasn't in deterministic text
    assert result.rewritten_text == "I was at the fountain."
    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"


def test_dialogue_rejects_forbidden_facts(monkeypatch):
    """Test that forbidden hidden facts are rejected even if not using role labels."""
    
    test_case_data = get_case("case_001")
    
    def mock_get_llm_client():
        # Suppose the solution says the killer stole money from the register
        return FakeLLMClient(override_response={"rewritten_text": "I definitely didn't steal money from the register."})
        
    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)
    
    # Force the solution to contain "steal money from the register"
    test_case_data.solution.motive.concept_groups = [["steal money from the register"]]
    
    agent = test_case_data.agents[0]
    
    result = rewrite_interview_answer(
        case=test_case_data,
        agent=agent,
        question_text="Where were you?",
        deterministic_text="I was at the fountain.",
        allowed_facts=["I was at the fountain."],
        pressure_level=0.5
    )
    
    assert result.rewritten_text == "I was at the fountain."
    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"

