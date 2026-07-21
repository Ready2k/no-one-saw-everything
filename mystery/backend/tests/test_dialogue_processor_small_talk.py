"""default_small_talk_line replaces one universal "I don't have much to say
about that." shared by every character in every case with content derived
from fields every agent already has (occupation, first trait, temperament
dials) — never a fixed vocabulary of specific trait words, since traits are
freeform text authored per case.
"""

from app.dialogue_processor import default_small_talk_line
from app.models import Agent


def _agent(**overrides) -> Agent:
    defaults = dict(
        agent_id="agent_test",
        full_name="Test Testerson",
        age=40,
        occupation="Builder",
        traits=["proud"],
    )
    defaults.update(overrides)
    return Agent(**defaults)


def test_occupation_uses_the_agents_real_occupation():
    agent = _agent(occupation="Timber delivery driver")
    assert "Timber delivery driver" in default_small_talk_line(agent, "occupation")


def test_favorite_thing_and_about_me_differ_between_agents():
    a = _agent(occupation="Builder", traits=["proud"])
    b = _agent(occupation="Clinic nurse", traits=["discreet"])
    assert default_small_talk_line(a, "favorite_thing") != default_small_talk_line(b, "favorite_thing")
    assert default_small_talk_line(a, "about_me") != default_small_talk_line(b, "about_me")


def test_general_relationships_reflects_temperament_dials():
    guarded = _agent(conflict_avoidance=0.9)
    chatty = _agent(gossip_tendency=0.9, conflict_avoidance=0.2)
    assert "keep out of" in default_small_talk_line(guarded, "general_relationships")
    assert "hear things" in default_small_talk_line(chatty, "general_relationships")


def test_unhandled_intent_keeps_the_old_generic_default():
    agent = _agent()
    assert default_small_talk_line(agent, "greeting") == "I don't have much to say about that."
