"""Guards for the LLM-authored timeline phase (timeline_compiler.py).

Before this feature every generated case replayed case_001's 29 template events
verbatim (only names/one-location/clock-offset swapped), so the Rewind and the
per-agent Routines were always identical. These tests lock in that a generated
case now gets a *freshly compiled* morning and fresh routines, that the compiled
timeline is fair (valid) by construction, and that it never leaks the truth.

The default test LLM provider is `fake`, whose FakeLLMClient returns FAKE_TIMELINE
(app/llm/client.py) — so `mode="llm_assisted"` exercises the real compiler with
no network.
"""

import json
from pathlib import Path

from app.generator import generate_case
from app.validator import validate_case
from app.projections import project_event
from app.models import CaseData


def _gen(seed: int) -> CaseData:
    case, fallback_used, reason, _ = generate_case(
        "blackmail", "standard", seed, mode="llm_assisted", fallback_allowed=True
    )
    assert fallback_used is False, f"unexpected fallback ({reason}) — timeline path not exercised"
    return case


def _template_events() -> list[dict]:
    path = Path(__file__).parent.parent / "app/data/templates/blackmail.json"
    return json.load(open(path))["events"]


def test_ambient_layer_is_regenerated():
    """The regression test the original bug lacked: a generated case gains a
    fresh ambient layer (`ev_gen_amb_*`), and its overall morning no longer
    matches the template's fixed event set beat-for-beat."""
    case = _gen(16481)
    ids = [e.event_id for e in case.events]
    assert any(i.startswith("ev_gen_amb_") for i in ids), "no fresh ambient beats were injected"
    # The template's public ambient routine events (no clue) should be gone.
    template_ambient = {
        e["event_id"] for e in _template_events()
        if not e.get("linked_clue_ids") and e.get("event_type") in {"routine", "movement", "arrival", "departure"}
        and e.get("visibility", "public") in {"public", "public_partial"}
    }
    # after a random time-shift the template ids are still the ids on kept
    # events, but every *ambient* one must have been dropped.
    assert not (set(ids) & template_ambient)


def test_clue_events_keep_coherent_timing():
    """Clue-bearing events are the kept puzzle spine, never the re-timed ambient
    layer — so a murder-window clue (e.g. the sound of the murder) can never
    drift to before the murder. Every event a clue points at must exist and not
    be a synthesised ambient beat."""
    case = _gen(16481)
    event_ids = {e.event_id for e in case.events}
    for clue in case.clues:
        for eid in clue.linked_event_ids:
            assert eid in event_ids, (clue.clue_id, eid)
            assert not eid.startswith("ev_gen_amb_"), (clue.clue_id, eid)


def test_generated_timeline_is_valid_and_murder_hidden():
    """Every fairness invariant the compiler promises holds, across seeds."""
    for seed in (16481, 20002, 33333, 40404):
        case = _gen(seed)
        result = validate_case(case)
        assert result["valid"], (seed, result["errors"])

        murders = [e for e in case.events if e.event_type == "murder"]
        assert len(murders) == 1
        assert murders[0].visibility == "hidden"
        assert murders[0].time == case.case.time_of_death
        # No agent in two places at one minute.
        seen: dict[tuple[str, str], str] = {}
        for e in case.events:
            for aid in e.agent_ids:
                key = (aid, e.time)
                assert seen.get(key, e.location_id) == e.location_id, (seed, key)
                seen[key] = e.location_id


def test_generated_timeline_varies_between_cases():
    """Two different seeds produce structurally different mornings (not just
    renamed) — different event counts or different (time, location) beat sets."""
    a, b = _gen(16481), _gen(70707)
    sig_a = sorted((e.time, e.location_id, e.event_type) for e in a.events)
    sig_b = sorted((e.time, e.location_id, e.event_type) for e in b.events)
    assert sig_a != sig_b


def test_routines_are_regenerated():
    """Per-agent routine_summary comes from the LLM plan, not the template."""
    template_routines = {
        a["routine_summary"]
        for a in json.load(open(Path(__file__).parent.parent / "app/data/templates/blackmail.json"))["agents"]
    }
    case = _gen(16481)
    regenerated = [a.routine_summary for a in case.agents if a.routine_summary]
    assert regenerated
    # At least most routines differ from every template routine string.
    fresh = [r for r in regenerated if r not in template_routines]
    assert len(fresh) >= len(regenerated) // 2


def test_generated_timeline_does_not_leak_truth():
    """The player-facing projection of the compiled timeline never exposes the
    murder event or the killer's identity as the culprit."""
    case = _gen(16481)
    killer = next(a for a in case.agents if a.agent_id == case.case.killer_id)

    # Project each event to its player-visible form (hidden/undiscovered → None).
    public_texts: list[str] = []
    for e in case.events:
        projected = project_event(e)
        if projected is None:
            continue  # hidden/undiscovered — correctly withheld
        for val in projected.values():
            if isinstance(val, str):
                public_texts.append(val.lower())
    blob = " ".join(public_texts)

    # The murder event's own truth text must not be in any public projection.
    assert "is killed" not in blob
    # No public text should brand the killer as the murderer.
    assert f"{killer.full_name.lower()}" not in blob or "killer" not in blob
    assert "murderer" not in blob
