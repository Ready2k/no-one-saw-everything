"""Tests for layer7.py and its wiring into PersonaSession's claim store.

No real network calls: every test that exercises try_claim_reasoning either
stays under the disabled/under-claimed no-op paths (which never reach
urllib), or monkeypatches layer7._call_ollama directly.
"""

from __future__ import annotations

import urllib.error

import layer7
from claims import Claim
from engine import PersonaSession


def _claim(topic: str, text: str) -> Claim:
    return Claim(claim_id=f"claim_{topic}", speaker_agent_id="agent_owen",
                 claim_text=text, topic=topic)


# ---------------------------------------------------------------------------
# PersonaSession -> ClaimStore wiring
# ---------------------------------------------------------------------------


def test_fact_reveal_logs_a_claim():
    session = PersonaSession("owen")
    assert session.claim_store.claims == []

    result = session.ask("where were you this morning")
    assert result["topic"] == "alibi"
    assert len(session.claim_store.claims) == 1
    claim = session.claim_store.claims[0]
    assert claim.topic == "alibi"
    assert claim.speaker_agent_id == "agent_owen"
    assert claim.claim_text  # the canonical fact text, not the rendered line


def test_repeat_question_does_not_log_a_second_claim():
    session = PersonaSession("owen")
    session.ask("where were you this morning")
    session.ask("where were you this morning")
    assert len(session.claim_store.claims) == 1


def test_unmatched_question_logs_nothing():
    session = PersonaSession("owen")
    result = session.ask("zzz qwerty unrelated gibberish nonsense")
    assert result["topic"] is None
    assert session.claim_store.claims == []


# ---------------------------------------------------------------------------
# try_claim_reasoning — gating (no network reached in any of these)
# ---------------------------------------------------------------------------


def test_disabled_by_default_returns_none():
    assert layer7.ENABLED is False  # true unless the env var was set for this run
    result = layer7.try_claim_reasoning(
        full_name="Owen Price", occupation="Builder", voice_card="Blunt.",
        claims=[_claim("alibi", "In his yard."), _claim("temper", "Has a temper.")],
        question="does that add up?",
    )
    assert result is None


def test_enabled_but_under_claimed_returns_none(monkeypatch):
    monkeypatch.setattr(layer7, "ENABLED", True)
    called = []
    monkeypatch.setattr(layer7, "_call_ollama", lambda messages: called.append(1) or "should not be reached")
    result = layer7.try_claim_reasoning(
        full_name="Owen Price", occupation="Builder", voice_card="Blunt.",
        claims=[_claim("alibi", "In his yard.")],  # only one claim
        question="does that add up?",
    )
    assert result is None
    assert called == []  # never even tried to call the model


# ---------------------------------------------------------------------------
# try_claim_reasoning — model call, mocked at _call_ollama
# ---------------------------------------------------------------------------


def test_enabled_with_two_claims_calls_model_and_returns_answer(monkeypatch):
    monkeypatch.setattr(layer7, "ENABLED", True)
    monkeypatch.setattr(layer7, "_call_ollama", lambda messages: '"I told you both those things already."')
    result = layer7.try_claim_reasoning(
        full_name="Owen Price", occupation="Builder", voice_card="Blunt.",
        claims=[_claim("alibi", "In his yard."), _claim("temper", "Has a temper.")],
        question="does that add up?",
    )
    assert result == "I told you both those things already."  # surrounding quotes stripped


def test_model_unreachable_degrades_to_none(monkeypatch):
    monkeypatch.setattr(layer7, "ENABLED", True)

    def _raise(req, timeout):
        raise urllib.error.URLError("connection refused")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _raise)
    result = layer7.try_claim_reasoning(
        full_name="Owen Price", occupation="Builder", voice_card="Blunt.",
        claims=[_claim("alibi", "In his yard."), _claim("temper", "Has a temper.")],
        question="does that add up?",
    )
    assert result is None


def test_empty_model_reply_treated_as_no_answer(monkeypatch):
    monkeypatch.setattr(layer7, "ENABLED", True)
    monkeypatch.setattr(layer7, "_call_ollama", lambda messages: "   ")
    result = layer7.try_claim_reasoning(
        full_name="Owen Price", occupation="Builder", voice_card="Blunt.",
        claims=[_claim("alibi", "In his yard."), _claim("temper", "Has a temper.")],
        question="does that add up?",
    )
    assert result is None


# ---------------------------------------------------------------------------
# Prompt construction — grounding sanity, not a network test
# ---------------------------------------------------------------------------


def test_prompt_includes_all_claims_and_forbids_invention():
    messages = layer7._build_messages(
        full_name="Priya Shah", occupation="Bookshop assistant",
        voice_card="Soft-spoken and apologetic.",
        claims=[_claim("alibi", "In the stockroom."), _claim("relationship", "He gave me my start.")],
        question="how do those two things fit together?",
    )
    system, user = messages[0]["content"], messages[1]["content"]
    assert "Priya Shah" in system
    assert "Soft-spoken and apologetic." in system
    assert "do not invent" in system.lower()
    assert "In the stockroom." in user
    assert "He gave me my start." in user
    assert "how do those two things fit together?" in user
