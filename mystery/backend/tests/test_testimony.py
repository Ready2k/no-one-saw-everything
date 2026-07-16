"""One person's word, used as evidence against another's.

The game is called No One Saw Everything, and until now a claim could only ever be broken by a
physical clue — the player could find the blue coat but could never say to Clara "Elias sat
facing that fountain all morning and never saw you there."

The conflict detector must be CONSERVATIVE. A detector that cries wolf is worse than no detector,
because the player stops believing it: these tests pin down the things that are NOT
contradictions just as hard as the things that are.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.models import Claim
from app.testimony import find_conflict

client = TestClient(app)


def _claim(cid, speaker, text, t=None, loc=None, about=None, presence=True, t_to=None):
    return Claim(
        claim_id=cid,
        speaker_agent_id=speaker,
        claim_text=text,
        time_reference=t,
        time_to=t_to,
        location_reference_id=loc,
        about_agent_id=about,
        asserts_presence=presence,
    )


# ─────────────────────────────────────────────── what IS a contradiction

def test_a_witness_denial_breaks_an_alibi():
    """Clara says she was at the fountain. Elias watched that fountain and says she wasn't."""
    clara = _claim("c", "agent_clara", "I was at the fountain.", "07:45", "loc_fountain", about="agent_clara", t_to="08:00")
    elias = _claim(
        "e", "agent_elias", "She was never at that fountain.", "07:45", "loc_fountain",
        about="agent_clara", presence=False, t_to="08:00",
    )
    conflict = find_conflict(clara, elias)
    assert conflict is not None
    assert conflict.kind == "denial"
    assert conflict.subject_agent_id == "agent_clara"


def test_a_person_can_contradict_themselves():
    """Priya puts herself in the stockroom and, later, in the alley at the same moment."""
    stockroom = _claim("a", "agent_priya", "I was in the stockroom.", "07:00", "loc_bookshop", about="agent_priya", t_to="08:00")
    alley = _claim("b", "agent_priya", "I was in the alley with Ben.", "07:47", "loc_rear_alley", about="agent_priya")
    conflict = find_conflict(stockroom, alley)
    assert conflict is not None
    assert conflict.kind == "self_contradiction"


def test_two_witnesses_can_put_the_same_person_in_two_places():
    a = _claim("a", "agent_clara", "I was at the fountain.", "07:45", "loc_fountain", about="agent_clara", t_to="08:00")
    b = _claim(
        "b", "agent_ben", "I saw Clara in the alley.", "07:48", "loc_rear_alley",
        about="agent_clara",
    )
    assert find_conflict(a, b).kind == "bilocation"


# ─────────────────────────────────────────────── what is NOT a contradiction

def test_walking_between_two_places_is_not_a_contradiction():
    """The bug this pins: Clara in the cafe at 07:40 and the fountain at 07:50 is a WALK.

    At a 15-minute tolerance the detector called this a bilocation. It is not, and telling the
    player it was would have been a lie.
    """
    cafe = _claim("a", "agent_clara", "I last saw Marcus at the cafe.", "07:40", "loc_hobbs_cafe")
    fountain = _claim("b", "agent_clara", "I was at the fountain.", "07:50", "loc_fountain")
    assert find_conflict(cafe, fountain) is None


def test_statements_about_different_people_never_conflict():
    clara = _claim("a", "agent_clara", "I was at the fountain.", "07:50", "loc_fountain")
    owen = _claim("b", "agent_owen", "I was in my yard.", "07:50", "loc_owen_house")
    assert find_conflict(clara, owen) is None


def test_a_denial_of_one_place_agrees_with_presence_elsewhere():
    """'I wasn't in the alley' and 'I was at the fountain' are perfectly compatible."""
    fountain = _claim("a", "agent_clara", "I was at the fountain.", "07:50", "loc_fountain")
    not_alley = _claim(
        "b", "agent_clara", "I was never in the alley.", "07:50", "loc_rear_alley", presence=False
    )
    assert find_conflict(fountain, not_alley) is None


def test_corroboration_is_not_conflict():
    """Nadia putting Isabella at the clinic AGREES with Isabella putting herself there."""
    isabella = _claim("a", "agent_isabella", "I was at the clinic.", "07:50", "loc_clinic")
    nadia = _claim(
        "b", "agent_nadia", "Isabella was with me at the clinic.", "07:50", "loc_clinic",
        about="agent_isabella",
    )
    assert find_conflict(isabella, nadia) is None


def test_a_claim_that_places_nobody_anywhere_conflicts_with_nothing():
    opinion = _claim("a", "agent_elias", "Owen's the one you want, mark my words.")
    alibi = _claim("b", "agent_clara", "I was at the fountain.", "07:50", "loc_fountain")
    assert find_conflict(alibi, opinion) is None


def test_a_claim_never_contradicts_itself():
    c = _claim("a", "agent_clara", "I was at the fountain.", "07:50", "loc_fountain")
    assert find_conflict(c, c) is None


def test_a_witness_is_not_placed_at_the_scene_they_merely_described():
    """The false positive that forced `about_agent_id` to be explicit.

    A witness statement carries the location of the thing OBSERVED, not of the observer. When
    the subject defaulted to the speaker, Elias reporting two arrivals at two different places
    looked like Elias claiming to be in both — and he appeared to contradict himself.
    """
    arrival = _claim(
        "a", "agent_elias", "Isabella arrived at the bookshop at 12:32.", "12:32", "loc_bookshop"
    )
    account = _claim(
        "b", "agent_elias", "Owen paused at the cafe window at 12:25.", "12:25", "loc_hobbs_cafe"
    )
    assert find_conflict(arrival, account) is None


def test_an_alibi_is_a_span_not_an_instant():
    """'I was home all evening' must be breakable by a sighting at ANY point inside it."""
    home = _claim(
        "a", "agent_ruth", "I was home all evening.", "18:00", "loc_ruth_cottage",
        about="agent_ruth", t_to="23:00",
    )
    seen = _claim(
        "b", "agent_elias", "I saw Ruth leaving his front door at half six.", "18:30",
        "loc_marcus_house", about="agent_ruth",
    )
    assert find_conflict(home, seen).kind == "bilocation"


# ─────────────────────────────────────────────── end to end, through the API

def _hear(agent_id, question_type, **kw):
    return client.post(
        "/api/interview/ask", json={"agent_id": agent_id, "question_type": question_type, **kw}
    ).json()


def test_confronting_clara_with_elias_word_lands(monkeypatch):
    client.post("/api/session/reset")

    # Hear Clara's alibi, then hear Elias say he never saw her at that fountain.
    _hear("agent_clara", "alibi")
    _hear("agent_elias", "timeline", time_reference="07:50")

    claims = {c["claim_id"] for c in client.get("/api/claims").json()}
    assert "claim_clara_fountain" in claims
    assert "claim_elias_no_fountain" in claims, "Elias must actually say it before it can be used"

    # Put the old man's word in front of her — with no physical evidence at all.
    r = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": "claim_clara_fountain",
            "evidence_claim_ids": ["claim_elias_no_fountain"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["testimony_conflict"], "the contradiction must be reported back to the player"
    assert body["emotional_shift"] == "rattled"

    # And it must have cost her something.
    board = client.get("/api/board").json()
    clara = next(s for s in board["suspects"] if s["agent"]["agent_id"] == "agent_clara")
    assert clara["pressure"] > 0
    assert any(
        c["claim_id"] == "claim_clara_fountain" and c["player_known_status"] == "disputed"
        for c in clara["claims"]
    )


def test_irrelevant_testimony_is_honestly_rebuffed():
    client.post("/api/session/reset")
    _hear("agent_clara", "alibi")
    _hear("agent_owen", "alibi")

    r = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": "claim_clara_fountain",
            "evidence_claim_ids": ["claim_owen_yard"],
        },
    ).json()
    # Owen being in his yard says nothing about Clara. The game must not pretend it did.
    assert r["testimony_conflict"] is None
    assert r["outcome"] == "deny"
    assert r["pressure_delta"] == 0.0


def test_cannot_quote_a_statement_you_have_not_heard():
    client.post("/api/session/reset")
    _hear("agent_clara", "alibi")
    r = client.post(
        "/api/challenge",
        json={
            "target_agent_id": "agent_clara",
            "challenged_claim_id": "claim_clara_fountain",
            "evidence_claim_ids": ["claim_elias_no_fountain"],
        },
    )
    assert r.status_code == 404
