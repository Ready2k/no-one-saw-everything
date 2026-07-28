"""Tests for claims.py — Layer 2's schema (ENGINE_SPEC.md §4/§4.1/§4.2).

Migration tests run against real facts pulled straight out of personas.py,
not hand-written fixtures — the point of §4.2 is that the mechanical half of
the migration works on the actual content, not on a toy example shaped to
make the code look good.
"""

import pytest

from claims import (
    SELF,
    ClaimStore,
    ConceptTrigger,
    Fact,
    GateCondition,
    LiteralTrigger,
    fact_from_legacy,
    hhmm,
    minutes,
)
from personas import OWEN, OWEN_TWIN


def _legacy_fact(persona: dict, topic: str) -> dict:
    return next(f for f in persona["facts"] if f["topic"] == topic)


# ---------------------------------------------------------------------------
# minutes()/hhmm()
# ---------------------------------------------------------------------------


def test_minutes_hhmm_round_trip():
    assert minutes("07:15") == 435
    assert hhmm(435) == "07:15"
    assert hhmm(minutes("08:12")) == "08:12"


# ---------------------------------------------------------------------------
# Fact immutability — frozen=True alone doesn't stop a list field from being
# mutated in place, or make the dataclass hashable. Regression test for that
# gap, found during review and closed by storing tuples instead of lists.
# ---------------------------------------------------------------------------


def test_fact_is_truly_immutable_and_hashable():
    fact = Fact(
        topic="alibi",
        subject=SELF,
        trigger=LiteralTrigger(keywords=["where were you"]),
        opening_variants=["I was in my yard."],
    )

    with pytest.raises(AttributeError):
        fact.topic = "changed"  # frozen dataclass: top-level reassignment blocked

    assert isinstance(fact.opening_variants, tuple)
    with pytest.raises(AttributeError):
        fact.opening_variants.append("smuggled in")  # tuples have no .append

    hash(fact)  # must not raise — a "frozen" fact that can't be hashed isn't


def test_fact_normalises_list_input_to_tuples():
    """A caller passing plain lists (as every call site in this file does)
    still ends up with tuples — the normalisation happens in __post_init__,
    not left to the caller to get right."""
    trigger = ConceptTrigger(concept_groups=[frozenset({"MONEY"})])
    assert isinstance(trigger.concept_groups, tuple)
    fact = Fact(topic="x", subject=SELF, trigger=trigger, opening_variants=["a", "b"])
    assert isinstance(fact.opening_variants, tuple)
    hash(fact)  # only possible because concept_groups and opening_variants are tuples


# ---------------------------------------------------------------------------
# GateCondition
# ---------------------------------------------------------------------------


def test_gate_condition_met():
    gate = GateCondition(topic="alibi", min_ask=1)
    assert not gate.met({})
    assert not gate.met({"alibi": 0})
    assert gate.met({"alibi": 1})
    assert gate.met({"alibi": 2})


def test_gate_condition_default_min_ask_is_one():
    assert GateCondition(topic="x").min_ask == 1


# ---------------------------------------------------------------------------
# ClaimStore.record — about_agent_id resolution
# ---------------------------------------------------------------------------


def test_record_self_subject_with_placement_resolves_to_speaker():
    store = ClaimStore()
    fact = Fact(
        topic="alibi",
        subject=SELF,
        trigger=LiteralTrigger(keywords=["where were you"]),
        opening_variants=["I was in my yard."],
        time_reference="07:15",
        location_reference_id="loc_his_yard",
    )
    claim = store.record(fact, speaker_agent_id="agent_owen", text="I was in my yard.")
    assert claim.about_agent_id == "agent_owen"
    assert claim.asserts_presence is True
    assert store.claims == [claim]


def test_record_third_party_subject_resolves_to_subject_not_speaker():
    store = ClaimStore()
    fact = Fact(
        topic="opinion_isabella",
        subject="agent_isabella",
        trigger=ConceptTrigger(concept_groups=[frozenset({"ISABELLA"})]),
        opening_variants=["She's always been kind to me."],
        time_reference="07:20",
        location_reference_id="loc_cafe",
    )
    claim = store.record(fact, speaker_agent_id="agent_owen", text="She's always been kind to me.")
    assert claim.about_agent_id == "agent_isabella"
    assert claim.speaker_agent_id == "agent_owen"


def test_record_fact_without_placement_has_no_about_agent_id():
    """A fact with no time/location doesn't settle anyone's whereabouts —
    about_agent_id must stay None, not silently default to the speaker
    (testimony.py's own documented mistake, first time round)."""
    store = ClaimStore()
    fact = Fact(
        topic="occupation",
        subject=SELF,
        trigger=LiteralTrigger(keywords=["what do you do"]),
        opening_variants=["I'm a builder."],
    )
    claim = store.record(fact, speaker_agent_id="agent_owen", text="I'm a builder.")
    assert claim.about_agent_id is None


def test_record_generates_distinct_ids_and_preserves_order():
    store = ClaimStore()
    fact = Fact(
        topic="alibi",
        subject=SELF,
        trigger=LiteralTrigger(keywords=["alibi"]),
        opening_variants=["..."],
    )
    first = store.record(fact, speaker_agent_id="agent_owen", text="first")
    second = store.record(fact, speaker_agent_id="agent_owen", text="second")
    assert first.claim_id != second.claim_id
    assert store.claims == [first, second]
    assert store.by_topic("alibi") == [first, second]


def test_by_topic_and_about_filter_correctly():
    store = ClaimStore()
    self_fact = Fact(
        topic="alibi", subject=SELF, trigger=LiteralTrigger(keywords=["x"]),
        opening_variants=["..."], time_reference="07:15", location_reference_id="loc_yard",
    )
    other_fact = Fact(
        topic="opinion_isabella", subject="agent_isabella",
        trigger=LiteralTrigger(keywords=["y"]), opening_variants=["..."],
        time_reference="07:20", location_reference_id="loc_cafe",
    )
    store.record(self_fact, speaker_agent_id="agent_owen", text="a")
    store.record(other_fact, speaker_agent_id="agent_owen", text="b")

    assert len(store.by_topic("alibi")) == 1
    assert len(store.about("agent_isabella")) == 1
    assert len(store.about("agent_owen")) == 1


# ---------------------------------------------------------------------------
# fact_from_legacy — against real personas.py content, not fixtures
# ---------------------------------------------------------------------------


def test_migrate_literal_fact_from_owen():
    raw = _legacy_fact(OWEN, "accusation")
    fact = fact_from_legacy(raw, subject=SELF)

    assert isinstance(fact.trigger, LiteralTrigger)
    assert "you killed him" in fact.trigger.keywords
    assert fact.accusation is True
    assert fact.sensitive is True
    assert fact.truthfulness == "true"
    assert fact.opening_variants == tuple(raw["opening"])
    assert fact.repeat_variants == tuple(raw["repeat"])


def test_migrate_literal_fact_with_time_and_location_from_owen():
    raw = _legacy_fact(OWEN, "alibi")
    fact = fact_from_legacy(raw, subject=SELF)

    # Legacy stores minutes as an int (435); the new schema stores "HH:MM".
    assert raw["time_reference"] == 435
    assert fact.time_reference == "07:15"
    assert fact.location_reference_id == "loc_his_yard"
    assert fact.gate is None


def test_migrate_concept_fact_from_owen_concepts_variant():
    raw = _legacy_fact(OWEN_TWIN, "alibi_corroboration")
    fact = fact_from_legacy(raw, subject=SELF)

    assert isinstance(fact.trigger, ConceptTrigger)
    assert frozenset({"WITNESS"}) in fact.trigger.concept_groups
    # gate_topic/gate_min_ask -> GateCondition, mechanically.
    assert fact.gate == GateCondition(topic="alibi", min_ask=1)


def test_migrate_drops_exclusion_lists_not_carried_over():
    """exclude_keywords/exclude_concepts are dropped by design (§5: replaced
    structurally by `subject`) — the migrated Fact has no such field at all,
    which is the point, not an oversight."""
    raw = _legacy_fact(OWEN_TWIN, "alibi")
    assert "exclude_concepts" in raw  # legacy data still has it
    fact = fact_from_legacy(raw, subject=SELF)
    assert not hasattr(fact, "exclude_concepts")
    assert not hasattr(fact, "exclude_keywords")


def test_migrate_raises_on_fact_with_neither_trigger_kind():
    with pytest.raises(ValueError):
        fact_from_legacy({"topic": "broken"}, subject=SELF)
