"""Tests that the API never leaks hidden truth before accusation."""

from fastapi.testclient import TestClient

from app.main import app
from app.case_store import load_case_from_disk

client = TestClient(app)


def test_case_metadata_does_not_leak_killer():
    resp = client.get("/api/case")
    assert resp.status_code == 200
    data = resp.json()
    
    # We should see the victim
    assert data["victim"]["full_name"] == "Marcus Bell"
    
    # But the killer should NOT be mentioned in the top-level case data
    assert "killer_id" not in data
    assert "killer" not in data


def test_events_do_not_leak_murder():
    resp = client.get("/api/events")
    assert resp.status_code == 200
    events = resp.json()
    
    # Ensure no hidden events like the murder itself are leaked
    for e in events:
        assert e["visibility"] != "hidden"
        # Since 'murder' is a hidden event type in our data
        assert e["event_type"] != "murder"


def test_agents_do_not_leak_hidden_roles():
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    agents = resp.json()
    
    # Check that roles like "killer" or "red_herring" are not in the response
    for a in agents:
        assert "killer" not in str(a).lower()
        # They should just be agents with names, occupations, etc.


def test_clues_only_returns_discovered():
    # Fresh session
    client.post("/api/session/reset")
    
    resp = client.get("/api/clues")
    assert resp.status_code == 200
    clues = resp.json()
    
    # At the start of the game, no clues should be discovered except maybe initials
    # In case_001, there might be 0 discovered clues at reset
    assert len(clues) == 0


def test_reveal_blocked_before_accusation():
    resp = client.get("/api/reveal")
    assert resp.status_code == 403
    assert "sealed" in resp.json()["detail"]
