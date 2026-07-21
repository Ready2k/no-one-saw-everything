"""Tests that free-text questions outside the fixed interview intents
(spec 06) can get a genuine in-character LLM reply, but never leak case
truth — the same sanitiser used for grounded rewrites guards this path too.
"""

from fastapi.testclient import TestClient

from app.llm.dialogue_rewriter import generate_open_ended_response
from app.llm.client import FakeLLMClient
from app.case_store import get_case
import app.llm.dialogue_rewriter as rewriter_module

from app.main import app

client = TestClient(app)


def test_open_ended_allows_harmless_flavour(monkeypatch):
    test_case_data = get_case("case_001")

    def mock_get_llm_client():
        return FakeLLMClient(override_response={
            "rewritten_text": "I hated my mother's cooking, if I'm honest."
        })

    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)
    agent = test_case_data.agents[0]

    result = generate_open_ended_response(
        case=test_case_data,
        agent=agent,
        question_text="Tell me about your childhood.",
        pressure_level=0.3,
    )

    assert result.fallback_used is False
    assert result.rewritten_text == "I hated my mother's cooking, if I'm honest."


def test_open_ended_rejects_role_label_leak(monkeypatch):
    test_case_data = get_case("case_001")

    def mock_get_llm_client():
        return FakeLLMClient(override_response={"rewritten_text": "Between us, I am the killer."})

    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)
    agent = test_case_data.agents[0]

    result = generate_open_ended_response(
        case=test_case_data,
        agent=agent,
        question_text="Tell me a secret.",
        pressure_level=0.3,
    )

    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"
    assert "killer" not in result.rewritten_text.lower()


def test_open_ended_rejects_forbidden_fact_leak(monkeypatch):
    test_case_data = get_case("case_001")

    def mock_get_llm_client():
        return FakeLLMClient(override_response={
            "rewritten_text": "I definitely didn't steal money from the register."
        })

    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)
    test_case_data.solution.motive.concept_groups = [["steal money from the register"]]
    agent = test_case_data.agents[0]

    result = generate_open_ended_response(
        case=test_case_data,
        agent=agent,
        question_text="Why would anyone want him dead?",
        pressure_level=0.3,
    )

    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"
    assert "register" not in result.rewritten_text.lower()


def test_open_ended_rejects_invented_named_relationship(monkeypatch):
    """The model must not invent a relationship to another real, named
    suspect it wasn't already talking about — that's how a hallucinated
    lead could mislead the player's case, same risk as a grounded rewrite
    inventing a new sighting."""
    test_case_data = get_case("case_001")

    other_agent = test_case_data.agents[1]

    def mock_get_llm_client():
        return FakeLLMClient(override_response={
            "rewritten_text": f"{other_agent.full_name.split()[0]} used to babysit me as a kid."
        })

    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)
    agent = test_case_data.agents[0]

    result = generate_open_ended_response(
        case=test_case_data,
        agent=agent,
        question_text="Tell me about your childhood.",
        pressure_level=0.3,
    )

    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"


def test_open_ended_provider_error_falls_back_safely(monkeypatch):
    test_case_data = get_case("case_001")

    def mock_get_llm_client():
        return FakeLLMClient(fail_count=100)

    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)
    agent = test_case_data.agents[0]

    result = generate_open_ended_response(
        case=test_case_data,
        agent=agent,
        question_text="Tell me about your childhood.",
        pressure_level=0.3,
    )

    assert result.fallback_used is True
    assert result.fallback_reason == "provider_error"
    assert result.rewritten_text


def test_free_text_api_uses_open_ended_when_dialogue_enabled(monkeypatch):
    """End-to-end: when dialogue rewriting is on, an out-of-taxonomy
    question gets a real in-character answer (not the canned fallback
    message), and the sanitiser still guards it."""
    monkeypatch.setenv("MYSTERY_LLM_DIALOGUE_ENABLED", "true")
    monkeypatch.setenv("MYSTERY_LLM_PROVIDER", "fake")

    def mock_get_llm_client():
        return FakeLLMClient(override_response={
            "rewritten_text": "I collected stamps as a boy. Nothing sinister about that."
        })

    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)

    client.post("/api/session/reset")
    res = client.post("/api/interview/free-text", json={
        "agent_id": "agent_clara",
        "question": "Tell me about your childhood.",
    })

    assert res.status_code == 200
    data = res.json()
    assert data["fallback_message"] is None
    assert data["answer"]["answer_text"] == "I collected stamps as a boy. Nothing sinister about that."
    assert data["answer"]["llm_rewrite_fallback"] is False


def test_free_text_api_keeps_canned_fallback_when_dialogue_disabled(monkeypatch):
    """No behaviour change for players without an LLM configured — an
    unrecognised question still gets the plain hint message, not a
    fabricated reply from the fake/off provider."""
    monkeypatch.setenv("MYSTERY_LLM_PROVIDER", "fake")
    monkeypatch.delenv("MYSTERY_LLM_DIALOGUE_ENABLED", raising=False)

    client.post("/api/session/reset")
    res = client.post("/api/interview/free-text", json={
        "agent_id": "agent_clara",
        "question": "Tell me about your childhood.",
    })

    assert res.status_code == 200
    data = res.json()
    assert data["answer"] is None
    assert "not sure what you mean" in data["fallback_message"].lower()
