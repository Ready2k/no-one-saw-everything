"""Mutable player-session state.

An *investigation* is everything one player has discovered, noted, or been told in one
case; the locked case truth never changes. Investigations are scoped by a player id
(an opaque browser token sent as X-Session-Id; tokenless clients share the "local"
player) so concurrent players never see each other's notebooks — the reveal gate is
only sound if one player's accusation cannot unlock the truth for another.

On disk each player owns a directory of saves:

    data/sessions/<player_id>/meta.json        # per-player state (active case)
    data/sessions/<player_id>/<case_id>.json   # one investigation per case

Saves carry a schema_version. A save from a *newer* schema refuses to load with a
clear message (never a 500, never silent loss); an unreadable file is quarantined
beside the original so nothing is destroyed. The pre-versioning MVP layout
(data/sessions/<case_id>.json, one global player) is migrated into local/ on first use.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Optional

from .models import (
    AccusationResult,
    AgentBeliefState,
    ChallengeRecord,
    Claim,
    BehaviouralBaseline,
    InterviewTranscript,
    Note,
    ObservationRead,
    SuspicionLevel,
    MarkerType,
    Feedback,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2

DEFAULT_PLAYER_ID = "local"


class SessionLoadError(Exception):
    """A saved investigation exists but cannot be used. The message is player-facing."""


class Session:
    def __init__(self, case_id: str, player_id: str = DEFAULT_PLAYER_ID):
        self.case_id = case_id
        self.player_id = player_id
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
        # How each suspect behaves when calm, quietly remembered from their first
        # unpressured answer; later reads compare against it. baseline_shift_noted
        # records which pressure bands have already produced a "different from
        # earlier" tell, so the comparison lands once per escalation, as news.
        self.baselines: dict[str, BehaviouralBaseline] = {}
        self.baseline_shift_noted: dict[str, list[int]] = {}
        # Set when this session replaced a save that could not be read; the original
        # file was quarantined, not deleted. Surfaced once via /api/cases/activate.
        self.recovered_from_corrupt_save: bool = False
        # Tripped the first time a configured LLM call fails to connect (timeout,
        # refused, unresolvable host). Once set, dialogue rewriting skips straight
        # to the deterministic fallback instead of hanging on the same dead host
        # again — the point of a session-scoped, in-memory-only breaker rather than
        # a config flag is that it clears itself the moment a new investigation
        # starts (new case, restart, or a backend restart), so a host that comes
        # back online gets tried again next game rather than needing a manual reset.
        self.llm_unavailable: bool = False
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
            "schema_version": SCHEMA_VERSION,
            "case_id": self.case_id,
            "player_id": self.player_id,
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
            "baselines": {k: v.model_dump() for k, v in self.baselines.items()},
            "baseline_shift_noted": {k: list(v) for k, v in self.baseline_shift_noted.items()},
            "notes_issued": self._notes_issued,
            "challenges_issued": self._challenges_issued,
            "observations_issued": self._observations_issued,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        # Version 1 saves (the MVP) carried no schema_version; every v1 field has a
        # v2 default, so they migrate by loading. A save from a FUTURE schema is the
        # one thing we must not guess at — refuse it loudly rather than load half of it.
        version = data.get("schema_version", 1)
        if version > SCHEMA_VERSION:
            raise SessionLoadError(
                f"This saved investigation was written by a newer version of the game "
                f"(save schema v{version}, this server reads up to v{SCHEMA_VERSION}). "
                "Update the server, or restart the case to begin a fresh investigation."
            )
        s = cls(data["case_id"], data.get("player_id", DEFAULT_PLAYER_ID))
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
        s.baselines = {
            k: BehaviouralBaseline(**v) for k, v in data.get("baselines", {}).items()
        }
        s.baseline_shift_noted = {
            k: list(v) for k, v in data.get("baseline_shift_noted", {}).items()
        }
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


# (player_id, case_id) -> Session. One process owns the store: run a single worker.
_sessions: dict[tuple[str, str], Session] = {}

# Saved investigations live beside the case data. Disabled entirely under pytest (and by
# MYSTERY_SESSION_PERSIST=0) so tests never see each other's saves — test_isolation.py exists
# precisely because leaking state between cases is the bug class this file attracts.
SESSIONS_DIR = Path(__file__).parent / "data" / "sessions"

_store_lock = threading.RLock()
_player_locks: dict[str, threading.RLock] = {}


def _lock_for(player_id: str) -> threading.RLock:
    with _store_lock:
        if player_id not in _player_locks:
            _player_locks[player_id] = threading.RLock()
        return _player_locks[player_id]


def _persist_enabled() -> bool:
    if os.environ.get("MYSTERY_SESSION_PERSIST") == "0":
        return False
    return "PYTEST_CURRENT_TEST" not in os.environ


def sanitize_player_id(raw: Optional[str]) -> str:
    """Player ids come off the wire (X-Session-Id) and become directory names.

    Anything that isn't a plain token collapses to the shared local player rather
    than erroring: an investigation must never be lost to a malformed header, and
    the id namespace must never reach the filesystem unfiltered.
    """
    if not raw:
        return DEFAULT_PLAYER_ID
    raw = raw.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", raw):
        return DEFAULT_PLAYER_ID
    return raw


def _safe_case_component(case_id: str) -> str:
    # case_ids are generated internally (case_001, gen_<type>_<seed>_<ts>), but this path is
    # built from one, so refuse anything that could climb out of the sessions directory.
    return re.sub(r"[^A-Za-z0-9_.-]", "_", case_id).lstrip(".")


def _player_dir(player_id: str) -> Path:
    return SESSIONS_DIR / sanitize_player_id(player_id)


def _session_path(case_id: str, player_id: str = DEFAULT_PLAYER_ID) -> Path:
    return _player_dir(player_id) / f"{_safe_case_component(case_id)}.json"


def _meta_path(player_id: str) -> Path:
    return _player_dir(player_id) / "meta.json"


# ------------------------------------------------------------------ legacy layout
# The MVP stored one global player's saves flat in data/sessions/<case_id>.json.
# Move them under local/ once; the first *tokened* player to appear then adopts
# local/'s investigations, because before tokens existed that browser WAS the
# local player and must not wake up to an empty case library.

_LEGACY_MIGRATED = False
_META_FILENAMES = {"meta.json", "active_state.json"}


def _migrate_legacy_layout() -> None:
    global _LEGACY_MIGRATED
    if _LEGACY_MIGRATED or not _persist_enabled() or not SESSIONS_DIR.exists():
        _LEGACY_MIGRATED = True
        return
    with _store_lock:
        local_dir = SESSIONS_DIR / DEFAULT_PLAYER_ID
        for p in SESSIONS_DIR.iterdir():
            if p.is_file() and p.suffix == ".json" and p.name not in _META_FILENAMES:
                try:
                    local_dir.mkdir(parents=True, exist_ok=True)
                    target = local_dir / p.name
                    if not target.exists():
                        p.rename(target)
                    else:
                        p.unlink()
                except OSError:
                    logger.exception("Could not migrate legacy save %s", p)
        _LEGACY_MIGRATED = True


def _maybe_adopt_local_saves(player_id: str) -> None:
    """Give the first tokened player the pre-token ('local') investigations."""
    if player_id == DEFAULT_PLAYER_ID or not _persist_enabled():
        return
    with _store_lock:
        player_dir = _player_dir(player_id)
        if player_dir.exists():
            return
        local_dir = SESSIONS_DIR / DEFAULT_PLAYER_ID
        marker = local_dir / "adopted_by.json"
        if not local_dir.exists() or marker.exists():
            return
        saves = [p for p in local_dir.glob("*.json") if p.name not in _META_FILENAMES]
        if not saves:
            return
        player_dir.mkdir(parents=True, exist_ok=True)
        for p in saves + ([local_dir / "meta.json"] if (local_dir / "meta.json").exists() else []):
            try:
                p.rename(player_dir / p.name)
            except OSError:
                logger.exception("Could not adopt legacy save %s", p)
        try:
            marker.write_text(json.dumps({"adopted_by": player_id, "at": time.time()}))
        except OSError:
            logger.exception("Could not write adoption marker")


# ------------------------------------------------------------------ player meta

def _load_meta(player_id: str) -> dict:
    if not _persist_enabled():
        return dict(_meta_memory.get(sanitize_player_id(player_id), {}))
    path = _meta_path(player_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        logger.exception("Unreadable player meta for %s", player_id)
        return {}


def _save_meta(player_id: str, meta: dict) -> None:
    player_id = sanitize_player_id(player_id)
    if not _persist_enabled():
        _meta_memory[player_id] = dict(meta)
        return
    with _lock_for(player_id):
        path = _meta_path(player_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"schema_version": SCHEMA_VERSION, **meta}, indent=2))
        tmp.replace(path)


# Under pytest (persistence off) meta still needs to behave per-player in memory.
_meta_memory: dict[str, dict] = {}


def get_active_case(player_id: str) -> Optional[str]:
    _migrate_legacy_layout()
    _maybe_adopt_local_saves(sanitize_player_id(player_id))
    return _load_meta(player_id).get("active_case_id")


def set_active_case(player_id: str, case_id: str) -> None:
    _migrate_legacy_layout()
    meta = _load_meta(player_id)
    meta["active_case_id"] = case_id
    _save_meta(player_id, meta)


# ------------------------------------------------------------------ save / load

def save_session(session: Session) -> None:
    if not _persist_enabled():
        return
    try:
        with _lock_for(session.player_id):
            path = _session_path(session.case_id, session.player_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Write-then-rename: a crash mid-write must not leave a half-written investigation.
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(session.to_dict(), indent=2, ensure_ascii=False))
            tmp.replace(path)
    except Exception:
        # Losing a save is bad; taking the player's game down to report it is worse.
        logger.exception(
            "Failed to save session for %s/%s", session.player_id, session.case_id
        )


def _quarantine(path: Path) -> None:
    """Set an unreadable save aside — never destroy what might be recoverable."""
    target = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
    try:
        path.rename(target)
        logger.warning("Quarantined unreadable save %s -> %s", path, target.name)
    except OSError:
        logger.exception("Could not quarantine %s", path)


def _load_session(case_id: str, player_id: str) -> Optional[Session]:
    """Load a saved investigation from disk.

    Returns None when there is no usable save. Raises SessionLoadError only for a
    future-schema save (the one case where starting fresh would silently discard
    data a newer server could still read).
    """
    if not _persist_enabled():
        return None
    _migrate_legacy_layout()
    path = _session_path(case_id, player_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        logger.exception("Corrupt session save for %s/%s", player_id, case_id)
        _quarantine(path)
        fresh = Session(case_id, player_id)
        fresh.recovered_from_corrupt_save = True
        return fresh
    try:
        s = Session.from_dict(data)
    except SessionLoadError:
        raise
    except Exception:
        # Parsed as JSON but the fields no longer fit any schema we know: treat it
        # like corruption — quarantine and recover — rather than wedging the player.
        logger.exception("Unloadable session save for %s/%s", player_id, case_id)
        _quarantine(path)
        fresh = Session(case_id, player_id)
        fresh.recovered_from_corrupt_save = True
        return fresh
    s.case_id = case_id
    s.player_id = sanitize_player_id(player_id)
    return s


def peek_session(case_id: str, player_id: str = DEFAULT_PLAYER_ID) -> Optional[Session]:
    """The in-memory session if one is loaded — never loads or creates one."""
    return _sessions.get((sanitize_player_id(player_id), case_id))


def get_session(case_id: str = "case_001", player_id: str = DEFAULT_PLAYER_ID) -> Session:
    player_id = sanitize_player_id(player_id)
    _maybe_adopt_local_saves(player_id)
    key = (player_id, case_id)
    with _lock_for(player_id):
        if key not in _sessions:
            _sessions[key] = _load_session(case_id, player_id) or Session(case_id, player_id)
        return _sessions[key]


def reset_session(case_id: str = "case_001", player_id: str = DEFAULT_PLAYER_ID) -> Session:
    player_id = sanitize_player_id(player_id)
    key = (player_id, case_id)
    with _lock_for(player_id):
        _sessions[key] = Session(case_id, player_id)
        if _persist_enabled():
            _session_path(case_id, player_id).unlink(missing_ok=True)
        return _sessions[key]


def reset_session_store() -> None:
    global _LEGACY_MIGRATED
    _sessions.clear()
    _meta_memory.clear()
    _LEGACY_MIGRATED = False


def has_saved_session(case_id: str, player_id: str = DEFAULT_PLAYER_ID) -> bool:
    if not _persist_enabled():
        return False
    _migrate_legacy_layout()
    return _session_path(case_id, player_id).exists()


def delete_investigation(case_id: str, player_id: str = DEFAULT_PLAYER_ID) -> bool:
    """Drop one investigation — memory and disk. Returns True if anything existed."""
    player_id = sanitize_player_id(player_id)
    key = (player_id, case_id)
    with _lock_for(player_id):
        existed = key in _sessions
        _sessions.pop(key, None)
        if _persist_enabled():
            path = _session_path(case_id, player_id)
            if path.exists():
                path.unlink()
                existed = True
    return existed


def list_investigations(player_id: str = DEFAULT_PLAYER_ID) -> list[dict]:
    """Every investigation this player has, on disk or in memory, with a summary."""
    player_id = sanitize_player_id(player_id)
    _migrate_legacy_layout()
    _maybe_adopt_local_saves(player_id)
    case_ids: set[str] = {cid for (pid, cid) in _sessions if pid == player_id}
    if _persist_enabled():
        player_dir = _player_dir(player_id)
        if player_dir.exists():
            for p in player_dir.glob("*.json"):
                if p.name not in _META_FILENAMES and not p.name.endswith(".tmp"):
                    case_ids.add(p.stem)
    out = []
    for cid in sorted(case_ids):
        summary = load_session_summary(cid, player_id)
        if summary is not None:
            out.append({"case_id": cid, **summary})
    return out


def load_session_summary(case_id: str, player_id: str = DEFAULT_PLAYER_ID) -> Optional[dict]:
    """A cheap 'is there an investigation here?' peek for the case library.

    Reads the live session if the case is already loaded in memory, otherwise the save on disk.
    Returns None when the case has never been opened.
    """
    player_id = sanitize_player_id(player_id)
    sess = _sessions.get((player_id, case_id))
    if sess is None:
        if not has_saved_session(case_id, player_id):
            return None
        try:
            data = json.loads(_session_path(case_id, player_id).read_text())
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
