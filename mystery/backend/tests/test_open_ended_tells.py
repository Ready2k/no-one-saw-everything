"""open_ended_tells gives small talk, unmatched questions, and unevidenced
confrontations a pressure-driven observable tell — paths with no
truthfulness/emotional_shift to react to, which previously never generated
any observable_tells at all.
"""

from app.behavioural_tells import open_ended_tells
from app.models import Agent


def _agent() -> Agent:
    return Agent(agent_id="agent_test", full_name="Test Agent", age=30, occupation="Builder")


def test_low_pressure_yields_no_tell():
    assert open_ended_tells(agent=_agent(), pressure=0.1, seed="s1") == []


def test_elevated_pressure_yields_one_tell():
    tells = open_ended_tells(agent=_agent(), pressure=0.5, seed="s2")
    assert len(tells) == 1
    assert tells[0].source == "interview"
    assert tells[0].agent_id == "agent_test"


def test_guarded_confrontation_can_cross_the_threshold_alone():
    # 0.25 pressure alone is below the 0.38 threshold, but a guarded
    # confrontation (a bluff with no evidence) adds a 0.2 bonus.
    assert open_ended_tells(agent=_agent(), pressure=0.25, seed="s3") == []
    tells = open_ended_tells(agent=_agent(), pressure=0.25, seed="s3", guarded=True)
    assert len(tells) == 1
    assert tells[0].category in {"gaze", "timing", "hands", "overexplaining"}
