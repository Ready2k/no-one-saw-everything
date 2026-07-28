"""Layer 2 — Structured Claim Store (ENGINE_SPEC.md §4 / §4.1 / §4.2).

Two schemas live here, deliberately kept separate:

- `Fact` is *authored* content — the persona's grounding pack, written once,
  never mutated. `Trigger` (`ConceptTrigger` / `LiteralTrigger`) and
  `GateCondition` are its sub-schemas, pinned down per §4.1.
- `Claim` is what a `Fact` becomes the moment it's actually revealed to a
  player in a session — timestamped, logged into a `ClaimStore`, and shaped
  to match the shipped game's `Claim` model (`mystery/backend/app/models.py`)
  closely enough to be a valid input to `testimony.py:find_conflict` without
  translation, per §4's reuse promise.

This module intentionally does NOT do any matching/scoring — that's Layer 4
(`concepts.py`, and `engine.py`'s keyword scorer), which this schema is
built to plug into unchanged: `ConceptTrigger.concept_groups` is exactly the
`list[frozenset[str]]` shape `concepts.concept_group_score` already expects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# An agent_id, or the SELF sentinel meaning "the persona being interviewed,
# not a third party". §5.1: `Fact.subject` is never left implicit.
AgentRef = str
SELF: AgentRef = "SELF"

Truthfulness = Literal["true", "false", "mistaken"]


def minutes(hhmm_str: str) -> int:
    """"HH:MM" -> minutes since 00:00.

    Deliberately simpler than the shipped game's `case_store.minutes()`:
    no cross-midnight wraparound relative to an active case start time,
    because every case in this lab runs within a single morning. If this
    module ever needs to interoperate with a case that crosses midnight,
    port that logic over rather than growing it here unasked.
    """
    h, m = hhmm_str.split(":")
    return int(h) * 60 + int(m)


def hhmm(total_minutes: int) -> str:
    """Inverse of `minutes()` — needed by §4.2's migration, since the
    sandbox's legacy fact data stores `time_reference` as raw minutes
    (`435`) rather than the "HH:MM" string this schema and the shipped
    `Claim` model both use."""
    h, m = divmod(total_minutes, 60)
    return f"{h:02d}:{m:02d}"


# ---------------------------------------------------------------------------
# Trigger — §4.1. A property of the FACT, not the persona: this is what lets
# §5.3's literal-only exemption (accusation, confession-adjacent language)
# coexist with concept clustering everywhere else on the same persona.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConceptTrigger:
    # Same shape `concepts.concept_group_score(groups, present)` already
    # scores: a fact matches a group if every concept name in that frozenset
    # is present in the question. Stored as a tuple, not a list — see
    # `Fact`'s __post_init__ note: `frozen=True` alone doesn't stop a list
    # field from being mutated in place, only tuples/frozensets actually
    # deliver on "authored content, never mutated".
    concept_groups: tuple[frozenset[str], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "concept_groups", tuple(self.concept_groups))


@dataclass(frozen=True)
class LiteralTrigger:
    keywords: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "keywords", tuple(self.keywords))


Trigger = ConceptTrigger | LiteralTrigger


@dataclass(frozen=True)
class GateCondition:
    """A fact becomes eligible only once `topic` has been asked at least
    `min_ask` times. Formalises `engine.py:_match_fact`'s existing
    `gate_topic`/`gate_min_ask` dict keys — no behaviour change, see §4.1."""

    topic: str
    min_ask: int = 1

    def met(self, ask_counts: dict[str, int]) -> bool:
        return ask_counts.get(self.topic, 0) >= self.min_ask


@dataclass(frozen=True)
class Fact:
    topic: str
    subject: AgentRef
    trigger: Trigger
    opening_variants: tuple[str, ...]
    repeat_variants: tuple[str, ...] = ()
    time_reference: str | None = None
    location_reference_id: str | None = None
    truthfulness: Truthfulness = "true"
    sensitive: bool = False
    accusation: bool = False
    # Not in the original §4 sketch — added while building this module.
    # A fact can PLACE someone (an alibi: "I was in my yard") or DENY a
    # placement ("she was never at the fountain"); testimony.py's
    # bilocation/denial math needs to know which. Every fact authored so
    # far asserts presence, hence the default, but a denial-shaped fact
    # (§4's whole reason for mirroring the shipped `Claim` model) is
    # unrepresentable without this field.
    asserts_presence: bool = True
    gate: GateCondition | None = None

    def __post_init__(self) -> None:
        # `frozen=True` only blocks *reassigning* a field — it does nothing
        # to stop `fact.opening_variants.append(...)` on a list field, and a
        # dataclass with any unhashable field (a list) is itself unhashable
        # even though it's "frozen". Tuples close both gaps at once.
        # `object.__setattr__` is the documented way to set a field from
        # inside a frozen dataclass's own __post_init__.
        object.__setattr__(self, "opening_variants", tuple(self.opening_variants))
        object.__setattr__(self, "repeat_variants", tuple(self.repeat_variants))


# ---------------------------------------------------------------------------
# Claim — what a Fact becomes once it's actually said out loud in a session.
# Field-for-field aligned with mystery/backend/app/models.py's Claim, so a
# ClaimStore's contents are a valid `testimony.find_conflict` input as-is.
# ---------------------------------------------------------------------------


@dataclass
class Claim:
    claim_id: str
    speaker_agent_id: str
    claim_text: str
    topic: str
    claim_type: str = "statement"
    time_reference: str | None = None
    # Always None for now: every authored Fact is a single point in time,
    # never a span ("I was home all evening"). Kept as a field, not omitted,
    # so a future span-shaped fact doesn't need a schema change to use it.
    time_to: str | None = None
    location_reference_id: str | None = None
    truthfulness: Truthfulness = "true"
    player_known_status: str = "claimed"
    about_agent_id: AgentRef | None = None
    asserts_presence: bool = True


@dataclass
class ClaimStore:
    """Session-scoped log of every claim actually revealed to the player
    this playthrough — not the fact bank. §4: 'every fact the detective can
    extract becomes a first-class, timestamped claim the moment it's
    revealed.'"""

    claims: list[Claim] = field(default_factory=list)
    # Internal counter, not part of a ClaimStore's identity — two stores
    # holding the same claims should compare equal regardless of how many
    # `record()` calls it took to get there.
    _next_id: int = field(default=0, repr=False, compare=False)

    def record(self, fact: Fact, speaker_agent_id: str, text: str) -> Claim:
        self._next_id += 1
        # about_agent_id is "whose whereabouts this claim settles" (see
        # testimony.py), not just "who this fact is about" — a fact with no
        # time/location doesn't place anyone, so it must stay None rather
        # than silently defaulting to the speaker (testimony.py's own
        # documented mistake, first time round).
        places_someone = fact.time_reference is not None or fact.location_reference_id is not None
        about_agent_id = None
        if places_someone:
            about_agent_id = speaker_agent_id if fact.subject == SELF else fact.subject

        claim = Claim(
            claim_id=f"claim_{speaker_agent_id}_{fact.topic}_{self._next_id}",
            speaker_agent_id=speaker_agent_id,
            claim_text=text,
            topic=fact.topic,
            time_reference=fact.time_reference,
            location_reference_id=fact.location_reference_id,
            truthfulness=fact.truthfulness,
            about_agent_id=about_agent_id,
            asserts_presence=fact.asserts_presence,
        )
        self.claims.append(claim)
        return claim

    def by_topic(self, topic: str) -> list[Claim]:
        return [c for c in self.claims if c.topic == topic]

    def about(self, agent_id: AgentRef) -> list[Claim]:
        return [c for c in self.claims if c.about_agent_id == agent_id]


# ---------------------------------------------------------------------------
# §4.2 — migrating personas.py's legacy flat-dict facts. Everything here is
# mechanical except `subject`, which the caller must supply: it doesn't
# exist anywhere in the legacy data (subject exclusion was done via
# `exclude_keywords`/`exclude_concepts`, dropped here per §5), so there is
# nothing to derive it from. This function is the "few hours of scripting"
# half of §4.2's cost, not the "hand-audit every fact" half.
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    return "loc_" + "_".join(name.lower().replace("'", "").split())


def fact_from_legacy(raw: dict, *, subject: AgentRef) -> Fact:
    if "keywords" in raw:
        trigger: Trigger = LiteralTrigger(keywords=list(raw["keywords"]))
    elif "concept_groups" in raw:
        trigger = ConceptTrigger(concept_groups=list(raw["concept_groups"]))
    else:
        raise ValueError(f"fact {raw.get('topic')!r} has neither keywords nor concept_groups")

    gate = None
    if "gate_topic" in raw:
        gate = GateCondition(topic=raw["gate_topic"], min_ask=raw.get("gate_min_ask", 1))

    time_reference = None
    if "time_reference" in raw:
        time_reference = hhmm(raw["time_reference"])

    # No canonical location-ID registry exists in this sandbox (unlike the
    # shipped game's `loc_*` IDs from town_map.py) — this is a slugified
    # stand-in, not a real cross-referenceable ID. Flagged, not hidden.
    location_reference_id = None
    if "location_name" in raw:
        location_reference_id = _slugify(raw["location_name"])

    return Fact(
        topic=raw["topic"],
        subject=subject,
        trigger=trigger,
        opening_variants=list(raw.get("opening", [])),
        repeat_variants=list(raw.get("repeat", [])),
        time_reference=time_reference,
        location_reference_id=location_reference_id,
        truthfulness=raw.get("truthfulness", "true"),
        sensitive=raw.get("sensitive", False),
        accusation=raw.get("accusation", False),
        gate=gate,
    )
