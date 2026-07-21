"""Every shipped case must give the behavioural layer something to work with.

The engine (tells, composure meter, portrait swap, baseline memory) is only as
good as the arcs the case data affords. These tests encode the authoring
contract from docs/17_behavioural_authoring_guide.md:

  * every living principal can be asked something calm — the baseline capture path;
  * the killer has a route to the cracking portrait (>= 0.7 cumulative) and a
    confession (contradiction_locked) to end it;
  * anyone the case invites you to challenge either has a route that visibly moves
    the meter (>= 0.35, the Rattled band) or a resolution beat
    (reveal_innocent_secret / reframe / a relief delta) — a challenge that does
    nothing teaches the player to stop challenging;
  * no principal is missing a portrait state, so the swap never silently fails;
  * authored baselines describe visible behaviour, never guilt.
"""

import pytest

from app.case_store import get_case

CASE_IDS = [f"case_{n:03d}" for n in range(1, 8)]

FORBIDDEN_WORDS = {"lie", "lying", "liar", "false", "guilty", "killer", "murderer"}

# Outcomes that move the story even without pressure: relief beats, reframes,
# and admissions (which surface new testimony the player can use elsewhere).
RESOLUTION_OUTCOMES = {"reveal_innocent_secret", "reframe", "partial_admission", "contradiction_locked"}


def _principals(case):
    return [a for a in case.agents if not a.is_background]


def _living_principals(case):
    return [a for a in _principals(case) if a.agent_id != case.case.victim_id]


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_living_principal_has_a_baseline_capture_path(case_id):
    """Baseline memory banks on a suspect's first unpressured answer, so every
    living principal needs an interview pack to answer from."""
    case = get_case(case_id)
    packs = {p.agent_id for p in case.interview_packs}
    for agent in _living_principals(case):
        assert agent.agent_id in packs, f"{case_id}: {agent.agent_id} cannot be interviewed"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_killer_can_be_walked_to_cracking_and_confession(case_id):
    case = get_case(case_id)
    killer = case.solution.killer_id
    rules = [r for r in case.challenge_rules if r.target_agent_id == killer]
    positive = sum(r.pressure_delta for r in rules if r.pressure_delta > 0)
    assert positive >= 0.7, (
        f"{case_id}: killer {killer} can only accumulate {positive:.2f} pressure — "
        "the cracking portrait (0.7) is unreachable"
    )
    assert any(r.outcome == "contradiction_locked" for r in rules), (
        f"{case_id}: killer {killer} has no confession (contradiction_locked) rule"
    )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_challenged_suspect_has_a_route_that_goes_somewhere(case_id):
    """A medium-pressure route, or a resolution beat. Never a dead challenge tree."""
    case = get_case(case_id)
    by_agent: dict[str, list] = {}
    for r in case.challenge_rules:
        by_agent.setdefault(r.target_agent_id, []).append(r)
    for agent_id, rules in by_agent.items():
        positive = sum(r.pressure_delta for r in rules if r.pressure_delta > 0)
        has_resolution = any(
            r.outcome in RESOLUTION_OUTCOMES or r.pressure_delta < 0 for r in rules
        )
        assert positive >= 0.35 or has_resolution, (
            f"{case_id}: challenging {agent_id} can neither rattle them "
            f"(max +{positive:.2f}) nor resolve anything — the route is a dead end"
        )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_no_principal_is_missing_a_portrait_state(case_id):
    """The portrait swap fails silently (falls back to calm) when a state is
    missing — case_007 shipped that way. Never again."""
    case = get_case(case_id)
    for agent in _principals(case):
        art = agent.portrait_art
        assert art is not None, f"{case_id}: {agent.agent_id} has no portrait art"
        needed = ["calm", "defensive", "cracking"]
        if agent.agent_id == case.case.victim_id:
            needed.append("deceased")
        for state in needed:
            assert getattr(art, state, None), (
                f"{case_id}: {agent.agent_id} is missing the {state!r} portrait"
            )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_authored_baselines_describe_behaviour_not_guilt(case_id):
    case = get_case(case_id)
    for agent in _principals(case):
        spec = agent.baseline
        if spec is None:
            continue
        for text in (spec.habit_text, spec.deviation_cue):
            assert text.strip(), f"{case_id}: {agent.agent_id} baseline has empty text"
            words = text.lower().replace(".", " ").replace(",", " ").split()
            for word in FORBIDDEN_WORDS:
                assert word not in words, (
                    f"{case_id}: {agent.agent_id} baseline leaks the word {word!r}"
                )
        # Habit completes "at ease, {habit_text}": present tense, lowercase start.
        assert spec.habit_text[0].islower(), (
            f"{case_id}: {agent.agent_id} habit_text should complete 'at ease, …'"
        )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_principals_have_distinct_authored_manners(case_id):
    """Marcus (case_007) is the model arc; every case's principals are held to
    the same bar. Distinct means distinct texts — two agents may share a
    category, never a manner. A recurring villager may keep their manner across
    cases (same person, same habit); within one case every manner is unique."""
    case = get_case(case_id)
    specs = {a.agent_id: a.baseline for a in _living_principals(case)}
    missing = [aid for aid, s in specs.items() if s is None]
    assert not missing, f"{case_id}: no authored baseline for {missing}"
    habits = [s.habit_text for s in specs.values()]
    cues = [s.deviation_cue for s in specs.values()]
    assert len(set(habits)) == len(habits), f"{case_id}: duplicated habit_text"
    assert len(set(cues)) == len(cues), f"{case_id}: duplicated deviation_cue"
