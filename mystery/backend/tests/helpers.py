"""Shared test helpers for driving the player-facing discovery flow.

Inspection no longer auto-reveals clues: /api/inspect returns hidden-clue
hotspots (magnifying-glass search) and each one must be claimed through
/api/discover_clue, exactly as the frontend does.
"""


def inspect_and_discover(client, location_id: str) -> list[str]:
    """Inspect a location and discover every hotspot it exposes.

    Returns the clue ids discovered by this call.
    """
    r = client.post("/api/inspect", json={"location_id": location_id})
    r.raise_for_status()
    discovered = []
    for hotspot in r.json()["hidden_clues"]:
        d = client.post("/api/discover_clue", json={"clue_id": hotspot["clue_id"]})
        d.raise_for_status()
        discovered.append(hotspot["clue_id"])
    return discovered


def examine_body_and_discover(client, agent_id: str) -> list[str]:
    """Examine the victim body and discover every body hotspot it exposes."""
    r = client.get(f"/api/examine_body/{agent_id}")
    r.raise_for_status()
    discovered = []
    for hotspot in r.json()["hidden_clues"]:
        d = client.post("/api/discover_clue", json={"clue_id": hotspot["clue_id"]})
        d.raise_for_status()
        discovered.append(hotspot["clue_id"])
    return discovered
