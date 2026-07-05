from fastapi.testclient import TestClient
from app.main import app, session

client = TestClient(app)

def test_api_alibi(reset_app_state):
    resp = client.post("/api/interview/free-text", json={
        "agent_id": "agent_clara",
        "question": "Where were you around 07:50?"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"]["intent"] == "alibi"
    assert data["answer"] is not None
    assert "deterministic_answer_text" in data["answer"]

def test_api_contradiction_challenge(reset_app_state):
    sess = session()
    from app.models import Claim
    sess.claims["claim_clara_fountain"] = Claim(
        claim_id="claim_clara_fountain",
        speaker_agent_id="agent_clara",
        claim_text="I was at the fountain",
        summary="dummy",
        claim_type="alibi",
        time_reference="07:50",
        truthfulness="mistaken",
        player_known_status="disputed"
    )
    sess.discovered_clue_ids.add("clue_ben_sighting")
    
    client.post("/api/interview/free-text", json={
        "agent_id": "agent_clara",
        "question": "Where were you around 07:50?"
    })
    
    resp = client.post("/api/interview/free-text", json={
        "agent_id": "agent_clara",
        "question": "Why did Ben say you were near the alley?"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"]["intent"] == "contradiction"
    assert data["challenge_suggestion"] is not None
    
def test_api_object_mapped_to_evidence(reset_app_state):
    sess = session()
    sess.discovered_clue_ids.add("clue_loan_book")
    
    resp = client.post("/api/interview/free-text", json={
        "agent_id": "agent_ben",
        "question": "What is the deal with Marcus's loan book?"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"]["intent"] == "object"
    assert data["intent"]["referenced_object_id"] == "obj_loan_ledger"
    assert data["answer"] is not None

def test_api_vague_contradiction_does_not_mutate_state(reset_app_state):
    sess = session()
    from app.models import Claim
    sess.claims["claim_clara_fountain"] = Claim(
        claim_id="claim_clara_fountain",
        speaker_agent_id="agent_clara",
        claim_text="I was at the fountain",
        summary="dummy",
        claim_type="alibi",
        time_reference="07:50",
        truthfulness="mistaken",
        player_known_status="disputed"
    )
    sess.discovered_clue_ids.add("clue_ben_sighting")
    
    initial_pressure = sess.pressure.get("agent_clara", 0)
    initial_claims_len = len(sess.claims)
    initial_notes_len = len(sess.notes)
    
    resp = client.post("/api/interview/free-text", json={
        "agent_id": "agent_clara",
        "question": "Why did Ben say you were near the alley?"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"]["intent"] == "contradiction"
    assert data.get("challenge_suggestion") is not None
    assert data.get("challenge_result") is None
    
    assert sess.pressure.get("agent_clara", 0) == initial_pressure
    assert len(sess.claims) == initial_claims_len
    assert len(sess.notes) == initial_notes_len


def test_api_explicit_challenge_mutates_state(reset_app_state):
    sess = session()
    from app.models import Claim
    sess.claims["claim_clara_fountain"] = Claim(
        claim_id="claim_clara_fountain",
        speaker_agent_id="agent_clara",
        claim_text="I was at the fountain",
        summary="dummy",
        claim_type="alibi",
        time_reference="07:50",
        truthfulness="mistaken",
        player_known_status="disputed"
    )
    sess.discovered_clue_ids.add("clue_ben_sighting")
    
    initial_pressure = sess.pressure.get("agent_clara", 0)
    
    resp = client.post("/api/interview/free-text", json={
        "agent_id": "agent_clara",
        "question": "I challenge you with what Ben saw."
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"]["intent"] == "explicit_challenge"
    assert data.get("challenge_result") is not None
    assert data.get("challenge_suggestion") is None
    
    assert sess.pressure.get("agent_clara", 0) > initial_pressure

def test_free_text_body_examination(reset_app_state, monkeypatch):
    # Monkeypatch the classifier to raise an error if it gets called
    # This proves the free text examination bypasses the LLM
    def mock_classify(*args, **kwargs):
        raise RuntimeError("LLM path should not be invoked for body examination")
    
    monkeypatch.setattr("app.free_text_api.classify_question", mock_classify)
    
    resp = client.post("/api/interview/free-text", json={
        "agent_id": "agent_marcus",
        "question": "search the pockets"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"]["intent"] == "evidence"
    assert data["intent"]["rewritten_structured_question"] == "Examine body"
    assert "You examine" in data["answer"]["answer_text"]

