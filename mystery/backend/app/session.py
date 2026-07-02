"""Mutable player-session state.

One in-memory session per case for the MVP. Everything the player has
discovered, noted, or been told lives here; the locked case truth never
changes.
"""

from __future__ import annotations

import itertools

from typing import Optional

from .models import (
    AccusationResult,
    ChallengeRecord,
    Claim,
    InterviewTranscript,
    Note,
    SuspicionLevel,
    MarkerType,
    Feedback,
)


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
        self.feedback: Optional[Feedback] = None
        self._note_counter = itertools.count(1)
        self._challenge_counter = itertools.count(1)

    def next_note_id(self) -> str:
        return f"note_{next(self._note_counter):03d}"

    def next_challenge_id(self) -> str:
        return f"challenge_{next(self._challenge_counter):03d}"

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


def get_session(case_id: str = "case_001") -> Session:
    if case_id not in _sessions:
        _sessions[case_id] = Session(case_id)
    return _sessions[case_id]


def reset_session(case_id: str = "case_001") -> Session:
    _sessions[case_id] = Session(case_id)
    return _sessions[case_id]


def reset_session_store() -> None:
    _sessions.clear()
