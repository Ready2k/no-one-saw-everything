"""Telemetry used to live only inside the session object: a reset deleted it,
and a crash before the next autosave lost it outright. The durable log is a
separate append-only file per (player, case) that neither reset_session nor a
restart ever truncates.
"""

import pytest

from app import telemetry as telemetry_mod
from app.models import Feedback
from app.session import Session
from app.telemetry import log_telemetry_event, read_durable_log


@pytest.fixture
def persistent(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry_mod, "TELEMETRY_DIR", tmp_path)
    monkeypatch.setattr(telemetry_mod, "_persist_enabled", lambda: True)
    return tmp_path


def test_events_are_appended_durably(persistent):
    s = Session("case_001", "playerA")
    log_telemetry_event(s, "clue_discovered", {"clue_id": "clue_a"})
    log_telemetry_event(s, "clue_discovered", {"clue_id": "clue_b"})

    events = read_durable_log("playerA", "case_001")
    assert [e["data"]["clue_id"] for e in events] == ["clue_a", "clue_b"]
    # The in-memory copy still gets everything too — nothing regresses there.
    assert len(s.event_log) == 2


def test_durable_log_survives_a_reset(persistent):
    s = Session("case_001", "playerA")
    log_telemetry_event(s, "accusation_submitted", {"score": 40})

    # A reset makes a brand-new Session object with an empty in-memory log —
    # exactly what reset_session() does.
    fresh = Session("case_001", "playerA")
    assert fresh.event_log == []
    assert len(read_durable_log("playerA", "case_001")) == 1


def test_durable_log_is_scoped_per_player_and_case(persistent):
    a = Session("case_001", "playerA")
    b = Session("case_001", "playerB")
    c = Session("case_002", "playerA")
    log_telemetry_event(a, "note_created")
    log_telemetry_event(b, "note_created")
    log_telemetry_event(b, "note_created")
    log_telemetry_event(c, "note_created")

    assert len(read_durable_log("playerA", "case_001")) == 1
    assert len(read_durable_log("playerB", "case_001")) == 2
    assert len(read_durable_log("playerA", "case_002")) == 1
    assert read_durable_log("playerB", "case_002") == []


def test_a_corrupt_line_does_not_break_the_rest_of_the_log(persistent):
    s = Session("case_001", "playerA")
    log_telemetry_event(s, "note_created")
    log_telemetry_event(s, "note_created")

    path = telemetry_mod._durable_log_path("playerA", "case_001")
    with path.open("a") as f:
        f.write("{ not json\n")

    events = read_durable_log("playerA", "case_001")
    assert len(events) == 2


def test_dev_telemetry_disabled_writes_nothing(persistent, monkeypatch):
    monkeypatch.setattr(telemetry_mod, "MYSTERY_DEV_TELEMETRY_ENABLED", False)
    s = Session("case_001", "playerA")
    log_telemetry_event(s, "note_created")
    assert s.event_log == []
    assert read_durable_log("playerA", "case_001") == []


def test_reading_a_log_that_was_never_written_is_empty(persistent):
    assert read_durable_log("nobody", "case_999") == []
