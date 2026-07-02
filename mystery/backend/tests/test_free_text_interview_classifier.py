from app.main import case_data, session
from app.question_classifier import classify_question
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
