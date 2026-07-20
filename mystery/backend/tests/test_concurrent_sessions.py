"""Load sanity: 20 players interrogating the village at once, nobody sharing a notebook.

Extends test_isolation.py to the per-player session layer: concurrent requests
under distinct X-Session-Id tokens must never bleed notes, transcripts, pressure
or suspicion into each other's investigations.
"""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app

N_PLAYERS = 20


def _play(player_index: int) -> dict:
    token = f"loadtest-player-{player_index:02d}"
    headers = {"X-Session-Id": token}
    client = TestClient(app)

    client.post(
        "/api/notes",
        json={"title": f"note-of-{token}", "body": f"private theory {player_index}"},
        headers=headers,
    )
    # Players ask a different number of questions so equal-looking state can't pass.
    asks = 1 + (player_index % 3)
    for _ in range(asks):
        r = client.post(
            "/api/interview/ask",
            json={"agent_id": "agent_clara", "question_type": "alibi"},
            headers=headers,
        )
        assert r.status_code == 200
    client.post(
        "/api/suspicion",
        json={"agent_id": "agent_clara", "level": "suspect" if player_index % 2 else "cleared"},
        headers=headers,
    )
    return {"token": token, "headers": headers, "asks": asks, "client": client}


def test_twenty_concurrent_sessions_do_not_cross_contaminate():
    with ThreadPoolExecutor(max_workers=N_PLAYERS) as pool:
        players = list(pool.map(_play, range(N_PLAYERS)))

    for i, p in enumerate(players):
        notes = p["client"].get("/api/notes", headers=p["headers"]).json()
        assert [n["title"] for n in notes] == [f"note-of-{p['token']}"], (
            f"{p['token']} sees foreign notes"
        )

        transcript = p["client"].get("/api/interview/agent_clara", headers=p["headers"]).json()
        # Each ask records a player line and an agent line.
        assert len(transcript) == p["asks"] * 2, (
            f"{p['token']} transcript has {len(transcript)} messages, expected {p['asks'] * 2}"
        )

        board = p["client"].get("/api/board", headers=p["headers"]).json()
        clara = next(s for s in board["suspects"] if s["agent"]["agent_id"] == "agent_clara")
        expected_level = "suspect" if i % 2 else "cleared"
        assert clara["suspicion"] == expected_level, f"{p['token']} suspicion bled"


def test_concurrent_accusations_keep_the_reveal_gate_per_player():
    def accuse(i: int):
        headers = {"X-Session-Id": f"loadtest-accuser-{i:02d}"}
        client = TestClient(app)
        if i % 2 == 0:
            r = client.post(
                "/api/accuse", json={"accused_agent_id": "agent_clara"}, headers=headers
            )
            assert r.status_code == 200
        return client.get("/api/reveal", headers=headers).status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(accuse, range(10)))

    # Accusers see the reveal; everyone else is still sealed out.
    assert results == [200, 403] * 5
