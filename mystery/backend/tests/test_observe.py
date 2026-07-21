"""Observe: an action the player spends to study a suspect, not a free lie detector.

The contract under test:
  * Observe needs a fresh exchange — a new answer or a new challenge — and each
    exchange affords exactly one read (409 otherwise).
  * The read is player-safe: built from pressure and already-shown tells, and it
    never names truthfulness or guilt.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FORBIDDEN_WORDS = {"lie", "lying", "liar", "false", "guilty", "killer", "murderer"}


@pytest.fixture(autouse=True)
def fresh_session():
    client.post("/api/session/reset")
    yield


def _observe(agent_id="agent_clara"):
    return client.post("/api/interview/observe", json={"agent_id": agent_id})


def _ask_alibi(agent_id="agent_clara"):
    return client.post(
        "/api/interview/ask", json={"agent_id": agent_id, "question_type": "alibi"}
    ).json()


def _assert_player_safe(obs: dict):
    assert obs["text"]
    assert obs["category"] in {"gaze", "voice", "hands", "posture", "timing", "overexplaining"}
    assert obs["intensity"] in {"subtle", "noticeable", "strong"}
    assert "truthfulness" not in obs
    lowered = obs["text"].lower()
    for word in FORBIDDEN_WORDS:
        assert word not in lowered.split(), f"observation leaked the word {word!r}"


def test_observe_requires_an_exchange_first():
    r = _observe()
    assert r.status_code == 409


def test_observe_after_an_answer_returns_a_player_safe_read():
    _ask_alibi()
    r = _observe()
    assert r.status_code == 200
    _assert_player_safe(r.json())


def test_each_exchange_affords_exactly_one_read():
    _ask_alibi()
    assert _observe().status_code == 200
    assert _observe().status_code == 409  # nothing new to watch
    client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_clara", "question_type": "relationship"},
    )
    assert _observe().status_code == 200  # a fresh answer re-arms it


def test_a_challenge_counts_as_a_fresh_exchange():
    alibi = _ask_alibi()
    claim_id = alibi["new_claims"][0]["claim_id"]
    assert _observe().status_code == 200
    client.post("/api/discover_clue", json={"clue_id": "clue_elias_fountain"})
    r = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": claim_id,
            "evidence_clue_ids": ["clue_elias_fountain"],
        },
    )
    assert r.status_code == 200
    obs = _observe()
    assert obs.status_code == 200
    _assert_player_safe(obs.json())


def test_observe_rejects_victim_and_background_people():
    assert _observe("agent_marcus").status_code == 400  # the victim
    assert _observe("agent_rosa").status_code == 400  # background NPC
    assert _observe("agent_nobody").status_code == 404


def test_observing_an_honest_suspect_reads_as_composed_not_as_cleared():
    """An innocent, unpressured suspect must still get a read — ambiguity cuts both
    ways, and 'they seem fine' must never be phrased as an exoneration."""
    _ask_alibi("agent_owen")
    r = _observe("agent_owen")
    assert r.status_code == 200
    obs = r.json()
    _assert_player_safe(obs)
    lowered = obs["text"].lower()
    assert "innocent" not in lowered
    assert "truth" not in lowered


def test_observations_are_listed_per_agent():
    _ask_alibi()
    obs = _observe().json()
    listed = client.get("/api/interview/agent_clara/observations").json()
    assert [o["observation_id"] for o in listed] == [obs["observation_id"]]
    assert client.get("/api/interview/agent_owen/observations").json() == []
