"""A low-confidence structured classification from the LLM intent
classifier should be downgraded to fallback_unknown rather than forcing a
possibly-wrong scripted answer — see MIN_INTENT_CONFIDENCE."""

from app.case_store import get_case
from app.session import Session
from app.llm.client import FakeLLMClient
import app.llm.question_intent_classifier as classifier_module
from app.llm.question_intent_classifier import classify_question_intent_llm


def test_low_confidence_structured_guess_downgrades_to_fallback(monkeypatch, reset_app_state):
    case = get_case("case_001")
    sess = Session(case_id="case_001")

    def mock_get_llm_client():
        return FakeLLMClient(override_response={
            "intent": "relationship",
            "confidence": 0.4,
            "rewritten_structured_question": "Describe your relationship with someone.",
        })

    monkeypatch.setattr(classifier_module, "get_llm_client", mock_get_llm_client)

    intent = classify_question_intent_llm("Tell me about your childhood.", case, sess, agent_id="agent_ben")

    assert intent.intent == "fallback_unknown"


def test_high_confidence_structured_guess_is_kept(monkeypatch, reset_app_state):
    case = get_case("case_001")
    sess = Session(case_id="case_001")

    def mock_get_llm_client():
        return FakeLLMClient(override_response={
            "intent": "alibi",
            "confidence": 0.95,
            "rewritten_structured_question": "Where were you during the murder window?",
        })

    monkeypatch.setattr(classifier_module, "get_llm_client", mock_get_llm_client)

    intent = classify_question_intent_llm("Where were you at half seven?", case, sess, agent_id="agent_ben")

    assert intent.intent == "alibi"


def test_low_confidence_fallback_is_left_alone(monkeypatch, reset_app_state):
    """fallback_unknown itself should never be blocked by the threshold,
    even at confidence 0.0 — there's nothing to downgrade it further to."""
    case = get_case("case_001")
    sess = Session(case_id="case_001")

    def mock_get_llm_client():
        return FakeLLMClient(override_response={
            "intent": "fallback_unknown",
            "confidence": 0.0,
            "rewritten_structured_question": "Unknown question",
        })

    monkeypatch.setattr(classifier_module, "get_llm_client", mock_get_llm_client)

    intent = classify_question_intent_llm("asdkjfh", case, sess, agent_id="agent_ben")

    assert intent.intent == "fallback_unknown"
