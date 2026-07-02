"""Loads a locked case from disk. Case data is immutable during play."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import (
    Agent,
    AgentInterviewPack,
    CaseData,
    CaseFile,
    Clue,
    Conclusion,
    Event,
    GameObject,
    Location,
    SeededMemory,
)

DATA_DIR = Path(__file__).parent / "data"


def _load_json(case_dir: Path, name: str):
    return json.loads((case_dir / name).read_text())


@lru_cache(maxsize=8)
def load_case(case_id: str = "case_001") -> CaseData:
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
    )


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)
