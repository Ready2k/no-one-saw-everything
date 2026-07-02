"""Mutable player-session state.

One in-memory session per case for the MVP. Everything the player has
discovered, noted, or been told lives here; the locked case truth never
changes.
"""

from __future__ import annotations

import itertools

from .models import Claim, InterviewTranscript, Note, SuspicionLevel


class Session:
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.discovered_clue_ids: set[str] = set()
        self.pinned_event_ids: set[str] = set()
        self.inspected_location_ids: set[str] = set()
        self.claims: dict[str, Claim] = {}
        self.transcripts: dict[str, InterviewTranscript] = {}
        self.notes: dict[str, Note] = {}
        self.suspicion: dict[str, SuspicionLevel] = {}
        self._note_counter = itertools.count(1)

    def next_note_id(self) -> str:
        return f"note_{next(self._note_counter):03d}"

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
