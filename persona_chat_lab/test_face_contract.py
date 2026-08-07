"""Regression checks for the safe chat-to-face presentation contract."""

from engine import PersonaSession
from server import PORTRAITS


def test_each_persona_has_a_pressure_portrait_for_every_band():
    for persona in ("owen", "owen_twin", "priya"):
        assert set(PORTRAITS[persona]) == {"composed", "guarded", "cornered", "breaking"}


def test_response_exposes_only_authored_emotion_metadata():
    response = PersonaSession("owen").ask("where were you this morning?")
    assert response["emotion"] == "bristling"
    assert response["performance"] == "guarded"
    assert "killer" not in response
