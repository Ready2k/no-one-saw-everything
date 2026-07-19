"""Mutable player-session state.

One in-memory session per case for the MVP. Everything the player has
discovered, noted, or been told lives here; the locked case truth never
changes.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from .models import (
    AccusationResult,
    AgentBeliefState,
    ChallengeRecord,
    Claim,
    InterviewTranscript,
    Note,
    ObservationRead,
    SuspicionLevel,
    MarkerType,
    Feedback,
)

logger = logging.getLogger(__name__)


class Session:
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.discovered_clue_ids: set[str] = set()
        self.revealed_memory_ids: set[str] = set()
        self.pinned_event_ids: set[str] = set()
        self.inspected_location_ids: set[str] = set()
        self.claims: dict[str, Claim] = {}
        self.transcripts: dict[str, InterviewTranscript] = {}
        self.notes: dict[str, Note] = {}
        self.suspicion: dict[str, SuspicionLevel] = {}
        self.pressure: dict[str, float] = {}  # agent_id -> cumulative pressure
        # agent_id -> private state of mind, written only by the offline
        # belief updater (spec 15 Phase C); read only as prompt flavour.
        self.belief_states: dict[str, AgentBeliefState] = {}
        self.challenges: dict[str, ChallengeRecord] = {}
        # (claim_id, frozenset(evidence_ids)) -> challenge_id, for de-duplication
        self.challenge_index: dict[tuple[str, frozenset[str]], str] = {}
        self.accusation: Optional[AccusationResult] = None
        self.case_board_markers: dict[str, list[MarkerType]] = {}
        self.tutorial_enabled: bool = True
        self.tutorial_step: Optional[int] = 0
        self.event_log: list[dict] = []
        # (claim_id, clue_id) pairs already logged as challenge_suggested, so
        # polling the suggestions endpoint doesn't flood the telemetry log.
        self.logged_suggestion_keys: set[tuple[str, str]] = set()
        # How many times the player asked the game to show them a contradiction outright,
        # rather than spotting it themselves. Surfaced back to the player, not hidden.
        self.hint_count: int = 0
        self.feedback: Optional[Feedback] = None
        # Observe is an action you spend on a person answering: one read per fresh
        # exchange. agent_id -> [message_count, challenge_count] at the last observe.
        self.observations: dict[str, list[ObservationRead]] = {}
        self.observed_progress: dict[str, list[int]] = {}
        self._notes_issued = 0
        self._challenges_issued = 0
        self._observations_issued = 0

    def next_note_id(self) -> str:
        self._notes_issued += 1
        return f"note_{self._notes_issued:03d}"

    def next_observation_id(self) -> str:
        self._observations_issued += 1
        return f"obs_{self._observations_issued:03d}"

    def next_challenge_id(self) -> str:
        self._challenges_issued += 1
        return f"challenge_{self._challenges_issued:03d}"

    # ---------------------------------------------------------------- persistence
    # An investigation is hours of work. It used to live only in this process: restart the
    # backend and every clue, claim, note and transcript was gone. The case truth is immutable
    # and stays on disk in data/<case_id>/; this is the mutable half, saved beside it.

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "discovered_clue_ids": sorted(self.discovered_clue_ids),
            "revealed_memory_ids": sorted(self.revealed_memory_ids),
            "pinned_event_ids": sorted(self.pinned_event_ids),
            "inspected_location_ids": sorted(self.inspected_location_ids),
            "claims": {k: v.model_dump() for k, v in self.claims.items()},
            "transcripts": {k: v.model_dump() for k, v in self.transcripts.items()},
            "notes": {k: v.model_dump() for k, v in self.notes.items()},
            "suspicion": dict(self.suspicion),
            "pressure": dict(self.pressure),
            "belief_states": {k: v.model_dump() for k, v in self.belief_states.items()},
            "challenges": {k: v.model_dump() for k, v in self.challenges.items()},
            # tuple keys aren't JSON-representable; rebuilt on load from the challenge records.
            "accusation": self.accusation.model_dump() if self.accusation else None,
            "case_board_markers": {k: list(v) for k, v in self.case_board_markers.items()},
            "tutorial_enabled": self.tutorial_enabled,
            "tutorial_step": self.tutorial_step,
            "event_log": self.event_log,
            "logged_suggestion_keys": [list(k) for k in self.logged_suggestion_keys],
            "hint_count": self.hint_count,
            "feedback": self.feedback.model_dump() if self.feedback else None,
            "observations": {
                k: [o.model_dump() for o in v] for k, v in self.observations.items()
            },
            "observed_progress": {k: list(v) for k, v in self.observed_progress.items()},
            "notes_issued": self._notes_issued,
            "challenges_issued": self._challenges_issued,
            "observations_issued": self._observations_issued,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        s = cls(data["case_id"])
        s.discovered_clue_ids = set(data.get("discovered_clue_ids", []))
        s.revealed_memory_ids = set(data.get("revealed_memory_ids", []))
        s.pinned_event_ids = set(data.get("pinned_event_ids", []))
        s.inspected_location_ids = set(data.get("inspected_location_ids", []))
        s.claims = {k: Claim(**v) for k, v in data.get("claims", {}).items()}
        s.transcripts = {
            k: InterviewTranscript(**v) for k, v in data.get("transcripts", {}).items()
        }
        s.notes = {k: Note(**v) for k, v in data.get("notes", {}).items()}
        s.suspicion = data.get("suspicion", {})
        s.pressure = data.get("pressure", {})
        s.belief_states = {
            k: AgentBeliefState(**v) for k, v in data.get("belief_states", {}).items()
        }
        s.challenges = {
            k: ChallengeRecord(**v) for k, v in data.get("challenges", {}).items()
        }
        # Rebuild the de-duplication index from the records themselves, so it can never drift
        # out of step with them.
        s.challenge_index = {
            (rec.challenged_claim_id, frozenset(rec.evidence_clue_ids)): cid
            for cid, rec in s.challenges.items()
        }
        if data.get("accusation"):
            s.accusation = AccusationResult(**data["accusation"])
        s.case_board_markers = data.get("case_board_markers", {})
        s.tutorial_enabled = data.get("tutorial_enabled", True)
        s.tutorial_step = data.get("tutorial_step", 0)
        s.event_log = data.get("event_log", [])
        s.logged_suggestion_keys = {tuple(k) for k in data.get("logged_suggestion_keys", [])}
        s.hint_count = data.get("hint_count", 0)
        if data.get("feedback"):
            s.feedback = Feedback(**data["feedback"])
        s.observations = {
            k: [ObservationRead(**o) for o in v]
            for k, v in data.get("observations", {}).items()
        }
        s.observed_progress = {k: list(v) for k, v in data.get("observed_progress", {}).items()}
        # Resume the id sequences where they left off, so a reloaded session cannot mint an id
        # that collides with a note or challenge it already holds.
        s._notes_issued = data.get("notes_issued", len(s.notes))
        s._challenges_issued = data.get("challenges_issued", len(s.challenges))
        s._observations_issued = data.get(
            "observations_issued", sum(len(v) for v in s.observations.values())
        )
        return s

    def pressure_for(self, agent_id: str) -> float:
        return self.pressure.get(agent_id, 0.0)

    def add_pressure(self, agent_id: str, delta: float) -> None:
        self.pressure[agent_id] = max(0.0, min(1.0, self.pressure_for(agent_id) + delta))

    def transcript_for(self, agent_id: str) -> InterviewTranscript:
        if agent_id not in self.transcripts:
            self.transcripts[agent_id] = InterviewTranscript(agent_id=agent_id)
        return self.transcripts[agent_id]

    def record_claim(self, claim: Claim) -> None:
        existing = self.claims.get(claim.claim_id)
        if existing is None:
            self.claims[claim.claim_id] = claim


_sessions: dict[str, Session] = {}

# Saved investigations live beside the case data. Disabled entirely under pytest (and by
# MYSTERY_SESSION_PERSIST=0) so tests never see each other's saves — test_isolation.py exists
# precisely because leaking state between cases is the bug class this file attracts.
SESSIONS_DIR = Path(__file__).parent / "data" / "sessions"


def _persist_enabled() -> bool:
    if os.environ.get("MYSTERY_SESSION_PERSIST") == "0":
        return False
    return "PYTEST_CURRENT_TEST" not in os.environ


def _session_path(case_id: str) -> Path:
    # case_ids are generated internally (case_001, gen_<type>_<seed>_<ts>), but this path is
    # built from one, so refuse anything that could climb out of the sessions directory.
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", case_id)
    return SESSIONS_DIR / f"{safe}.json"


def save_session(session: Session) -> None:
    if not _persist_enabled():
        return
    try:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        path = _session_path(session.case_id)
        # Write-then-rename: a crash mid-write must not leave a half-written investigation.
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(session.to_dict(), indent=2, ensure_ascii=False))
        tmp.replace(path)
    except Exception:
        # Losing a save is bad; taking the player's game down to report it is worse.
        logger.exception("Failed to save session for %s", session.case_id)


def _load_session(case_id: str) -> Optional[Session]:
    if not _persist_enabled():
        return None
    path = _session_path(case_id)
    if not path.exists():
        return None
    try:
        return Session.from_dict(json.loads(path.read_text()))
    except Exception:
        # A save written by an older schema is not worth crashing over — start the case fresh
        # rather than wedging the player on a file they cannot see or delete.
        logger.exception("Discarding unreadable session save for %s", case_id)
        return None


def get_session(case_id: str = "case_001") -> Session:
    if case_id not in _sessions:
        _sessions[case_id] = _load_session(case_id) or Session(case_id)
    return _sessions[case_id]


def reset_session(case_id: str = "case_001") -> Session:
    _sessions[case_id] = Session(case_id)
    if _persist_enabled():
        _session_path(case_id).unlink(missing_ok=True)
    return _sessions[case_id]


def reset_session_store() -> None:
    _sessions.clear()


def has_saved_session(case_id: str) -> bool:
    return _persist_enabled() and _session_path(case_id).exists()


def load_session_summary(case_id: str) -> Optional[dict]:
    """A cheap 'is there an investigation here?' peek for the case library.

    Reads the live session if the case is already loaded in memory, otherwise the save on disk.
    Returns None when the case has never been opened.
    """
    sess = _sessions.get(case_id)
    if sess is None:
        if not has_saved_session(case_id):
            return None
        try:
            data = json.loads(_session_path(case_id).read_text())
        except Exception:
            return None
        return {
            "clues_found": len(data.get("discovered_clue_ids", [])),
            "suspects_interviewed": len(data.get("transcripts", {})),
            "notes": len(data.get("notes", {})),
            "hints_taken": data.get("hint_count", 0),
            "accused": data.get("accusation") is not None,
        }

    return {
        "clues_found": len(sess.discovered_clue_ids),
        "suspects_interviewed": len(sess.transcripts),
        "notes": len(sess.notes),
        "hints_taken": sess.hint_count,
        "accused": sess.accusation is not None,
    }
