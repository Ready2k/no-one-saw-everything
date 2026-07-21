"""An unresolved object/location/clue reference (undiscovered evidence, or
just not a real thing) previously always hit a flat canned deflection that
bypassed the LLM rewrite entirely, even about the actual murder weapon.
It now reacts in-character when a rewrite model is configured, and is
unchanged (same canned fallback message) when it is not.
"""

from app.case_store import get_case
from app.llm.client import FakeLLMClient
from app.llm.config import LLMConfig
from app.models import FreeTextAskRequest, QuestionIntent
from app.session import Session
import app.free_text_api as free_text_api_module
import app.llm.dialogue_rewriter as rewriter_module

from app.free_text_api import handle_free_text


def _unresolved_object_intent(*args, **kwargs) -> QuestionIntent:
    return QuestionIntent(
        intent="object",
        confidence=0.8,
        referenced_object_id=None,
        rewritten_structured_question="What do you know about this object?",
    )


def _dialogue_enabled_config() -> LLMConfig:
    return LLMConfig(
        provider="openai_compatible",
        base_url="http://fake-host/v1",
        api_key=None,
        model="fake-model",
        timeout_seconds=5,
        configured=True,
        fallback_reason=None,
        dialogue_enabled=True,
        beliefs_enabled=False,
    )


def test_unresolved_object_gets_in_character_reply_when_dialogue_enabled(monkeypatch):
    case = get_case("case_005")
    sess = Session("test_evidence_dead_end_enabled")

    monkeypatch.setattr(free_text_api_module, "classify_question", _unresolved_object_intent)
    monkeypatch.setattr(free_text_api_module, "get_llm_config", _dialogue_enabled_config)
    monkeypatch.setattr(
        rewriter_module,
        "get_llm_client",
        lambda: FakeLLMClient(override_response={
            "rewritten_text": "I don't see what that's got to do with anything."
        }),
    )

    resp = handle_free_text(
        FreeTextAskRequest(agent_id="agent_owen", question="That belt of yours?"), case, sess
    )

    assert resp.fallback_message is None
    assert resp.answer is not None
    assert resp.answer["llm_rewrite_used"] is True
    assert resp.answer["answer_text"] == "I don't see what that's got to do with anything."
    assert "observable_tells" in resp.answer


def test_unresolved_object_keeps_canned_fallback_when_dialogue_disabled(monkeypatch):
    case = get_case("case_005")
    sess = Session("test_evidence_dead_end_disabled")

    monkeypatch.setattr(free_text_api_module, "classify_question", _unresolved_object_intent)

    resp = handle_free_text(
        FreeTextAskRequest(agent_id="agent_owen", question="That belt of yours?"), case, sess
    )

    assert resp.answer is None
    assert resp.fallback_message is not None
