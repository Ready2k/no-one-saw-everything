"""Latency work that must not cost the player anything real.

Two mechanisms, one shared requirement: neither may change what a suspect says
or what the player can infer from how they said it.

Stall fillers cover generation latency with speech. The trap they must avoid is
specific to this game — hesitation is *evidence* here (`Agent.baseline`, the
pressure bands, `observable_tells`), so a stall that reads as evasion, or that
varies as the interview heats up, manufactures a tell out of GPU load. That is
worse than a spinner, which is at least honestly outside the fiction.

Prefetch pays for the next turn early. It runs the real engine against a *copy*
of the session, so its mutations are discarded, and it can only ever populate a
cache keyed on the complete turn — meaning a wrong guess costs a model call and
a right guess is invisible.
"""

import copy

import pytest
from fastapi.testclient import TestClient

from app import prefetch
from app.case_store import get_case
from app.dialogue_processor import (
    ALL_CANNED_DEFLECTIONS,
    ALL_STALL_FILLERS,
    stall_fillers_for,
)
from app.llm import rewrite_cache
from app.main import app
from app.models import AskRequest
from app.projections import project_agent
from app.session import get_session

client = TestClient(app)
CASE_IDS = [f"case_{i:03d}" for i in range(1, 8)]


@pytest.fixture(autouse=True)
def _clean():
    rewrite_cache.reset_rewrite_cache()
    prefetch.reset()
    yield
    rewrite_cache.reset_rewrite_cache()
    prefetch.reset()


# ---------------------------------------------------------------------------
# Stall fillers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_speaking_character_has_something_to_stall_with(case_id):
    case = get_case(case_id)
    for agent in case.agents:
        if agent.is_background or agent.is_victim:
            continue
        assert stall_fillers_for(agent), f"{agent.agent_id} would stall in silence"


def test_a_stall_is_never_a_deflection():
    """The load-bearing rule. "I'd rather not elaborate" is a refusal and reads
    as guilt; a stall must read as nothing at all, because the player is taught
    to interpret evasion and cannot know the model was simply slow."""
    overlap = ALL_STALL_FILLERS & ALL_CANNED_DEFLECTIONS

    assert not overlap, f"these double as refusals and would read as tells: {overlap}"


def test_a_stall_cannot_vary_with_pressure():
    """Enforced structurally rather than by convention: the function takes the
    agent and nothing else, so there is no channel through which the interview's
    temperature could leak into how a suspect hesitates."""
    import inspect

    params = list(inspect.signature(stall_fillers_for).parameters)

    assert params == ["agent"], f"a stall filler must depend on nothing but the agent, got {params}"


def test_stalls_are_stable_for_the_same_agent():
    case = get_case("case_001")
    agent = next(a for a in case.agents if not a.is_background and not a.is_victim)

    assert stall_fillers_for(agent) == stall_fillers_for(agent)


def test_stall_fillers_carry_no_case_content():
    """They are shipped to the client before a single clue is found, so they
    must not name anyone or anything in the case."""
    for case_id in CASE_IDS:
        case = get_case(case_id)
        names = {a.full_name.split()[0].lower() for a in case.agents}
        names |= {loc.name.lower() for loc in case.locations}
        for line in ALL_STALL_FILLERS:
            lowered = line.lower()
            for name in names:
                assert name not in lowered, f"{line!r} names {name!r} from {case_id}"


def test_the_client_is_given_stalls_with_the_agent():
    """Sent up front so playing one costs no round trip — the whole point is
    that it appears the instant the question is clicked."""
    case = get_case("case_001")
    agent = next(a for a in case.agents if not a.is_background and not a.is_victim)

    projected = project_agent(agent)

    assert projected["stall_fillers"]
    assert all(isinstance(line, str) and line.strip() for line in projected["stall_fillers"])


def test_stalls_survive_the_api_boundary():
    response = client.get("/api/agents")

    assert response.status_code == 200
    speaking = [a for a in response.json() if not a["is_background"] and not a["is_victim"]]
    assert speaking
    assert all(a["stall_fillers"] for a in speaking)


# ---------------------------------------------------------------------------
# The rewrite cache
# ---------------------------------------------------------------------------

def test_identical_turns_share_an_answer():
    key = rewrite_cache.make_key(agent_id="agent_clara", question_text="Where were you?")

    assert key == rewrite_cache.make_key(question_text="Where were you?", agent_id="agent_clara"), \
        "key must not depend on argument order"


@pytest.mark.parametrize("changed", [
    {"pressure_level": 3},
    {"is_repeat": True},
    {"emotion": "defensive"},
    {"deterministic_text": "Something else entirely."},
    {"model": ("openai_compatible", "http://host/v1", "other-model", False)},
    {"claim_history": ["claim_a"]},
])
def test_anything_that_could_change_the_answer_changes_the_key(changed):
    """The cache's one safety property: a hit is impossible unless the whole
    turn matches, so it can move latency and never content."""
    base = dict(
        agent_id="agent_clara", question_text="Where were you?",
        deterministic_text="I was in early.", pressure_level=1, is_repeat=False,
        emotion="neutral", claim_history=[],
        model=("openai_compatible", "http://host/v1", "gemma4:latest", False),
    )

    assert rewrite_cache.make_key(**base) != rewrite_cache.make_key(**{**base, **changed})


def test_a_stored_result_comes_back():
    key = rewrite_cache.make_key(x=1)
    rewrite_cache.put(key, "an answer")

    assert rewrite_cache.get(key) == "an answer"
    assert rewrite_cache.get(rewrite_cache.make_key(x=2)) is None


def test_the_cache_is_bounded():
    """It lives for the life of the process and a long interrogation touches
    many distinct turns."""
    for i in range(rewrite_cache.MAX_ENTRIES + 50):
        rewrite_cache.put(rewrite_cache.make_key(i=i), i)

    assert rewrite_cache.stats()["size"] <= rewrite_cache.MAX_ENTRIES


def test_reset_clears_it():
    rewrite_cache.put(rewrite_cache.make_key(x=1), "v")
    rewrite_cache.reset_rewrite_cache()

    assert rewrite_cache.stats()["size"] == 0


def test_a_session_reset_does_not_inherit_the_last_run_s_dialogue():
    rewrite_cache.put(rewrite_cache.make_key(x=1), "stale line")
    client.post("/api/session/reset")

    assert rewrite_cache.stats()["size"] == 0


# ---------------------------------------------------------------------------
# Prefetch
# ---------------------------------------------------------------------------

def test_prefetch_never_touches_the_real_session():
    """The reason it runs against a copy. Answering mutates claims, revealed
    clues, transcripts and ask counts; a warmer that leaked any of that would
    hand the player evidence they never asked for."""
    prefetch.set_enabled(True)
    client.post("/api/session/reset")
    case = get_case("case_001")
    session = get_session("case_001")

    before = copy.deepcopy(
        (dict(session.claims), set(session.discovered_clue_ids), len(session.transcripts))
    )
    prefetch.warm_agent(case, session, "agent_clara")
    prefetch.wait_idle(timeout=15)

    after = (dict(session.claims), set(session.discovered_clue_ids), len(session.transcripts))
    assert after[0].keys() == before[0].keys(), "prefetch recorded a claim in the real session"
    assert after[1] == before[1], "prefetch revealed a clue in the real session"
    assert after[2] == before[2], "prefetch opened a transcript in the real session"


def test_prefetch_is_skipped_when_there_is_nothing_to_gain(monkeypatch):
    """With no LLM configured the answer is already deterministic and instant;
    spending threads to pre-compute it would be pure waste."""
    from app.llm.config import LLMConfig

    monkeypatch.setattr(
        "app.llm.config.get_llm_config",
        lambda: LLMConfig(provider="fake", base_url=None, api_key=None, model=None,
                          timeout_seconds=60, configured=True, fallback_reason=None,
                          dialogue_enabled=False),
    )
    case = get_case("case_001")
    session = get_session("case_001")

    assert prefetch.warm_agent(case, session, "agent_clara") == 0


def test_a_degraded_session_is_not_prefetched(monkeypatch):
    """Once the session has dropped to the written script every turn is instant,
    so warming would queue model calls whose results can never be used."""
    from app.llm.config import LLMConfig

    monkeypatch.setattr(
        "app.llm.config.get_llm_config",
        lambda: LLMConfig(provider="openai_compatible", base_url="http://h/v1", api_key=None,
                          model="m", timeout_seconds=60, configured=True,
                          fallback_reason=None, dialogue_enabled=True),
    )
    case = get_case("case_001")
    session = get_session("case_001")
    session.llm_unavailable = True
    try:
        assert prefetch.warm_agent(case, session, "agent_clara") == 0
    finally:
        session.llm_unavailable = False


def test_prefetch_does_not_re_warm_what_was_just_asked():
    """The player has the answer on screen; generating it again is the one
    prediction guaranteed to be wrong."""
    from app.llm.config import LLMConfig
    import app.llm.config as config_module

    original = config_module.get_llm_config
    config_module.get_llm_config = lambda: LLMConfig(
        provider="openai_compatible", base_url="http://unreachable.invalid/v1", api_key=None,
        model="m", timeout_seconds=1, configured=True, fallback_reason=None,
        dialogue_enabled=True)
    try:
        case = get_case("case_001")
        session = get_session("case_001")
        scheduled = prefetch.warm_agent(case, session, "agent_clara", just_asked="alibi")
    finally:
        config_module.get_llm_config = original
        prefetch.wait_idle(timeout=15)

    assert scheduled == len(prefetch.PREFETCHABLE_QUESTION_TYPES) - 1


def test_the_answer_is_identical_whether_or_not_it_was_prefetched():
    """The property that makes this safe to leave on. Prefetch is allowed to
    change when the words are computed, never which words they are.

    `session_seed` is pinned across both runs because it is minted fresh on
    every reset and drives the replay-variety pools — without pinning it, this
    compares two different (legitimately) worded answers and fails for a reason
    that has nothing to do with prefetch.
    """
    def ask_once(warm_first: bool) -> str:
        client.post("/api/session/reset")
        session = get_session("case_001")
        session.session_seed = "pinned-seed"
        if warm_first:
            prefetch.warm_agent(get_case("case_001"), session, "agent_clara")
            prefetch.wait_idle(timeout=20)
        return client.post(
            "/api/interview/ask",
            json={"agent_id": "agent_clara", "question_type": "alibi"},
        ).json()["answer_text"]

    prefetch.set_enabled(False)
    cold = ask_once(warm_first=False)
    prefetch.set_enabled(True)
    warm = ask_once(warm_first=True)

    assert warm == cold
