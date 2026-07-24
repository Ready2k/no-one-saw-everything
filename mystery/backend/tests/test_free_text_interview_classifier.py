from app.main import case_data, session
from app.question_classifier import classify_question, _refers_to_victim
from app.reference_resolver import resolve_references

def test_alibi_classification(reset_app_state):
    case = case_data()
    sess = session()
    intent = classify_question("where were you at 07:50?", case, sess)
    assert intent is not None
    assert intent.intent == "alibi"

def test_last_seen_classification(reset_app_state):
    case = case_data()
    sess = session()
    intent = classify_question("When did you last see Marcus?", case, sess)
    assert intent is not None
    assert intent.intent == "last_seen_victim"

def test_object_unresolved_before_discovery(reset_app_state):
    case = case_data()
    sess = session()
    sess.discovered_clue_ids = []
    refs = resolve_references("What is the deal with Marcus's loan book?", case, sess)
    assert refs["referenced_object_id"] is None

def test_object_resolved_after_discovery(reset_app_state):
    case = case_data()
    sess = session()
    sess.discovered_clue_ids = {"clue_loan_book"}
    refs = resolve_references("What is the deal with Marcus's loan book?", case, sess)
    assert refs["referenced_object_id"] == "obj_loan_ledger"
    intent = classify_question("What is the deal with Marcus's loan book?", case, sess)
    assert intent is not None
    assert intent.intent == "object"
    assert intent.referenced_object_id == "obj_loan_ledger"

def test_contradiction_requires_reference(reset_app_state):
    case = case_data()
    sess = session()
    sess.discovered_clue_ids = {"clue_ben_sighting"}
    intent = classify_question("Why did Ben say you were near the rear alley?", case, sess)
    assert intent is not None
    assert intent.intent == "contradiction"
    assert intent.referenced_agent_id == "agent_ben"
    assert intent.referenced_location_id == "loc_rear_alley"

def test_motive_classification(reset_app_state):
    case = case_data()
    sess = session()
    intent = classify_question("Why would you want Marcus dead?", case, sess)
    assert intent is not None
    assert intent.intent == "motive"

def test_fallback_unknown(reset_app_state):
    case = case_data()
    sess = session()
    intent = classify_question("What is the meaning of life?", case, sess)
    assert intent is None

def test_argued_with_victim_routes_to_relationship_not_last_seen(reset_app_state):
    # "argued" is a relationship dynamic, not a sighting — routing it to
    # last_seen_victim forces the dialogue rewriter to bridge an unrelated
    # topic, which is how it previously fabricated an incident ("we had a
    # disagreement") that was never in the seeded truth.
    case = case_data()
    sess = session()
    intent = classify_question("When was the last time you argued with the deceased?", case, sess)
    assert intent is not None
    assert intent.intent == "relationship"

def test_confrontational_bluff_routes_to_explicit_challenge_not_small_talk(reset_app_state):
    case = case_data()
    sess = session()
    intent = classify_question(
        "We both know what really happened back there. Why not just tell me?", case, sess
    )
    assert intent is not None
    assert intent.intent == "explicit_challenge"

def test_greeting_does_not_swallow_a_substantive_grief_question(reset_app_state):
    # "Hi X, how are you coping with the loss of Y?" used to classify as
    # pure "greeting" (a bare "hi" acknowledgment) because the greeting
    # check ran before the more substantive "how are you" check, losing the
    # real question entirely.
    case = case_data()
    sess = session()
    victim = next(a for a in case.agents if a.is_victim)
    intent = classify_question(
        f"Hi there, how are you coping with the loss of {victim.full_name.split()[0]}?", case, sess
    )
    assert intent is not None
    assert intent.intent != "greeting"

def test_bare_greeting_alone_still_classifies_as_greeting(reset_app_state):
    case = case_data()
    sess = session()
    intent = classify_question("Hi there.", case, sess)
    assert intent is not None
    assert intent.intent == "greeting"

def test_victim_pronoun_requires_word_boundary(reset_app_state):
    # A plain substring check for "her" matches inside "there", "gathered",
    # "weather" etc. and silently misroutes any question containing one of
    # those words, e.g. "what happened back there".
    victim = next(a for a in case_data().agents if a.is_victim)
    q_norm = "what happened back there this morning"
    assert _refers_to_victim(q_norm, set(q_norm.split()), victim) is False
    q_norm_real = "what happened to her this morning"
    assert _refers_to_victim(q_norm_real, set(q_norm_real.split()), victim) is True
