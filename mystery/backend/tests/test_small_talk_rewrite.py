"""Small talk previously never reached the LLM rewrite pipeline at all —
a friendly rapport-building question always got the same flat canned line,
LLM configured or not. These tests lock in that small talk now goes through
the same trusted rewrite+sanitiser as every grounded answer when a rewrite
model is configured, and is untouched (same canned line) when it is not.
"""

from app.case_store import get_case
from app.free_text_api import handle_free_text
from app.llm.client import FakeLLMClient
from app.llm.config import LLMConfig
from app.models import FreeTextAskRequest
from app.session import Session
import app.free_text_api as free_text_api_module
import app.llm.dialogue_rewriter as rewriter_module


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


def test_small_talk_uses_llm_rewrite_when_dialogue_enabled(monkeypatch):
    case = get_case("case_005")
    sess = Session("test_small_talk_rewrite_enabled")
    agent_id = next(a.agent_id for a in case.agents if not a.is_background and a.agent_id != case.case.victim_id)

    monkeypatch.setattr(free_text_api_module, "get_llm_config", _dialogue_enabled_config)
    monkeypatch.setattr(
        rewriter_module,
        "get_llm_client",
        lambda: FakeLLMClient(override_response={"rewritten_text": "It's been a rough morning, honestly."}),
    )

    resp = handle_free_text(
        FreeTextAskRequest(agent_id=agent_id, question="How are you holding up?"), case, sess
    )

    assert resp.intent.intent == "how_are_you"
    assert resp.answer["llm_rewrite_used"] is True
    assert resp.answer["answer_text"] == "It's been a rough morning, honestly."
    # The canned line is preserved as ground truth even though it isn't displayed.
    assert resp.answer["deterministic_answer_text"] != resp.answer["answer_text"]


def test_small_talk_keeps_canned_line_when_dialogue_disabled():
    case = get_case("case_005")
    sess = Session("test_small_talk_rewrite_disabled")
    agent_id = next(a.agent_id for a in case.agents if not a.is_background and a.agent_id != case.case.victim_id)

    resp = handle_free_text(
        FreeTextAskRequest(agent_id=agent_id, question="How are you holding up?"), case, sess
    )

    assert resp.intent.intent == "how_are_you"
    assert resp.answer["llm_rewrite_used"] is False
    assert resp.answer["answer_text"] == resp.answer["deterministic_answer_text"]


def test_small_talk_rewrite_is_still_sanitised(monkeypatch):
    case = get_case("case_005")
    sess = Session("test_small_talk_rewrite_sanitised")
    agent_id = next(a.agent_id for a in case.agents if not a.is_background and a.agent_id != case.case.victim_id)

    monkeypatch.setattr(free_text_api_module, "get_llm_config", _dialogue_enabled_config)
    monkeypatch.setattr(
        rewriter_module,
        "get_llm_client",
        lambda: FakeLLMClient(override_response={"rewritten_text": "Between us, I am the killer."}),
    )

    resp = handle_free_text(
        FreeTextAskRequest(agent_id=agent_id, question="How are you holding up?"), case, sess
    )

    assert resp.answer["llm_rewrite_fallback"] is True
    assert "killer" not in resp.answer["answer_text"].lower()
