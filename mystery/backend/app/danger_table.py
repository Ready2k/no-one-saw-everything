"""Layer 7 §9.1 — the combination-leak danger table.

`dialogue_rewriter._concept_combination_leak` already refuses a rewrite that
paraphrases the solution's answer key in the *same grading vocabulary*
`judge.py` scores an accusation with. It does that by scanning one finished
piece of text. That is enough while the model is only ever handed one
pre-computed answer to re-word.

It stops being enough the moment the model is handed the agent's whole claim
history and invited to reason across it — which is the entire point of Layer 7.
Two claims can each be individually harmless and still, *together*, spell out
the motive: "he gave me until this morning" plus "I was short on my mother's
care fees" is a confession assembled out of two innocent sentences. A live text
scan only sees the result; by then the model has already done the synthesis.

So the check moves earlier. For every pair of claims an agent can make, we
concatenate them offline and ask the existing scanner whether the *pair* clears
a facet's `min_groups` bar when neither half does alone. Every pair that does is
recorded as `(claim_id_a, claim_id_b) -> facet` in `danger_table.json`, written
beside `solution.json` and subject to the same firewall: it is never loaded into
`CaseData`, never projected, never served. Runtime enforcement is then an O(1)
set lookup on opaque claim ids, with no LLM judge call — a judge that had to see
the hidden solution to grade against it is exactly the step the truth firewall
forbids.

Two boundaries are deliberate:

* **§9.4 carve-out.** A pair where *both* claims pin a person to a place at a
  time never enters this table, and is refused outright at runtime. Narrowing
  identity by time and location ("only Marcus was near the shed at 8:05") is the
  single riskiest inference in the game, and `testimony.py` already settles it
  deterministically. Layer 7 does not get a second, softer opinion on Layer 6's
  question; its mandate is the motive/method/opportunity surface this table
  covers.
* **Pairs only.** `MAX_SOURCE_CLAIMS` is 2, so the table never needs triples —
  which is where O(n^2) over a few dozen claims would stop being cheap.
"""

from __future__ import annotations

import json
import logging
from itertools import combinations
from pathlib import Path
from typing import Optional, Protocol

from . import case_store
from .case_store import is_safe_case_id
from .models import CaseData

logger = logging.getLogger(__name__)

DANGER_TABLE_FILENAME = "danger_table.json"
DANGER_TABLE_VERSION = 1

# §9.3. Also the reason the table only ever has to be pairwise.
MAX_SOURCE_CLAIMS = 2

# pair of claim ids (sorted) -> the facet the pair would give away
DangerTable = dict[tuple[str, str], str]

_TABLE_CACHE: dict[str, DangerTable] = {}


class _Placeable(Protocol):
    """The fields shared by `models.Claim` and `models.AnswerClaim` that the
    carve-out needs — the table is built from authored `AnswerClaim`s and
    enforced against session `Claim`s, and both must answer the same way."""

    time_reference: Optional[str]
    location_reference_id: Optional[str]


def places_someone(claim: _Placeable) -> bool:
    """Does this claim pin somebody to a place at a time? — §9.4's test.

    Deliberately looser than `testimony._subject`, which also requires
    `about_agent_id` before it will reason about a claim. The carve-out is about
    what *kind* of inference a pair invites, not about whether Layer 6 would
    happen to fire on it: an unannotated "I was at the fountain at 07:50" is
    still a time/location claim, and an author forgetting `about_agent_id` must
    not quietly hand it to Layer 7 instead.
    """
    return bool(claim.time_reference and claim.location_reference_id)


def pair_key(claim_id_a: str, claim_id_b: str) -> tuple[str, str]:
    """Order-independent key: the model may cite a pair in either order."""
    return (claim_id_a, claim_id_b) if claim_id_a <= claim_id_b else (claim_id_b, claim_id_a)


def build_danger_table(case: CaseData) -> DangerTable:
    """Every dangerous claim pair in the case, computed offline (§9.1).

    Pairs are per-agent: two claims only combine into an inference in the
    player's ear when the same person says both.
    """
    # Imported here, not at module scope: `dialogue_rewriter` imports this
    # module for the runtime lookup, so a top-level import back into it would
    # close a cycle. The dependency is real and one-directional in meaning —
    # the table is precomputed *from* the sanitiser's own scoring — so the
    # local import is the honest way to express it.
    from .llm.dialogue_rewriter import _build_concept_facets, _concept_combination_leak

    facets = _build_concept_facets(case)
    table: DangerTable = {}

    for pack in case.interview_packs:
        by_id = {}
        for rule in pack.rules:
            for ac in rule.claims:
                by_id.setdefault(ac.claim_id, ac)
        claims = list(by_id.values())

        # A claim that trips a facet on its own is already blocked by the
        # existing single-text scan on every path. Pairing it with anything
        # would flag every pair it appears in, burying the pairs that are
        # dangerous *only* in combination — which are the ones this table
        # exists to find.
        solo = {
            ac.claim_id: _concept_combination_leak((ac.summary or "").lower(), "", facets)
            for ac in claims
        }

        for a, b in combinations(claims, 2):
            if solo[a.claim_id] or solo[b.claim_id]:
                continue
            if places_someone(a) and places_someone(b):
                continue  # §9.4 — Layer 6 owns this pair, and refuses it at runtime
            combined = f"{a.summary} {b.summary}".lower()
            leak = _concept_combination_leak(combined, "", facets)
            if leak:
                table[pair_key(a.claim_id, b.claim_id)] = leak

    return table


# ---------------------------------------------------------------------------
# Persistence. Server-only, by the same rule as solution.json: this file is
# never read into CaseData, so no projection or endpoint can accidentally
# serialise it.
# ---------------------------------------------------------------------------

def _serialise(table: DangerTable) -> dict:
    return {
        "version": DANGER_TABLE_VERSION,
        "pairs": [
            {"claim_ids": list(ids), "facet": facet}
            for ids, facet in sorted(table.items())
        ],
    }


def _deserialise(raw: dict) -> DangerTable:
    table: DangerTable = {}
    for entry in raw.get("pairs", []):
        ids = entry.get("claim_ids") or []
        if len(ids) != 2:
            continue
        table[pair_key(ids[0], ids[1])] = entry.get("facet", "unknown facet")
    return table


def _case_dir(case_id: str) -> Path:
    """Resolved per call, never snapshotted at import.

    `case_store.DATA_DIR` gets redirected — tests point it at a temp directory,
    and a `from .case_store import DATA_DIR` here would keep writing to the real
    one behind their backs. That is not hypothetical: it silently scattered
    danger tables through `app/data/` on every suite run before this was fixed.
    """
    return case_store.DATA_DIR / case_id


def save_danger_table(case_id: str, table: DangerTable) -> None:
    """Write the table beside the case's other locked files.

    Deliberately will not create the case directory. The table has no meaning
    on its own — it is an index into claims that live in `interviews.json` — so
    if there is no case here to sit beside, the right answer is to write
    nothing rather than to conjure a directory containing only this file.
    """
    if not is_safe_case_id(case_id):
        raise ValueError(f"Invalid case id: {case_id!r}")
    case_dir = _case_dir(case_id)
    if not case_dir.is_dir():
        logger.warning(f"No case directory for {case_id}; danger table not written.")
        return
    (case_dir / DANGER_TABLE_FILENAME).write_text(json.dumps(_serialise(table), indent=2))
    _TABLE_CACHE.pop(case_id, None)


def load_danger_table(case_id: str) -> Optional[DangerTable]:
    """The precomputed table from disk, or None if this case has none yet."""
    if not is_safe_case_id(case_id):
        return None
    path: Path = _case_dir(case_id) / DANGER_TABLE_FILENAME
    if not path.is_file():
        return None
    try:
        return _deserialise(json.loads(path.read_text()))
    except (OSError, ValueError) as e:
        logger.warning(f"Unreadable danger table for {case_id}, recomputing: {e}")
        return None


def get_danger_table(case: CaseData) -> DangerTable:
    """The case's danger table: from disk if it was built ahead of time, else
    computed now and cached.

    Computing at runtime is the fallback, not the design (§9.1 puts this at
    case-build time) — but a generated case that only ever lived in memory has
    no file to read, and the alternative to computing one is enforcing against
    an empty table, which is failing *open* on the exact surface this layer
    exists to guard.
    """
    case_id = case.case.case_id
    cached = _TABLE_CACHE.get(case_id)
    if cached is not None:
        return cached

    table = load_danger_table(case_id)
    if table is None:
        table = build_danger_table(case)
        logger.info(
            f"Danger table for {case_id} computed at runtime ({len(table)} pairs); "
            "no precomputed file on disk."
        )
    _TABLE_CACHE[case_id] = table
    return table


def reset_danger_table_cache() -> None:
    _TABLE_CACHE.clear()
