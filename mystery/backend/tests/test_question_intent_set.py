"""A labelled evaluation set for the deterministic free-text question classifier.

~50 natural questions across every intent, against case_001 (victim Marcus Bell;
Elias, Clara, Ben, Owen, Priya, Nadia, Isabella are suspects). The observed
production defect this guards: "How did you and Elias get along lately?" — a
relationship question about a *suspect* — was routed to a LOCATION answer about
"Elias Grant's House", because a person's bare name was allowed to stand in for
a place named after them and the relationship rule only knew a handful of
phrasings. A person is never a place; a question the deterministic classifier
cannot ground must fall to the open-ended path (None / fallback_unknown), never
to a confidently wrong intent.

Expected value None means "the deterministic classifier passes" (the LLM
classifier or the open-ended path takes over) — that is a correct answer for
out-of-scope questions, and a *wrong* answer for anything with a clear intent.
"""

import pytest

from app.main import case_data, session
from app.question_classifier import classify_question

# (question, expected_intent ('' == None), expected_refs subset, clues_to_discover)
CASES = [
    # --- alibi -------------------------------------------------------------
    ("Where were you during the murder window?", "alibi", {}, []),
    ("Where were you at 07:50?", "alibi", {}, []),
    ("Where was you when Marcus died?", "alibi", {}, []),
    ("What's your alibi for that morning?", "alibi", {}, []),
    ("Where were you this morning?", "alibi", {}, []),
    ("Where were you between 7:40 and 8:00?", "alibi", {}, []),
    # --- timeline ----------------------------------------------------------
    ("What were you doing at 07:45?", "timeline", {}, []),
    ("What did you do after opening up?", "timeline", {}, []),
    ("Where did you go after the square?", "timeline", {}, []),
    ("What were you doing when the body was found?", "timeline", {}, []),
    # --- last seen the victim ----------------------------------------------
    ("When did you last see Marcus?", "last_seen_victim", {}, []),
    ("When did you last see him?", "last_seen_victim", {}, []),
    ("When did you see the victim last?", "last_seen_victim", {}, []),
    ("When did you last see the deceased?", "last_seen_victim", {}, []),
    # --- relationship with the victim --------------------------------------
    ("What was your relationship with Marcus?", "relationship", {}, []),
    ("How did you and Marcus get along lately?", "relationship", {"referenced_location_id": None}, []),
    ("How well did you know Marcus?", "relationship", {}, []),
    ("How did you feel about the victim?", "relationship", {}, []),
    ("Were you on good terms with Marcus?", "relationship", {}, []),
    ("What did you think of Marcus?", "relationship", {}, []),
    # --- relationship about ANOTHER villager: open-ended, never a location --
    (
        "How did you and Elias get along lately?",
        "fallback_unknown",
        {"referenced_agent_id": "agent_elias", "referenced_location_id": None},
        [],
    ),
    ("What do you think of Clara?", "fallback_unknown", {"referenced_agent_id": "agent_clara"}, []),
    ("Were you friends with Nadia?", "fallback_unknown", {"referenced_agent_id": "agent_nadia", "referenced_location_id": None}, []),
    ("Do you trust Owen?", "fallback_unknown", {"referenced_agent_id": "agent_owen", "referenced_location_id": None}, []),
    # --- motive -------------------------------------------------------------
    ("Why would you want Marcus dead?", "motive", {}, []),
    ("Did you have any reason to hurt Marcus?", "motive", {}, []),
    ("Were you angry with Marcus?", "motive", {}, []),
    ("Why would you want him dead?", "motive", {}, []),
    # A motive question naming someone OTHER than the victim must not
    # degrade to the victim-motive answer: "Why would you want Isabella
    # dead?" was observed live returning the suspect's relationship-with-
    # Marcus confession, because "motive" degrades to a "relationship"
    # AnswerRule that's hardcoded to the victim with no target check.
    ("Why would you want Isabella dead?", "fallback_unknown", {"referenced_agent_id": "agent_isabella"}, []),
    ("Did you have a reason to hurt Clara?", "fallback_unknown", {"referenced_agent_id": "agent_clara"}, []),
    # --- contradiction ------------------------------------------------------
    (
        "Why did Ben say you were near the rear alley?",
        "contradiction",
        {"referenced_agent_id": "agent_ben", "referenced_location_id": "loc_rear_alley"},
        ["clue_ben_sighting"],
    ),
    ("Ben says you were in the alley that morning.", "contradiction", {"referenced_agent_id": "agent_ben"}, ["clue_ben_sighting"]),
    ("Clara saw you near the storage room.", "contradiction", {"referenced_agent_id": "agent_clara"}, []),
    # --- explicit challenge -------------------------------------------------
    ("I confront you: Ben saw you there.", "explicit_challenge", {"referenced_agent_id": "agent_ben"}, []),
    ("I accuse you of lying — Clara saw you.", "explicit_challenge", {"referenced_agent_id": "agent_clara"}, []),
    # --- evidence / objects -------------------------------------------------
    ("What is the deal with Marcus's loan book?", "object", {"referenced_object_id": "obj_loan_ledger"}, ["clue_loan_book"]),
    # --- location -----------------------------------------------------------
    ("What can you tell me about the rear alley?", "location", {"referenced_location_id": "loc_rear_alley"}, []),
    ("Did you see anything at the fountain?", "location", {"referenced_location_id": "loc_fountain"}, []),
    ("Tell me about Hobbs Cafe.", "location", {"referenced_location_id": "loc_hobbs_cafe"}, []),
    ("What happened in the storage room?", "location", {"referenced_location_id": "loc_cafe_storage"}, []),
    ("Were you in the village square this morning?", "location", {"referenced_location_id": "loc_village_square"}, []),
    # A place NAMED by its full name still resolves, even though it carries a
    # person's name — saying "Elias Grant's house" means the building.
    ("Did you go past Elias Grant's house?", "location", {"referenced_location_id": "loc_elias_house"}, []),
    # --- out of scope: the deterministic classifier must pass, not guess ----
    ("What is the meaning of life?", "", {}, []),
    ("Nice weather today, isn't it?", "", {}, []),
    ("Tell me everything.", "", {}, []),
    ("Who do you think did it?", "", {}, []),
    ("Did anyone dislike Marcus?", "", {}, []),
    # "there" must not read as "her" (substring bug): no victim mention here.
    ("Do you know if there was an argument that morning?", "", {}, []),
]


@pytest.mark.parametrize("question,expected,refs,clues", CASES, ids=[c[0][:48] for c in CASES])
def test_labelled_intent_set(question, expected, refs, clues):
    case = case_data()
    sess = session()
    sess.discovered_clue_ids = set(clues)

    intent = classify_question(question, case, sess)

    if expected == "":
        assert intent is None, f"expected deterministic pass, got {intent.intent}"
        return
    assert intent is not None, f"expected {expected}, classifier passed"
    assert intent.intent == expected, f"expected {expected}, got {intent.intent}"
    for field, want in refs.items():
        got = getattr(intent, field)
        assert got == want, f"{field}: expected {want}, got {got}"


def test_relationship_about_suspect_never_reaches_a_location_answer():
    """End-to-end regression for the observed defect: the free-text endpoint must
    not answer a question about a person with a description of their house."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/api/interview/free-text",
        json={"agent_id": "agent_clara", "question": "How did you and Elias get along lately?"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"]["intent"] != "location"
    answer_text = (body.get("answer") or {}).get("answer_text", "") or (
        body.get("fallback_message") or ""
    )
    assert "House" not in answer_text


def test_motive_about_suspect_never_reaches_victim_motive_answer():
    """End-to-end regression for a defect observed live: "Why would you want
    Isabella dead?" was answered with Owen's relationship-with-Marcus debt
    confession ("I owed him... I couldn't pay"), because the "motive" intent
    degrades to a "relationship" AnswerRule hardcoded to the victim, with no
    check on who the motive question actually named."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/api/interview/free-text",
        json={"agent_id": "agent_owen", "question": "Why would you want Isabella dead?"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"]["intent"] != "motive"
    answer_text = (body.get("answer") or {}).get("answer_text", "") or (
        body.get("fallback_message") or ""
    )
    assert "owed him" not in answer_text.lower()
    assert "couldn't pay" not in answer_text.lower()
