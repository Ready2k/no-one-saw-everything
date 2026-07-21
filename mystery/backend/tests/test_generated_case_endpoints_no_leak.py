"""The generated-case library endpoints must never serve or destroy case truth.

GET /api/generated_cases/{id} used to return the entire raw CaseData — solution,
killer, lie flags and all — and DELETE accepted any case id, including the shipped
hand-authored cases and path-traversal segments headed for shutil.rmtree.
"""

import json

import pytest
from fastapi.testclient import TestClient

import app.case_store as cs
from app.main import app

client = TestClient(app)


@pytest.fixture
def gen_case_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "DATA_DIR", tmp_path)
    d = tmp_path / "gen_test_1"
    d.mkdir()
    (d / "case.json").write_text(
        json.dumps(
            {
                "case_id": "gen_test_1",
                "title": "The Test Case",
                "case_type": "blackmail",
                "difficulty": "standard",
                "killer_id": "agent_sneaky",
                "motive_summary": "SECRET-MOTIVE",
            }
        )
    )
    (d / "metadata.json").write_text(json.dumps({"mode": "deterministic", "seed": 1}))
    (d / "solution.json").write_text(json.dumps({"killer_id": "agent_sneaky"}))
    for name in ["clues.json", "agents.json", "locations.json"]:
        (d / name).write_text("{}")
    return d


def test_single_generated_case_returns_library_metadata_not_the_bundle(gen_case_dir):
    r = client.get("/api/generated_cases/gen_test_1")
    assert r.status_code == 200
    body = r.json()
    assert body["case"]["case_id"] == "gen_test_1"
    assert body["title"] == "The Test Case"

    # Nothing truth-shaped may appear anywhere in the payload.
    text = json.dumps(body)
    for banned in ("killer", "solution", "agent_sneaky", "SECRET-MOTIVE", "memories", "events"):
        assert banned not in text, f"leaked {banned!r} in generated-case metadata"


def test_unknown_and_unsafe_case_ids_404(gen_case_dir):
    assert client.get("/api/generated_cases/gen_nope").status_code == 404
    assert client.get("/api/generated_cases/.hidden").status_code == 404


def test_hand_authored_cases_cannot_be_deleted():
    r = client.delete("/api/generated_cases/case_001")
    assert r.status_code == 400
    assert "generated" in r.json()["detail"].lower()


def test_delete_refuses_unsafe_ids_before_touching_disk():
    # Reference cs.* at call time: another test module reloads app.case_store,
    # and a snapshot import would raise/catch mismatched exception classes.
    with pytest.raises(cs.CaseDeleteError):
        cs.delete_case_from_disk("..")
    with pytest.raises(cs.CaseDeleteError):
        cs.delete_case_from_disk("gen_ok/../../case_001")
    with pytest.raises(cs.CaseDeleteError):
        cs.delete_case_from_disk("case_001")


def test_case_id_safety_rules():
    assert cs.is_safe_case_id("case_001")
    assert cs.is_safe_case_id("gen_blackmail_42_1700000000")
    assert not cs.is_safe_case_id("..")
    assert not cs.is_safe_case_id("../x")
    assert not cs.is_safe_case_id("a/b")
    assert not cs.is_safe_case_id("")
    assert not cs.is_safe_case_id(".hidden")
