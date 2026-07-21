"""Two browsers are two detectives.

Sessions are scoped by an opaque X-Session-Id token: player A's notebook, clues,
active case and accusation must be invisible to player B — the reveal gate is only
sound if one player's accusation cannot unseal the truth for another. Tokenless
clients (curl, the tests, the MVP frontend) share the "local" player, so nothing
about the original single-player flow changes shape.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app import session as session_mod
from app.main import app
from app.session import Session, SessionLoadError

client = TestClient(app)

A = {"X-Session-Id": "playerA-test-0001"}
B = {"X-Session-Id": "playerB-test-0002"}


# ---------------------------------------------------------------------------
# Isolation over the API
# ---------------------------------------------------------------------------

def test_notes_and_clues_do_not_cross_between_tokens():
    r = client.post(
        "/api/notes", json={"title": "A's hunch", "body": "Clara is lying"}, headers=A
    )
    assert r.status_code == 200
    r = client.post("/api/discover_clue", json={"clue_id": "clue_ben_sighting"}, headers=A)
    assert r.status_code == 200

    assert client.get("/api/notes", headers=B).json() == []
    assert client.get("/api/status", headers=B).json()["discovered_clue_count"] == 0

    assert len(client.get("/api/notes", headers=A).json()) == 1
    assert client.get("/api/status", headers=A).json()["discovered_clue_count"] == 1


def test_tokenless_requests_share_the_local_player_and_stay_isolated_from_tokens():
    client.post("/api/notes", json={"title": "local note", "body": "x"})
    assert len(client.get("/api/notes").json()) == 1
    assert client.get("/api/notes", headers=A).json() == []


def test_malformed_token_collapses_to_local_not_to_a_new_player():
    evil = {"X-Session-Id": "../../etc/passwd"}
    client.post("/api/notes", json={"title": "n", "body": "b"}, headers=evil)
    # The malformed header shares the tokenless player's notebook.
    assert len(client.get("/api/notes").json()) == 1


def test_one_players_accusation_does_not_unseal_truth_for_another():
    r = client.post(
        "/api/accuse",
        json={"accused_agent_id": "agent_clara"},
        headers=A,
    )
    assert r.status_code == 200
    assert client.get("/api/reveal", headers=A).status_code == 200

    # B has not accused: the truth stays sealed for them.
    assert client.get("/api/reveal", headers=B).status_code == 403
    assert client.get("/api/map/replay?mode=truth", headers=B).status_code == 403


def test_active_case_is_per_player():
    r = client.post(
        "/api/cases/generate",
        json={"case_type": "blackmail", "difficulty": "standard", "seed": 777, "mode": "deterministic", "activate": True},
        headers=A,
    )
    assert r.status_code == 200
    gen_id = r.json()["case_id"]
    assert r.json()["active_session_id"] == gen_id

    # A now plays the generated case; B and tokenless clients still play case_001.
    assert client.get("/api/case", headers=A).json()["case_id"] == gen_id
    assert client.get("/api/case", headers=B).json()["case_id"] == "case_001"
    assert client.get("/api/case").json()["case_id"] == "case_001"


# ---------------------------------------------------------------------------
# Investigation list / delete
# ---------------------------------------------------------------------------

def test_list_and_delete_investigations():
    client.post("/api/notes", json={"title": "n", "body": "b"}, headers=A)

    listed = client.get("/api/session/investigations", headers=A).json()
    assert listed["active_case_id"] == "case_001"
    assert [i["case_id"] for i in listed["investigations"]] == ["case_001"]
    assert listed["investigations"][0]["notes"] == 1

    assert client.get("/api/session/investigations", headers=B).json()["investigations"] == []

    assert client.delete("/api/session/investigations/case_001", headers=A).status_code == 200
    assert client.get("/api/session/investigations", headers=A).json()["investigations"] == []
    # Deleting what does not exist is a 404, not a silent success.
    assert client.delete("/api/session/investigations/case_001", headers=A).status_code == 404


# ---------------------------------------------------------------------------
# Save versioning & recovery (store level)
# ---------------------------------------------------------------------------

@pytest.fixture
def persistent(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path)
    monkeypatch.setattr(session_mod, "_persist_enabled", lambda: True)
    monkeypatch.setattr(session_mod, "_sessions", {})
    monkeypatch.setattr(session_mod, "_LEGACY_MIGRATED", False)
    return tmp_path


def test_future_schema_save_refuses_with_a_clear_message(persistent):
    save_dir = persistent / "local"
    save_dir.mkdir()
    (save_dir / "case_001.json").write_text(
        json.dumps({"schema_version": 99, "case_id": "case_001"})
    )
    with pytest.raises(SessionLoadError) as exc:
        session_mod.get_session("case_001")
    assert "newer version" in str(exc.value)
    # Nothing was deleted or quarantined — a newer server can still read it.
    assert (save_dir / "case_001.json").exists()


def test_session_load_error_is_a_409_not_a_500(monkeypatch):
    from app import main as main_mod

    def boom(*args, **kwargs):
        raise SessionLoadError("This saved investigation was written by a newer version.")

    monkeypatch.setattr(main_mod, "get_session", boom)
    r = client.get("/api/status")
    assert r.status_code == 409
    assert "newer version" in r.json()["detail"]


def test_corrupt_save_is_quarantined_and_case_starts_fresh(persistent):
    save_dir = persistent / "local"
    save_dir.mkdir()
    (save_dir / "case_001.json").write_text("{ not json")

    s = session_mod.get_session("case_001")
    assert s.discovered_clue_ids == set()
    assert s.recovered_from_corrupt_save is True
    # The unreadable file was set aside, not destroyed.
    assert not (save_dir / "case_001.json").exists()
    assert list(save_dir.glob("case_001.json.corrupt-*"))


def test_unrecognised_fields_quarantine_rather_than_500(persistent):
    save_dir = persistent / "local"
    save_dir.mkdir()
    # Valid JSON, declared v2, but a field no schema we know can parse.
    (save_dir / "case_001.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "case_id": "case_001",
                "claims": {"c1": {"utter": "garbage"}},
            }
        )
    )
    s = session_mod.get_session("case_001")
    assert s.recovered_from_corrupt_save is True
    assert list(save_dir.glob("case_001.json.corrupt-*"))


# ---------------------------------------------------------------------------
# Legacy layout migration & adoption
# ---------------------------------------------------------------------------

def _save_dict(case_id: str) -> dict:
    s = Session(case_id)
    s.discovered_clue_ids.add("clue_ben_sighting")
    return s.to_dict()


def test_mvp_flat_layout_migrates_into_local(persistent):
    # The MVP wrote data/sessions/<case_id>.json with no player scoping.
    legacy = _save_dict("case_001")
    legacy.pop("schema_version")  # v1 saves carried no version
    legacy.pop("player_id")
    (persistent / "case_001.json").write_text(json.dumps(legacy))

    s = session_mod.get_session("case_001")

    assert s.discovered_clue_ids == {"clue_ben_sighting"}
    assert not (persistent / "case_001.json").exists()
    assert (persistent / "local" / "case_001.json").exists()


def test_first_token_adopts_the_pre_token_saves(persistent):
    local_dir = persistent / "local"
    local_dir.mkdir()
    (local_dir / "case_001.json").write_text(json.dumps(_save_dict("case_001")))

    # Before tokens existed, this browser WAS the local player: its first
    # tokened appearance inherits those investigations.
    s = session_mod.get_session("case_001", "firstBrowserToken1")
    assert s.discovered_clue_ids == {"clue_ben_sighting"}
    assert (persistent / "firstBrowserToken1" / "case_001.json").exists()

    # A second new token starts empty — adoption happens exactly once.
    s2 = session_mod.get_session("case_001", "secondBrowserToken")
    assert s2.discovered_clue_ids == set()
