from app.main import case_data, session
from app.reference_resolver import resolve_references

def test_no_leak_hidden_object(reset_app_state):
    case = case_data()
    sess = session()
    sess.discovered_clue_ids = []
    refs = resolve_references("Did you hit him with the till weight?", case, sess)
    assert refs["referenced_object_id"] is None

def test_no_leak_hidden_event(reset_app_state):
    case = case_data()
    sess = session()
    refs = resolve_references("Where were you during the murder_marcus event?", case, sess)
    assert refs.get("referenced_event_id") is None
