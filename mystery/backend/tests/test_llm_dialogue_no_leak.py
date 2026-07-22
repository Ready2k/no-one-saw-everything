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
    
    # Must fallback, wrapped in an in-character deflection rather than a bare
    # repeat of the deterministic line, but the deterministic line itself
    # must still be present verbatim and nothing rejected must leak through.
    assert result.rewritten_text.endswith("I was at the fountain.")
    # First hearing: the authored line is returned exactly as written. (A repeat is wrapped
    # in a "you've asked me that" framing — see test_repeat_answer_is_framed_as_a_repeat.)
    assert result.rewritten_text == "I was at the fountain."
    assert "killer" not in result.rewritten_text.lower()
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
    
    # Must fallback, wrapped in an in-character deflection rather than a bare
    # repeat of the deterministic line, but the deterministic line itself
    # must still be present verbatim and nothing rejected must leak through.
    assert result.rewritten_text.endswith("I was at the fountain.")
    # First hearing: the authored line is returned exactly as written. (A repeat is wrapped
    # in a "you've asked me that" framing — see test_repeat_answer_is_framed_as_a_repeat.)
    assert result.rewritten_text == "I was at the fountain."
    assert "killer" not in result.rewritten_text.lower()
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
    assert result.rewritten_text.endswith("I was at the fountain.")
    assert "priya" not in result.rewritten_text.lower()
    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"


def test_dialogue_allows_forbidden_phrase_already_in_deterministic_text(monkeypatch):
    """A rewrite must not be rejected for reusing wording that is already
    present in the deterministic answer it's rewriting, even if that wording
    also happens to appear in the solution's grading concept groups. A
    killer's false alibi is deliberately worded close to the true murder
    window (e.g. Clara's fountain alibi legitimately says 'quarter to
    eight'), and a faithful paraphrase inherits that overlap without leaking
    anything the player couldn't already see in the scripted line."""

    test_case_data = get_case("case_001")

    paraphrase = "I was at the fountain from about a quarter to eight, needing some air."

    def mock_get_llm_client():
        return FakeLLMClient(override_response={"rewritten_text": paraphrase})

    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)

    clara = next(a for a in test_case_data.agents if a.agent_id == "agent_clara")
    deterministic_text = (
        "I was at the fountain from about a quarter to eight until just "
        "before opening. I needed air."
    )

    result = rewrite_interview_answer(
        case=test_case_data,
        agent=clara,
        question_text="Where were you during the murder window?",
        deterministic_text=deterministic_text,
        allowed_facts=["Clara claims she was at the fountain around 07:45."],
        pressure_level=0.2,
    )

    assert result.fallback_used is False
    assert result.rewritten_text == paraphrase


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
    
    assert result.rewritten_text.endswith("I was at the fountain.")
    assert "register" not in result.rewritten_text.lower()
    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"


def test_concept_group_combination_leak_is_blocked(monkeypatch):
    """A rewrite can paraphrase the killer's motive using nothing but the
    solution's own grading vocabulary (case_001's real, unmodified
    solution.motive.concept_groups: till/cash/..., steal/stole/...,
    blackmail/committee/..., mother/care home/...) — no role label, no
    violence term, no long-sentence exact match. Proven live against a
    running server: pointing the LLM settings at an attacker-controlled
    endpoint returning exactly this text made /api/interview/ask hand the
    killer's full motive to the player before a single clue was discovered.
    Every individual word here is <=10 chars, which is why the old
    `len(fact) > 10` gate in _sanitise let it straight through."""

    test_case_data = get_case("case_001")

    leak_text = (
        "Between us, I'd been quietly taking from the till to cover my "
        "mother's care home debts, and he found out. He said if I didn't "
        "own up by this morning he'd take it straight to the committee "
        "himself."
    )

    def mock_get_llm_client():
        return FakeLLMClient(override_response={"rewritten_text": leak_text})

    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)

    killer = next(a for a in test_case_data.agents if a.agent_id == test_case_data.solution.killer_id)

    result = rewrite_interview_answer(
        case=test_case_data,
        agent=killer,
        question_text="What was your relationship with the victim?",
        deterministic_text="He was exacting, but he gave me the manager's job when nobody else would.",
        allowed_facts=[],
        pressure_level=0.3,
    )

    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"
    assert "till" not in result.rewritten_text.lower()
    assert "committee" not in result.rewritten_text.lower()


def test_single_concept_word_in_unrelated_flavour_is_not_blocked(monkeypatch):
    """The flip side of the combination check: one word from one concept
    group, in a context that has nothing to do with the case, must not be
    treated as a leak — 'mother' alone is ordinary conversation, not a
    confession. Regression guard for the false positive the combination
    check itself introduced (case_001's motive concept groups include
    'mother' as a single-word group)."""

    test_case_data = get_case("case_001")

    def mock_get_llm_client():
        return FakeLLMClient(override_response={
            "rewritten_text": "I hated my mother's cooking, if I'm honest."
        })

    monkeypatch.setattr(rewriter_module, "get_llm_client", mock_get_llm_client)
    agent = test_case_data.agents[0]

    result = rewrite_interview_answer(
        case=test_case_data,
        agent=agent,
        question_text="Tell me about your childhood.",
        deterministic_text="I'd rather not get into that.",
        allowed_facts=[],
        pressure_level=0.3,
    )

    assert result.fallback_used is False
    assert result.rewritten_text == "I hated my mother's cooking, if I'm honest."

