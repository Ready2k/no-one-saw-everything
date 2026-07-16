"""Phase A presentation layer: portrait_art projection and board pressure."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Agent, PortraitState
from app.projections import project_agent

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_session():
    client.post("/api/session/reset")
    yield


def test_agents_expose_portrait_art_with_null_default():
    agents = client.get("/api/agents").json()
    assert agents, "case must have agents"
    for agent in agents:
        assert "portrait_art" in agent
        assert agent["portrait_art"] is not None  # now all cases have art assets
        assert "calm" in agent["portrait_art"]
        assert agent["portrait"] is not None  # emoji fallback still present


def test_project_agent_round_trips_portrait_art():
    agent = Agent(
        agent_id="a1",
        full_name="Test Agent",
        age=40,
        occupation="tester",
        portrait="🧪",
        portrait_art=PortraitState(calm="art/calm.png", cracking="art/cracking.png"),
    )
    projected = project_agent(agent)
    assert projected["portrait_art"] == {
        "calm": "art/calm.png",
        "defensive": None,
        "cracking": "art/cracking.png",
    }


def test_locations_expose_illustration_field():
    locations = client.get("/api/locations").json()
    assert locations, "case must have locations"
    for loc in locations:
        assert "illustration" in loc
        # Resolved from place_library art (or None for locations without a mapped asset) —
        # never absent, and never anything but a string or null.
        assert loc["illustration"] is None or isinstance(loc["illustration"], str)


def test_accusation_result_names_the_accused():
    living = [a for a in client.get("/api/agents").json() if not a["is_victim"]]
    accused = living[0]
    result = client.post(
        "/api/accuse",
        json={
            "accused_agent_id": accused["agent_id"],
            "motive_answer": "",
            "method_answer": "",
            "opportunity_answer": "",
            "supporting_note_ids": [],
            "supporting_clue_ids": [],
        },
    ).json()
    assert result["accused_agent_id"] == accused["agent_id"]
    assert result["accused_name"] == accused["full_name"]


def test_case_overview_includes_scene_description():
    overview = client.get("/api/case").json()
    assert "scene_description" in overview
    assert isinstance(overview["scene_description"], str)  # empty = client fallback


def test_board_suspects_include_pressure():
    board = client.get("/api/board").json()
    assert board["suspects"], "case must have suspects"
    for suspect in board["suspects"]:
        assert "pressure" in suspect
        assert 0.0 <= suspect["pressure"] <= 1.0
