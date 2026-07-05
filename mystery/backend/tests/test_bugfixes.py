"""Regression tests for the post-phase-10 bug-fix pass."""

from fastapi.testclient import TestClient

from app.main import app
from app.case_store import get_case
from app.session import get_session
from app.llm.client import FakeLLMClient

client = TestClient(app)


# ---------------------------------------------------------------------------
# LLM question-intent classifier actually calls the client (was a TypeError)
# ---------------------------------------------------------------------------

def test_llm_intent_classifier_uses_llm_result(monkeypatch):
    import app.llm.question_intent_classifier as qic

    def mock_get_llm_client():
        return FakeLLMClient(override_response={
            "intent": "alibi",
            "confidence": 0.9,
            "rewritten_structured_question": "Where were you?",
            # The LLM tries to smuggle in an undiscovered clue reference:
            "referenced_clue_id": "clue_ledger_page",
        })

    monkeypatch.setattr(qic, "get_llm_client", mock_get_llm_client)
    case = get_case("case_001")
    sess = get_session("case_001")

    intent = qic.classify_question_intent_llm("erm so like, that morning??", case, sess)
    assert intent.intent == "alibi"  # not fallback_unknown — the call worked
    # Reference clamped to the safe resolver output (nothing discovered).
    assert intent.referenced_clue_id is None


def test_llm_intent_classifier_fake_default_degrades_gracefully():
    import app.llm.question_intent_classifier as qic

    case = get_case("case_001")
    sess = get_session("case_001")
    intent = qic.classify_question_intent_llm("complete nonsense zzz", case, sess)
    assert intent.intent == "fallback_unknown"


# ---------------------------------------------------------------------------
# Free-text explicit challenge guardrail failure degrades, not 500
# ---------------------------------------------------------------------------

def test_free_text_challenge_guardrail_returns_fallback(monkeypatch):
    from app import free_text_api
    from app.challenge import ChallengeError
    from app.models import FreeTextAskRequest, QuestionIntent

    def boom(case, sess, req):
        raise ChallengeError(400, "You can only challenge with evidence you have discovered.")

    monkeypatch.setattr(free_text_api.challenge_engine, "resolve_challenge", boom)
    # Force an explicit_challenge intent that reaches the resolver.
    monkeypatch.setattr(
        free_text_api,
        "classify_question",
        lambda q, c, s: QuestionIntent(
            intent="explicit_challenge",
            confidence=0.9,
            referenced_clue_id="clue_ben_sighting",
            rewritten_structured_question="I challenge you.",
        ),
    )

    case = get_case("case_001")
    sess = get_session("case_001")
    # Seed the state the mapping path needs: a claim + discovered evidence.
    client.post("/api/interview/ask", json={"agent_id": "agent_clara", "question_type": "alibi"})
    sess.discovered_clue_ids.add("clue_ben_sighting")

    resp = free_text_api.handle_free_text(
        FreeTextAskRequest(agent_id="agent_clara", question="I challenge your alibi!"),
        case,
        sess,
    )
    assert resp.challenge_result is None
    assert "discovered" in (resp.fallback_message or "")


# ---------------------------------------------------------------------------
# /api/config reflects the real MYSTERY_LLM_* configuration
# ---------------------------------------------------------------------------

def test_config_reflects_llm_env(monkeypatch):
    monkeypatch.setenv("MYSTERY_LLM_DIALOGUE_ENABLED", "true")
    monkeypatch.setenv("MYSTERY_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("MYSTERY_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("MYSTERY_LLM_MODEL", "test-model")

    cfg = client.get("/api/config").json()
    assert cfg["llm_dialogue_enabled"] is True
    assert cfg["llm_generation_available"] is True


def test_config_defaults_off():
    cfg = client.get("/api/config").json()
    assert cfg["llm_dialogue_enabled"] is False
    assert cfg["llm_generation_available"] is False


# ---------------------------------------------------------------------------
# Re-generating with activate=true starts a fresh session
# ---------------------------------------------------------------------------

def test_generate_with_activate_resets_session():
    payload = {
        "case_type": "blackmail",
        "difficulty": "standard",
        "seed": 777,
        "activate": True,
        "mode": "deterministic",
        "fallback_allowed": True,
    }
    r = client.post("/api/cases/generate", json=payload).json()
    assert r["active_session_id"] == r["case_id"]

    # Make progress in the generated case. The crime path is remapped per
    # seed, so find whichever location exposes an ungated hotspot.
    from helpers import inspect_and_discover

    found = []
    for loc in client.get("/api/locations").json():
        found = inspect_and_discover(client, loc["location_id"])
        if found:
            break
    assert found, "expected some location to expose at least one hotspot"
    assert client.get("/api/status").json()["discovered_clue_count"] > 0

    # Re-generate the identical case (same type+seed) and activate again.
    client.post("/api/cases/generate", json=payload)
    assert client.get("/api/status").json()["discovered_clue_count"] == 0


# ---------------------------------------------------------------------------
# Suggestion polling logs telemetry once per suggestion, not per poll
# ---------------------------------------------------------------------------

def test_challenge_suggestion_telemetry_deduped():
    client.post("/api/interview/ask", json={"agent_id": "agent_clara", "question_type": "alibi"})
    client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_ben", "question_type": "timeline", "time_reference": "07:47"},
    )
    for _ in range(5):
        client.get("/api/challenge/suggestions")
    log = client.get("/api/session/log").json()
    suggested = [e for e in log if e["type"] == "challenge_suggested"]
    assert len(suggested) == len({e["data"]["challenged_claim_id"] for e in suggested}), (
        "each suggested claim should be logged once, not once per poll"
    )


# ---------------------------------------------------------------------------
# Rewrite sanitiser: word-boundary name check, no hardcoded cast member
# ---------------------------------------------------------------------------

def test_sanitise_allows_been_but_blocks_unsupported_names():
    from app.llm.dialogue_rewriter import _sanitise

    case = get_case("case_001")
    # "been" must not trip the "Ben" check.
    ok = _sanitise(
        "I have been at the fountain all morning.",
        forbidden_facts=[],
        allowed_facts=["I was at the fountain."],
        case=case,
        allowed_context=["Where were you?", "I was at the fountain."],
    )
    assert ok is None

    # An unmentioned cast member is a hallucinated fact — any of them, not just Priya.
    rejected = _sanitise(
        "I was at the fountain with Nadia.",
        forbidden_facts=[],
        allowed_facts=["I was at the fountain."],
        case=case,
        allowed_context=["Where were you?", "I was at the fountain."],
    )
    assert rejected is not None and "Nadia" in rejected


# ---------------------------------------------------------------------------
# Telemetry now records inspections and all clue-discovery sources
# ---------------------------------------------------------------------------

def test_telemetry_covers_inspection_and_discovery_sources():
    from helpers import inspect_and_discover

    inspect_and_discover(client, "loc_cafe_storage")
    client.post("/api/events/ev_0756_sound/pin")
    client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_ben", "question_type": "timeline", "time_reference": "07:47"},
    )
    log = client.get("/api/session/log").json()
    types = {e["type"] for e in log}
    assert "inspection_performed" in types
    sources = {e["data"].get("source") for e in log if e["type"] == "clue_discovered"}
    # Inspection discoveries are claimed through the magnifying-glass search.
    assert {"magnifying_glass", "observation", "interview"} <= sources
