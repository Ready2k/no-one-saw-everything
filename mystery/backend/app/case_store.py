"""Manages loading static cases and registering procedurally generated cases."""

from __future__ import annotations

import json
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


def reset_case_store() -> None:
    _GENERATED_CASES.clear()
    load_case_from_disk.cache_clear()


def _load_json(case_dir: Path, name: str):
    return json.loads((case_dir / name).read_text())


@lru_cache(maxsize=8)
def load_case_from_disk(case_id: str) -> CaseData:
    """Loads a static, hand-authored case from the data directory."""
    case_dir = DATA_DIR / case_id
    if not case_dir.is_dir():
        raise FileNotFoundError(f"No case directory: {case_dir}")

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
    )


def get_case(case_id: str) -> CaseData:
    """Gets a case from the generated registry or disk."""
    if case_id in _GENERATED_CASES:
        return _GENERATED_CASES[case_id]
    return load_case_from_disk(case_id)


def register_case(case_data: CaseData):
    """Registers a procedurally generated case so it can be played."""
    _GENERATED_CASES[case_data.case.case_id] = case_data


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)
