"""An investigation must survive the process that created it.

Sessions used to live only in memory, and `/api/cases/activate` called reset_session()
unconditionally — so restarting the backend, or simply opening a different case and coming back,
silently destroyed hours of work. (The case library had to warn "your current progress will be
lost".) Opening a case now RESUMES it; starting over is an explicit choice.

Persistence is switched off under pytest so tests never see each other's saves, so these tests
drive the Session serialisation directly and point the store at a tmp_path.
"""

import json

import pytest

from app import session as session_mod
from app.models import Claim, InterviewMessage, Note
from app.session import Session


@pytest.fixture
def persistent(tmp_path, monkeypatch):
    """Turn persistence on, pointed at a throwaway directory."""
    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path)
    monkeypatch.setattr(session_mod, "_persist_enabled", lambda: True)
    monkeypatch.setattr(session_mod, "_sessions", {})
    return tmp_path


def _worked_case() -> Session:
    s = Session("case_001")
    s.discovered_clue_ids.update({"clue_ben_sighting", "clue_till_weight_found"})
    s.inspected_location_ids.add("loc_cafe_kitchen")
    s.record_claim(
        Claim(
            claim_id="claim_clara_fountain",
            speaker_agent_id="agent_clara",
            claim_text="I was at the fountain.",
            claim_type="alibi",
        )
    )
    s.transcript_for("agent_clara").messages.append(
        InterviewMessage(
            speaker="agent",
            text="I was at the fountain.",
            deterministic_text="I was at the fountain.",
        )
    )
    note_id = s.next_note_id()
    s.notes[note_id] = Note(note_id=note_id, title="Clara is lying", body="Ben saw the coat.")
    s.add_pressure("agent_clara", 0.4)
    s.hint_count = 2
    return s


def test_an_investigation_survives_a_restart(persistent):
    session_mod.save_session(_worked_case())

    # A brand-new process: nothing in memory, only what is on disk.
    session_mod._sessions.clear()
    revived = session_mod.get_session("case_001")

    assert revived.discovered_clue_ids == {"clue_ben_sighting", "clue_till_weight_found"}
    assert revived.inspected_location_ids == {"loc_cafe_kitchen"}
    assert revived.claims["claim_clara_fountain"].claim_text == "I was at the fountain."
    assert len(revived.transcript_for("agent_clara").messages) == 1
    assert [n.title for n in revived.notes.values()] == ["Clara is lying"]
    assert revived.pressure_for("agent_clara") == pytest.approx(0.4)
    assert revived.hint_count == 2


def test_ids_resume_and_do_not_collide_after_reload(persistent):
    """A reloaded session must not mint a note id it already holds."""
    s = _worked_case()  # already issued note_001
    session_mod.save_session(s)
    session_mod._sessions.clear()

    revived = session_mod.get_session("case_001")
    assert revived.next_note_id() == "note_002", "reloaded session reused an existing note id"


def test_reset_discards_the_save(persistent):
    session_mod.save_session(_worked_case())
    assert session_mod.has_saved_session("case_001")

    session_mod.reset_session("case_001")

    assert not session_mod.has_saved_session("case_001")
    assert session_mod.get_session("case_001").discovered_clue_ids == set()


def test_two_investigations_coexist(persistent):
    a = Session("case_001")
    a.discovered_clue_ids.add("clue_ben_sighting")
    b = Session("case_005")
    b.discovered_clue_ids.update({"clue_back_lane", "clue_belt_weapon"})
    session_mod.save_session(a)
    session_mod.save_session(b)
    session_mod._sessions.clear()

    assert len(session_mod.get_session("case_001").discovered_clue_ids) == 1
    assert len(session_mod.get_session("case_005").discovered_clue_ids) == 2

    summary = session_mod.load_session_summary("case_005")
    assert summary["clues_found"] == 2
    assert summary["accused"] is False


def test_a_corrupt_save_does_not_wedge_the_case(persistent):
    """A save from an older schema must start the case fresh, not crash the player out of it."""
    (persistent / "case_001.json").write_text("{ this is not json")

    s = session_mod.get_session("case_001")

    assert s.case_id == "case_001"
    assert s.discovered_clue_ids == set()


def test_save_is_atomic(persistent):
    """Write-then-rename: no half-written investigation is ever left behind."""
    session_mod.save_session(_worked_case())
    assert not list(persistent.glob("*.tmp")), "a temp file was left behind"
    json.loads((persistent / "case_001.json").read_text())  # must be complete, valid JSON
