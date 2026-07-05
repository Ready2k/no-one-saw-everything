"""Tests for the LLM dialogue rewriting module."""

import pytest
from app.llm.dialogue_rewriter import rewrite_interview_answer, rewrite_challenge_response, RewriteResult
from app.llm.client import FakeLLMClient
from app.models import CaseData, Agent
import app.llm.dialogue_rewriter as rewriter_module


from app.case_store import get_case

def test_dialogue_rewrite_success(monkeypatch):
    """Test successful rewrite integration."""
    
    test_case_data = get_case("case_001")
    
    # Mock LLM client to return our desired dialogue
    def mock_get_llm_client():
        return FakeLLMClient(override_response={"rewritten_text": "I was indeed at the fountain."})
        
    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)
    
    agent = next(a for a in test_case_data.agents if a.agent_id == test_case_data.case.victim_id) # Just an agent for testing
    if not agent:
        agent = test_case_data.agents[0]
        
    result = rewrite_interview_answer(
        case=test_case_data,
        agent=agent,
        question_text="Where were you?",
        deterministic_text="I was at the fountain.",
        allowed_facts=["I was at the fountain."],
        pressure_level=0.5
    )
    
    assert result.rewritten_text == "I was indeed at the fountain."
    assert result.fallback_used is False


def test_dialogue_rewrite_provider_error_fallback(monkeypatch):
    """Test provider error falls back to deterministic text."""
    
    test_case_data = get_case("case_001")
    
    # Mock LLM client to always fail
    def mock_get_llm_client():
        return FakeLLMClient(fail_count=100) # Always fails
        
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
    
    # Fallback text is wrapped in an in-character deflection rather than
    # silently repeating the deterministic line verbatim, but must still
    # contain it exactly (nothing invented, nothing dropped).
    assert result.rewritten_text.endswith("I was at the fountain.")
    assert result.rewritten_text != "I was at the fountain."
    assert result.fallback_used is True
    assert result.fallback_reason == "provider_error"


from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_api_interview_uses_rewrite_when_enabled(monkeypatch):
    """Test that the API endpoint successfully rewrites and doesn't change state."""
    
    # 1. Enable dialogue
    monkeypatch.setenv("MYSTERY_LLM_DIALOGUE_ENABLED", "true")
    monkeypatch.setenv("MYSTERY_LLM_PROVIDER", "fake")
    
    # 2. Mock FakeLLMClient to return our expected text
    def mock_get_llm_client():
        return FakeLLMClient(override_response={"rewritten_text": "I absolutely do not know!"})
    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)

    # Start the session
    client.post("/api/session/reset")
    
    # Call the interview endpoint
    res = client.post("/api/interview/ask", json={
        "agent_id": "agent_clara",
        "question_type": "alibi"
    })
    
    assert res.status_code == 200
    data = res.json()
    assert data["llm_rewrite_used"] is True
    assert data["llm_rewrite_fallback"] is False
    assert data["answer_text"] == "I absolutely do not know!"
    
    # Ensure deterministic properties were not dropped
    assert "new_claims" in data
    assert "revealed_clues" in data


def test_api_interview_rewrites_default_answer_when_no_rule_matches(monkeypatch):
    """When an agent has no authored rule for a question type, the old
    behaviour recited pack.default_answers verbatim with no LLM involvement
    at all. That should now go through the same rewrite path as a scripted
    answer, so an agent with thin authored coverage still speaks in voice."""

    monkeypatch.setenv("MYSTERY_LLM_DIALOGUE_ENABLED", "true")
    monkeypatch.setenv("MYSTERY_LLM_PROVIDER", "fake")

    import app.interview as interview_module
    monkeypatch.setattr(interview_module, "_match_rule", lambda pack, case, session, req: None)

    def mock_get_llm_client():
        return FakeLLMClient(override_response={"rewritten_text": "Honestly? Nothing to add there."})
    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)

    client.post("/api/session/reset")
    res = client.post("/api/interview/ask", json={
        "agent_id": "agent_clara",
        "question_type": "alibi"
    })

    assert res.status_code == 200
    data = res.json()
    assert data["llm_rewrite_used"] is True
    assert data["llm_rewrite_fallback"] is False
    assert data["answer_text"] == "Honestly? Nothing to add there."
    
