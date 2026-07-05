"""Spec 15 Phase C: offline belief-state batch updates. Strictly additive
flavour — off by default, asynchronous, validated so it can never surface
(or fingerprint) the hidden truth.
"""

from app.case_store import get_case
from app.llm.belief_updater import (
    _validate_belief,
    schedule_belief_updates,
    update_belief_state,
)
from app.llm.client import FakeLLMClient
from app.models import AgentBeliefState
from app.session import reset_session
import app.llm.belief_updater as updater_module


def _agent(case, agent_id):
    return next(a for a in case.agents if a.agent_id == agent_id)


def _non_killer_suspect(case, exclude_id):
    return next(
        a.agent_id
        for a in case.agents
        if not a.is_victim
        and a.agent_id not in (case.solution.killer_id, exclude_id, case.case.victim_id)
    )


def test_suspicion_of_real_killer_is_nullified_not_discarded():
    """No-leak acceptance: a belief update resolving toward the actual
    killer keeps its worry level but loses the target — so neither the
    suspicion nor its conspicuous absence identifies the killer."""
    case = get_case("case_001")
    agent = next(
        a
        for a in case.agents
        if not a.is_victim and a.agent_id != case.solution.killer_id
    )

    raw = AgentBeliefState(
        worry_level=0.9,
        current_suspicion_target=case.solution.killer_id,
        talking_points=[],
    )
    state = _validate_belief(case, agent, raw)
    assert state.current_suspicion_target is None
    assert state.worry_level == 0.9
    # Generic fallback instead of a silent hole where suspicion used to be.
    assert state.talking_points


def test_valid_suspicion_target_is_kept():
    case = get_case("case_001")
    agent = _agent(case, "agent_clara")
    target = _non_killer_suspect(case, agent.agent_id)

    raw = AgentBeliefState(worry_level=0.5, current_suspicion_target=target)
    state = _validate_belief(case, agent, raw)
    assert state.current_suspicion_target == target


def test_invalid_targets_are_dropped():
    case = get_case("case_001")
    agent = _agent(case, "agent_clara")
    for bad in ("agent_clara", case.case.victim_id, "agent_nobody", "Detective"):
        raw = AgentBeliefState(worry_level=0.1, current_suspicion_target=bad)
        assert _validate_belief(case, agent, raw).current_suspicion_target is None


def test_talking_points_are_filtered():
    case = get_case("case_001")
    agent = _agent(case, "agent_clara")
    case.solution.motive.concept_groups = [["stole from the cafe safe"]]
    other_first_name = _agent(case, "agent_ben").full_name.split()[0]

    raw = AgentBeliefState(
        worry_level=0.3,
        talking_points=[
            "I hope this is over soon.",
            "Everyone knows who the killer is by now.",  # role label
            "They must never learn I stole from the cafe safe.",  # forbidden fact
            f"I saw {other_first_name} acting strangely.",  # invented sighting of a named suspect
            '{"schema": "leak"}',  # JSON artifact
        ],
    )
    state = _validate_belief(case, agent, raw)
    assert state.talking_points == ["I hope this is over soon."]


def test_update_belief_state_stores_validated_state(monkeypatch):
    case = get_case("case_001")
    session = reset_session("case_001")
    target = _non_killer_suspect(case, "agent_clara")

    monkeypatch.setattr(
        updater_module,
        "get_llm_client",
        lambda: FakeLLMClient(override_response={
            "worry_level": 0.6,
            "current_suspicion_target": target,
            "talking_points": ["I need to keep my head down."],
        }),
    )

    state = update_belief_state(case, session, "agent_clara", "A challenge just resolved.")
    assert state is not None
    assert session.belief_states["agent_clara"] == state
    assert state.current_suspicion_target == target


def test_update_failure_keeps_previous_state(monkeypatch):
    case = get_case("case_001")
    session = reset_session("case_001")
    previous = AgentBeliefState(worry_level=0.4)
    session.belief_states["agent_clara"] = previous

    monkeypatch.setattr(
        updater_module, "get_llm_client", lambda: FakeLLMClient(fail_count=100)
    )
    result = update_belief_state(case, session, "agent_clara", "trigger")
    assert result is None
    assert session.belief_states["agent_clara"] == previous


def test_victim_never_gets_a_belief_state():
    case = get_case("case_001")
    session = reset_session("case_001")
    assert update_belief_state(case, session, case.case.victim_id, "trigger") is None
    assert case.case.victim_id not in session.belief_states


def test_schedule_is_noop_when_flag_off(monkeypatch):
    """Turning the feature off restores Phase A/B behaviour exactly: no
    thread, no state."""
    monkeypatch.setenv("MYSTERY_LLM_PROVIDER", "fake")
    monkeypatch.setenv("MYSTERY_LLM_DIALOGUE_ENABLED", "true")
    monkeypatch.delenv("MYSTERY_LLM_BELIEFS_ENABLED", raising=False)

    case = get_case("case_001")
    session = reset_session("case_001")
    thread = schedule_belief_updates(case, session, ["agent_clara"], "trigger")
    assert thread is None
    assert session.belief_states == {}


def test_schedule_runs_off_the_request_path(monkeypatch):
    """The update happens on a background thread the caller doesn't wait on
    — the player-facing request path only ever reads existing state."""
    monkeypatch.setenv("MYSTERY_LLM_PROVIDER", "fake")
    monkeypatch.setenv("MYSTERY_LLM_DIALOGUE_ENABLED", "true")
    monkeypatch.setenv("MYSTERY_LLM_BELIEFS_ENABLED", "true")

    case = get_case("case_001")
    session = reset_session("case_001")
    thread = schedule_belief_updates(case, session, ["agent_clara"], "trigger")
    assert thread is not None
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert "agent_clara" in session.belief_states
