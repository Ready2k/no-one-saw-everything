"""Manages loading static cases and registering procedurally generated cases."""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

from .models import (
    Agent,
    AgentInterviewPack,
    CaseData,
    CaseFile,
    ChallengeRule,
    Clue,
    Conclusion,
    Event,
    GameObject,
    Location,
    SeededMemory,
    Solution,
)

DATA_DIR = Path(__file__).parent / "data"

_GENERATED_CASES: dict[str, CaseData] = {}
REQUIRED_CASE_FILES = {
    "case.json",
    "agents.json",
    "locations.json",
    "objects.json",
    "memories.json",
    "events.json",
    "interviews.json",
    "solution.json",
    "clues.json",
}


def reset_case_store() -> None:
    _GENERATED_CASES.clear()
    load_case_from_disk.cache_clear()
    # The danger table is keyed by case id and derived from the case's claims,
    # so a store reset must invalidate it too — otherwise a regenerated case
    # reusing an id is enforced against its predecessor's pairs.
    from .danger_table import reset_danger_table_cache

    reset_danger_table_cache()


def _load_json(case_dir: Path, name: str):
    return json.loads((case_dir / name).read_text())


_CASE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


def is_safe_case_id(case_id: str) -> bool:
    """Case ids become path components under DATA_DIR; anything else is an attack.

    Generated internally they are `case_00N` / `gen_<type>_<seed>_<ts>`, but several
    endpoints accept them off the wire — a `..` segment must never reach Path joins.
    """
    return bool(_CASE_ID_RE.fullmatch(case_id)) and ".." not in case_id


class CaseLoadError(Exception):
    def __init__(self, load_status: str, message: str):
        super().__init__(message)
        self.load_status = load_status


def normalize_case_metadata(raw_metadata: dict | None) -> dict:
    if raw_metadata is None:
        raw_metadata = {}
    normalized = {
        "metadata_version": raw_metadata.get("metadata_version", 1),
        "mode": raw_metadata.get("mode", "deterministic"),
        "seed": raw_metadata.get("seed", 12345),
        "selected_seed": raw_metadata.get("selected_seed", raw_metadata.get("seed", 12345)),
        "best_of_n_used": raw_metadata.get("best_of_n_used", False),
        "num_suspects": raw_metadata.get("num_suspects"),
        "num_locations": raw_metadata.get("num_locations"),
        "theme_preset": raw_metadata.get("theme_preset", "blackmail"),
        "custom_theme": raw_metadata.get("custom_theme"),
        "tone": raw_metadata.get("tone", "standard"),
        "fallback_used": raw_metadata.get("fallback_used", False),
        "repair_attempts": raw_metadata.get("repair_attempts", 0),
        "compaction_applied": raw_metadata.get("compaction_applied", False),
        "created_at": raw_metadata.get("created_at"),
        "activated_at": raw_metadata.get("activated_at"),
        "quality_report": raw_metadata.get("quality_report"),
    }
    candidate_scores = raw_metadata.get("candidate_scores", [])
    if candidate_scores:
        normalized["candidate_count"] = len(candidate_scores)
    else:
        normalized["candidate_count"] = raw_metadata.get("candidate_count", 1)
    return normalized


@lru_cache(maxsize=8)
def load_case_from_disk(case_id: str) -> CaseData:
    """Loads a static, hand-authored case or procedurally generated case from the data directory."""
    if not is_safe_case_id(case_id):
        raise CaseLoadError("missing_case_data", f"Invalid case id: {case_id!r}")
    case_dir = DATA_DIR / case_id
    if case_id.startswith("case_") and not case_dir.is_dir():
        case_dir = Path(__file__).parent / "data" / case_id
    if not case_dir.is_dir():
        raise CaseLoadError("missing_case_data", f"No case directory: {case_dir}")

    # Load metadata
    metadata = None
    load_status = "ok"
    metadata_file = case_dir / "metadata.json"
    if metadata_file.exists():
        try:
            metadata = json.loads(metadata_file.read_text())
            metadata = normalize_case_metadata(metadata)
        except json.JSONDecodeError:
            load_status = "corrupted_metadata"
            metadata = normalize_case_metadata(None)
    else:
        load_status = "missing_metadata"
        metadata = normalize_case_metadata(None)

    metadata["load_status"] = load_status

    # Load case files
    try:
        clue_pack = _load_json(case_dir, "clues.json")
        return CaseData(
            case=CaseFile(**_load_json(case_dir, "case.json")),
            agents=[Agent(**a) for a in _load_json(case_dir, "agents.json")],
            locations=[Location(**l) for l in _load_json(case_dir, "locations.json")],
            objects=[GameObject(**o) for o in _load_json(case_dir, "objects.json")],
            memories=[SeededMemory(**m) for m in _load_json(case_dir, "memories.json")],
            events=[Event(**e) for e in _load_json(case_dir, "events.json")],
            clues=[Clue(**c) for c in clue_pack["clues"]],
            conclusions=[Conclusion(**c) for c in clue_pack["conclusions"]],
            interview_packs=[AgentInterviewPack(**p) for p in _load_json(case_dir, "interviews.json")],
            challenge_rules=[ChallengeRule(**c) for c in _load_json(case_dir, "challenges.json")] if (case_dir / "challenges.json").exists() else [],
            solution=Solution(**_load_json(case_dir, "solution.json")),
            metadata=metadata
        )
    except Exception as e:
        raise CaseLoadError("missing_case_data", f"Error loading case files: {e}")


def get_case(case_id: str) -> CaseData:
    """Gets a case from the generated registry or disk."""
    if case_id in _GENERATED_CASES:
        return _GENERATED_CASES[case_id]
    return load_case_from_disk(case_id)


def register_case(case_data: CaseData):
    """Registers a procedurally generated case so it can be played."""
    _GENERATED_CASES[case_data.case.case_id] = case_data


def save_case_to_disk(case_data: CaseData) -> None:
    """Persists a procedurally generated CaseData to disk."""
    case_id = case_data.case.case_id
    case_dir = DATA_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    with open(case_dir / "case.json", "w") as f:
        json.dump(json.loads(case_data.case.model_dump_json()), f, indent=2)
    with open(case_dir / "agents.json", "w") as f:
        json.dump([json.loads(a.model_dump_json()) for a in case_data.agents], f, indent=2)
    with open(case_dir / "locations.json", "w") as f:
        json.dump([json.loads(l.model_dump_json()) for l in case_data.locations], f, indent=2)
    with open(case_dir / "objects.json", "w") as f:
        json.dump([json.loads(o.model_dump_json()) for o in case_data.objects], f, indent=2)
    with open(case_dir / "memories.json", "w") as f:
        json.dump([json.loads(m.model_dump_json()) for m in case_data.memories], f, indent=2)
    with open(case_dir / "events.json", "w") as f:
        json.dump([json.loads(e.model_dump_json()) for e in case_data.events], f, indent=2)
    with open(case_dir / "interviews.json", "w") as f:
        json.dump([json.loads(i.model_dump_json()) for i in case_data.interview_packs], f, indent=2)
    with open(case_dir / "challenges.json", "w") as f:
        json.dump([json.loads(c.model_dump_json()) for c in case_data.challenge_rules], f, indent=2)
    with open(case_dir / "solution.json", "w") as f:
        json.dump(json.loads(case_data.solution.model_dump_json()), f, indent=2)

    if case_data.metadata:
        with open(case_dir / "metadata.json", "w") as f:
            json.dump(case_data.metadata, f, indent=2)

    clue_pack = {
        "clues": [json.loads(c.model_dump_json()) for c in case_data.clues],
        "conclusions": [json.loads(con.model_dump_json()) for con in case_data.conclusions]
    }
    with open(case_dir / "clues.json", "w") as f:
        json.dump(clue_pack, f, indent=2)

    # Layer 7 §9.1. Written here rather than computed on first play so the
    # O(n^2) pass stays at build time, and — like solution.json — it is written
    # but never loaded back into CaseData, so nothing downstream can serialise
    # it to a client.
    from .danger_table import build_danger_table, save_danger_table

    save_danger_table(case_id, build_danger_table(case_data))


def list_all_cases() -> list[dict[str, str]]:
    """Lists all available cases from the data directory (both static and persistent generated)."""
    cases = []
    if not DATA_DIR.exists():
        return cases

    for p in DATA_DIR.iterdir():
        if p.is_dir() and p.name != "templates":
            case_json_path = p / "case.json"
            if case_json_path.exists() and REQUIRED_CASE_FILES <= {f.name for f in p.iterdir() if f.is_file()}:
                try:
                    with open(case_json_path) as f:
                        case_info = json.load(f)
                    cases.append({
                        "case_id": p.name,
                        "title": case_info.get("title", "Untitled Case"),
                        "case_type": case_info.get("case_type", "unknown")
                    })
                except Exception:
                    pass

    # Sort case_001, case_002... first, then others (procedural generated cases)
    def sort_key(c):
        cid = c["case_id"]
        if cid.startswith("case_"):
            return (0, cid)
        return (1, cid)

    cases.sort(key=sort_key)
    return cases


# The reference point for midnight wrapping in minutes(). A ContextVar, not a module
# global: two concurrent requests can be playing different cases (a 07:30 morning case
# and case_004's 22:00 night case), and each request must wrap times against its own
# case's clock. The request middleware sets this from the resolved active case; code
# running outside a request (tests, generators) sets it explicitly.
_ACTIVE_START_TIME: ContextVar[str | None] = ContextVar("mystery_start_time", default=None)


def set_active_start_time(start_time: str) -> None:
    _ACTIVE_START_TIME.set(start_time)


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    mins = int(h) * 60 + int(m)

    start = _ACTIVE_START_TIME.get()
    if start:
        sh, sm = start.split(":")
        start_mins = int(sh) * 60 + int(sm)
        if mins < start_mins:
            mins += 1440

    return mins


class CaseDeleteError(Exception):
    """Refusing to delete: the message says why and is safe to surface."""


def delete_case_from_disk(case_id: str) -> None:
    """Removes a *generated* case from the data directory and registry.

    Hand-authored cases (case_001..) are shipped content and must never be deletable
    over the API; and case_id is wire input, so it must be validated before it comes
    anywhere near a recursive delete.
    """
    if not is_safe_case_id(case_id):
        raise CaseDeleteError("Invalid case id.")
    if not case_id.startswith("gen_"):
        raise CaseDeleteError("Only generated cases (gen_*) can be deleted.")

    if case_id in _GENERATED_CASES:
        del _GENERATED_CASES[case_id]
    load_case_from_disk.cache_clear()

    case_dir = DATA_DIR / case_id
    if case_dir.is_dir():
        import shutil
        shutil.rmtree(case_dir)
