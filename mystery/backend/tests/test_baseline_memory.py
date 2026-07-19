"""Baseline observation memory: the game remembers how someone behaves when calm,
so later reads can say "different from earlier" — never "lying".

The contract under test:
  * A calm baseline is quietly captured from a suspect's first unpressured answer,
    and it is seeded identity only — the killer's baseline is as ordinary as
    anyone's, so the baseline can never leak guilt.
  * The first answer after a suspect enters a new pressure band carries exactly one
    "different from earlier" tell — once per escalation, so it stays news.
  * Observe compares against the baseline every time, and the comparison tracks
    pressure — an innocent under strain deviates too.
"""

import pytest
from fastapi.testclient import TestClient

from app.behavioural_tells import BASELINE_DEVIATION_CUES, baseline_habit
from app.main import app
from app.session import get_session

client = TestClient(app)

FORBIDDEN_WORDS = {"lie", "lying", "liar", "false", "guilty", "killer", "murderer"}


@pytest.fixture(autouse=True)
def fresh_session():
    client.post("/api/session/reset")
    yield


def _ask(agent_id, question_type="alibi", **kw):
    return client.post(
        "/api/interview/ask", json={"agent_id": agent_id, "question_type": question_type, **kw}
    ).json()


def _observe(agent_id="agent_clara"):
    return client.post("/api/interview/observe", json={"agent_id": agent_id})


def _raise_clara_pressure_to_cornered():
    """Clara (case_001's killer): fountain claim + three challenges -> P=0.47,
    two full meter bands above her banked calm baseline."""
    alibi = _ask("agent_clara")
    claim_id = alibi["new_claims"][0]["claim_id"]
    for clue in ("clue_elias_fountain", "clue_rear_door", "clue_ben_sighting", "clue_blue_coat_damp"):
        client.post("/api/discover_clue", json={"clue_id": clue})
    for clue in ("clue_elias_fountain", "clue_rear_door", "clue_ben_sighting"):
        r = client.post(
            "/api/challenge",
            json={
                "target_agent_id": "agent_clara",
                "challenged_claim_id": claim_id,
                "evidence_clue_ids": [clue],
            },
        )
        assert r.status_code == 200
    return claim_id


def _assert_no_forbidden(text: str):
    lowered = text.lower().replace(".", " ").replace(",", " ")
    for word in FORBIDDEN_WORDS:
        assert word not in lowered.split(), f"leaked the word {word!r}: {text}"


# ─────────────────────────────────────────────── capture

def test_first_calm_answer_banks_a_baseline():
    _ask("agent_clara")
    sess = get_session("case_001")
    baseline = sess.baselines.get("agent_clara")
    assert baseline is not None
    assert baseline.captured_at_pressure < 0.35
    assert baseline.habit_category in BASELINE_DEVIATION_CUES
    _assert_no_forbidden(baseline.habit_text)


def test_baseline_habit_is_seeded_identity_not_truth():
    """Same case, same agent -> same habit, killer or not, across resets."""
    _ask("agent_clara")
    first = get_session("case_001").baselines["agent_clara"].habit_text
    client.post("/api/session/reset")
    _ask("agent_clara")
    assert get_session("case_001").baselines["agent_clara"].habit_text == first
    # Every suspect gets one the same way; nothing distinguishes the killer's.
    _ask("agent_ben")
    assert get_session("case_001").baselines["agent_ben"].habit_category in BASELINE_DEVIATION_CUES


# ─────────────────────────────────────────────── "different from earlier" tells

def test_first_answer_after_entering_a_band_carries_the_comparison_once():
    _raise_clara_pressure_to_cornered()  # P=0.47, band 2, banked at band 0
    sess = get_session("case_001")
    habit_category = sess.baselines["agent_clara"].habit_category
    expected_cue = BASELINE_DEVIATION_CUES[habit_category]

    first = _ask("agent_clara", "relationship")
    cues = [t["cue"] for t in first["observable_tells"]]
    assert expected_cue in cues, "the escalation's first answer should carry the comparison"
    _assert_no_forbidden(" ".join(cues))

    again = _ask("agent_clara", "last_seen_victim")
    assert expected_cue not in [t["cue"] for t in again["observable_tells"]], (
        "the comparison is news once per band, not a recurring stinger"
    )


def test_comparison_lands_even_on_a_flat_answer():
    """The deviation tell must not depend on the answer being dramatic: asking a
    cornered suspect something mundane still shows the changed manner."""
    _raise_clara_pressure_to_cornered()
    resp = _ask("agent_clara", "location", topic_location_id="loc_bakery")
    sess = get_session("case_001")
    expected_cue = BASELINE_DEVIATION_CUES[sess.baselines["agent_clara"].habit_category]
    assert expected_cue in [t["cue"] for t in resp["observable_tells"]]


def test_unpressured_suspect_never_gets_a_comparison_tell():
    _ask("agent_ben")
    resp = _ask("agent_ben", "relationship")
    cues = [t["cue"] for t in resp["observable_tells"]]
    assert not (set(cues) & set(BASELINE_DEVIATION_CUES.values()))


# ─────────────────────────────────────────────── observe comparison

def test_first_calm_observe_notes_the_manner():
    _ask("agent_ben")
    r = _observe("agent_ben")
    assert r.status_code == 200
    obs = r.json()
    assert obs["baseline_state"] == "noted"
    sess = get_session("case_001")
    assert sess.baselines["agent_ben"].habit_text in obs["text"]
    _assert_no_forbidden(obs["text"])


def test_observe_under_pressure_reads_the_change():
    _raise_clara_pressure_to_cornered()
    r = _observe("agent_clara")
    assert r.status_code == 200
    obs = r.json()
    assert obs["baseline_state"] == "broken"  # rattled (band 2) vs banked band 0
    _assert_no_forbidden(obs["text"])


def test_calm_repeat_observe_reads_consistent():
    _ask("agent_ben")
    assert _observe("agent_ben").json()["baseline_state"] == "noted"
    _ask("agent_ben", "relationship")
    assert _observe("agent_ben").json()["baseline_state"] == "consistent"


# ─────────────────────────────────────────────── persistence

def test_baseline_memory_survives_a_session_roundtrip():
    _raise_clara_pressure_to_cornered()
    _ask("agent_clara", "relationship")  # consumes the band-3 comparison
    sess = get_session("case_001")
    restored = sess.from_dict(sess.to_dict())
    assert restored.baselines["agent_clara"].habit_text == sess.baselines["agent_clara"].habit_text
    assert restored.baseline_shift_noted == sess.baseline_shift_noted
