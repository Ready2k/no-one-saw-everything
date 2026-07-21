import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_session():
    client.post("/api/session/reset")
    yield


def _assert_player_safe_tell(tell: dict):
    assert tell["cue"]
    assert tell["category"] in {"gaze", "voice", "hands", "posture", "timing", "overexplaining"}
    assert tell["intensity"] in {"subtle", "noticeable", "strong"}
    assert tell["source"] in {"interview", "challenge"}
    text = " ".join(str(v).lower() for v in tell.values())
    assert "truthfulness" not in tell
    assert "false" not in text
    assert "lie" not in text
    assert "lying" not in text


def test_interview_response_includes_player_safe_behavioural_tells():
    result = client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_clara", "question_type": "alibi"},
    ).json()

    assert result["observable_tells"], "Clara's false alibi should produce an observation"
    for tell in result["observable_tells"]:
        _assert_player_safe_tell(tell)

    transcript = client.get("/api/interview/agent_clara").json()
    agent_messages = [m for m in transcript if m["speaker"] == "agent"]
    assert agent_messages[-1]["observable_tells"] == result["observable_tells"]


def test_challenge_response_includes_behavioural_tells_when_pressure_lands():
    alibi = client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_clara", "question_type": "alibi"},
    ).json()
    claim_id = alibi["new_claims"][0]["claim_id"]
    client.post(
        "/api/interview/ask",
        json={"agent_id": "agent_ben", "question_type": "timeline", "time_reference": "07:47"},
    )

    result = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": claim_id,
            "evidence_clue_ids": ["clue_ben_sighting"],
        },
    ).json()

    assert result["pressure_delta"] > 0
    assert result["observable_tells"], "a landed challenge should produce an observation"
    for tell in result["observable_tells"]:
        _assert_player_safe_tell(tell)

    transcript = client.get("/api/interview/agent_clara").json()
    agent_messages = [m for m in transcript if m["speaker"] == "agent"]
    assert agent_messages[-1]["observable_tells"] == result["observable_tells"]
