"""Layer 7 (ENGINE_SPEC §9.1-§9.4) — the combination-leak danger table and the
citation guard that enforces it.

The thing under test is not "does the model say a forbidden word". It is the
harder case the whole layer exists for: two claims that are each perfectly safe
to say, which together spell out the solution. The single-fact checks pass both
halves; only the pairwise table sees the combination.
"""

from fastapi.testclient import TestClient

import app.llm.dialogue_rewriter as rewriter_module
from app.case_store import get_case
from app.main import app
from app.danger_table import (
    MAX_SOURCE_CLAIMS,
    build_danger_table,
    load_danger_table,
    pair_key,
    places_someone,
    save_danger_table,
)
from app.llm.client import FakeLLMClient
from app.llm.dialogue_rewriter import (
    CitationContext,
    _build_concept_facets,
    _concept_combination_leak,
    _citation_leak,
    rewrite_interview_answer,
)
from app.models import Claim

CASE_IDS = [f"case_{i:03d}" for i in range(1, 8)]

client = TestClient(app)


def _claim(claim_id, text, *, time=None, loc=None, speaker="agent_clara"):
    return Claim(
        claim_id=claim_id,
        speaker_agent_id=speaker,
        claim_text=text,
        time_reference=time,
        location_reference_id=loc,
    )


def _ctx(claims, danger=None, required=False):
    return CitationContext(
        citable={c.claim_id: c for c in claims},
        danger=danger or {},
        required=required,
    )


# ---------------------------------------------------------------------------
# §9.1 — the offline table
# ---------------------------------------------------------------------------

def test_danger_table_finds_pairs_that_leak_only_in_combination():
    """The point of the table: each half is clean, the pair is not.

    A pair whose halves already trip the single-text scan would be caught by
    the existing checks anyway — recording it would only bury the pairs that
    are dangerous *only* together, which are the ones this layer is for.
    """
    case = get_case("case_001")
    table = build_danger_table(case)
    assert table, "case_001 should have at least one dangerous pair"

    facets = _build_concept_facets(case)
    by_id = {
        ac.claim_id: ac
        for pack in case.interview_packs
        for rule in pack.rules
        for ac in rule.claims
    }

    for (a_id, b_id), facet in table.items():
        a, b = by_id[a_id], by_id[b_id]
        assert _concept_combination_leak(a.summary.lower(), "", facets) is None
        assert _concept_combination_leak(b.summary.lower(), "", facets) is None
        combined = f"{a.summary} {b.summary}".lower()
        assert _concept_combination_leak(combined, "", facets) is not None
        assert facet


def test_danger_table_pairs_are_same_speaker_only():
    """Two people's claims do not combine into one person's inference."""
    for case_id in CASE_IDS:
        case = get_case(case_id)
        table = build_danger_table(case)
        speaker_of = {
            ac.claim_id: pack.agent_id
            for pack in case.interview_packs
            for rule in pack.rules
            for ac in rule.claims
        }
        for a_id, b_id in table:
            assert speaker_of[a_id] == speaker_of[b_id]


def test_committed_danger_tables_match_a_fresh_build():
    """The on-disk tables are content and go stale silently when claims change.

    Without this, editing an interview pack would leave the enforced table
    describing the previous version of the case — failing open on exactly the
    pair the edit introduced.
    """
    for case_id in CASE_IDS:
        on_disk = load_danger_table(case_id)
        assert on_disk is not None, f"{case_id} has no committed danger_table.json"
        assert on_disk == build_danger_table(get_case(case_id)), (
            f"{case_id}'s committed danger table is stale — rebuild it"
        )


def test_danger_table_round_trips_through_disk(tmp_path, monkeypatch):
    monkeypatch.setattr("app.case_store.DATA_DIR", tmp_path)
    (tmp_path / "gen_roundtrip").mkdir()
    table = {("claim_a", "claim_b"): "motive (2/4 concept groups)"}
    save_danger_table("gen_roundtrip", table)
    assert load_danger_table("gen_roundtrip") == table


def test_danger_table_follows_a_redirected_data_dir(tmp_path, monkeypatch):
    """The table must land wherever the case store is pointing right now.

    Snapshotting `DATA_DIR` at import time made this module deaf to the
    redirect every persistence test performs, so tables were written into the
    real `app/data/` during test runs — creating case directories that
    contained nothing but a danger table.
    """
    monkeypatch.setattr("app.case_store.DATA_DIR", tmp_path)
    (tmp_path / "gen_redirected").mkdir()
    save_danger_table("gen_redirected", {("a", "b"): "motive"})
    assert (tmp_path / "gen_redirected" / "danger_table.json").is_file()


def test_saving_a_table_never_conjures_a_case_directory(tmp_path, monkeypatch):
    """A danger table is an index into claims that live in interviews.json; on
    its own it means nothing, so no case dir means write nothing."""
    monkeypatch.setattr("app.case_store.DATA_DIR", tmp_path)
    save_danger_table("gen_no_such_case", {("a", "b"): "motive"})
    assert not (tmp_path / "gen_no_such_case").exists()


def test_danger_table_is_never_part_of_case_data():
    """Same firewall as solution.json, enforced structurally: the file is
    written beside the case but never read into CaseData, so no projection or
    endpoint can serialise it even by accident."""
    case = get_case("case_001")
    assert not hasattr(case, "danger_table")
    blob = case.model_dump_json()
    assert "danger_table" not in blob
    for (a, b) in build_danger_table(case):
        assert f'"{a}", "{b}"' not in blob


def test_danger_table_file_is_not_served_by_any_case_endpoint():
    """Belt and braces on the above: drive the real API and assert no response
    carries the table's contents."""
    table = build_danger_table(get_case("case_001"))
    assert table
    pair_ids = {cid for pair in table for cid in pair}

    for path in ("/api/case", "/api/agents", "/api/locations", "/api/clues", "/api/board"):
        r = client.get(path)
        if r.status_code != 200:
            continue
        body = r.text
        assert "danger_table" not in body
        # A claim id alone is not secret; the *pairing* is. Assert no response
        # ever exposes both halves of a recorded pair together.
        for a, b in table:
            assert not (a in body and b in body), f"{path} exposes dangerous pair {a}+{b}"
    assert pair_ids


# ---------------------------------------------------------------------------
# §9.2 — runtime lookup
# ---------------------------------------------------------------------------

def test_citation_of_a_recorded_dangerous_pair_is_rejected():
    a, b = _claim("c_a", "The ledger was nothing to do with me."), _claim("c_b", "Marcus kept checking the till.")
    danger = {pair_key("c_a", "c_b"): "motive (2/4 concept groups)"}
    reason = _citation_leak(["c_a", "c_b"], _ctx([a, b], danger))
    assert reason and "motive" in reason


def test_citation_order_does_not_matter():
    danger = {pair_key("c_a", "c_b"): "motive (2/4 concept groups)"}
    claims = [_claim("c_a", "one"), _claim("c_b", "two")]
    assert _citation_leak(["c_a", "c_b"], _ctx(claims, danger))
    assert _citation_leak(["c_b", "c_a"], _ctx(claims, danger))


def test_safe_pair_passes():
    claims = [_claim("c_a", "one"), _claim("c_b", "two")]
    assert _citation_leak(["c_a", "c_b"], _ctx(claims, {})) is None


def test_single_citation_is_never_a_combination():
    claims = [_claim("c_a", "one"), _claim("c_b", "two")]
    danger = {pair_key("c_a", "c_b"): "motive"}
    assert _citation_leak(["c_a"], _ctx(claims, danger)) is None


def test_unknown_claim_id_is_rejected():
    """A cited claim that was never offered is fabricated, and no table entry
    could vouch for it either way."""
    reason = _citation_leak(["c_a", "ghost"], _ctx([_claim("c_a", "one")]))
    assert reason and "ghost" in reason


def test_duplicate_citation_collapses_to_one_source():
    claims = [_claim("c_a", "one")]
    assert _citation_leak(["c_a", "c_a", " c_a "], _ctx(claims)) is None


# ---------------------------------------------------------------------------
# §9.3 — backstops
# ---------------------------------------------------------------------------

def test_citation_cap_is_two():
    claims = [_claim(f"c_{i}", str(i)) for i in range(3)]
    reason = _citation_leak(["c_0", "c_1", "c_2"], _ctx(claims))
    assert reason and f"cap {MAX_SOURCE_CLAIMS}" in reason


def test_a_missing_citation_fails_closed_when_reasoning_was_offered():
    """Superseded the original form of this test, which asserted that `[]` also
    failed closed. It does not any more, and the change is deliberate: `None`
    (field absent — the model said nothing about its sources) is the case §9.3
    was written for, while `[]` is the model answering "I drew on none of
    them". Collapsing them rejected the only models that answer honestly."""
    claims = [_claim("c_a", "one"), _claim("c_b", "two")]

    assert _citation_leak(None, _ctx(claims, required=True)) is not None
    # A list of blanks is not an answer either — it decodes to no ids at all
    # while looking like one, so it is graded as the empty answer it is.
    assert _citation_leak([""], _ctx(claims, required=True)) is None


def test_empty_citation_is_fine_when_nothing_was_offered_to_cite():
    """The plain flavour rewrite is handed no claim history and asked for no
    citation; silence there means nothing and must not cost the player their
    in-character dialogue."""
    claims = [_claim("c_a", "one"), _claim("c_b", "two")]
    assert _citation_leak([], _ctx(claims, required=False)) is None


def test_text_scan_still_rejects_an_uncited_paraphrase(monkeypatch):
    """§9.3's parallel backstop: an honest-looking single citation does not buy
    a pass for prose that paraphrases the answer key anyway."""
    case = get_case("case_001")
    clara = next(a for a in case.agents if a.agent_id == "agent_clara")

    monkeypatch.setattr(
        rewriter_module,
        "get_llm_client",
        lambda: FakeLLMClient(override_response={
            "rewritten_text": "I took money from the till, and I stole it to pay for things.",
            "source_claim_ids": ["claim_clara_fountain_alibi"],
        }),
    )
    result = rewrite_interview_answer(
        case=case,
        agent=clara,
        question_text="Where were you?",
        deterministic_text="I was at the fountain.",
        allowed_facts=["I was at the fountain."],
        pressure_level=0.2,
        claim_history=[_claim("claim_clara_fountain_alibi", "I was at the fountain.")],
    )
    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"
    assert result.rewritten_text == "I was at the fountain."
    assert result.source_claim_ids == []


# ---------------------------------------------------------------------------
# §9.4 — the scope carve-out
# ---------------------------------------------------------------------------

def test_two_time_location_claims_are_refused_as_layer_6_scope():
    """Narrowing identity by time and place is testimony.py's question, settled
    deterministically. Layer 7 never gets a second, softer opinion on it —
    including when the pair is not in the danger table at all."""
    a = _claim("c_a", "I was at the fountain.", time="07:50", loc="loc_fountain")
    b = _claim("c_b", "I was in the alley.", time="07:55", loc="loc_alley")
    reason = _citation_leak(["c_a", "c_b"], _ctx([a, b], {}))
    assert reason and "Layer 6" in reason


def test_one_time_location_claim_paired_with_another_kind_is_in_scope():
    a = _claim("c_a", "I was at the fountain.", time="07:50", loc="loc_fountain")
    b = _claim("c_b", "Marcus and I got on fine.")
    assert _citation_leak(["c_a", "c_b"], _ctx([a, b], {})) is None


def test_time_location_pairs_never_enter_the_danger_table():
    for case_id in CASE_IDS:
        case = get_case(case_id)
        by_id = {
            ac.claim_id: ac
            for pack in case.interview_packs
            for rule in pack.rules
            for ac in rule.claims
        }
        for a_id, b_id in build_danger_table(case):
            assert not (places_someone(by_id[a_id]) and places_someone(by_id[b_id]))


def test_places_someone_agrees_across_claim_types():
    """The table is built from authored AnswerClaims and enforced against
    session Claims; the carve-out must answer the same for both."""
    case = get_case("case_001")
    authored = {
        ac.claim_id: ac
        for pack in case.interview_packs
        for rule in pack.rules
        for ac in rule.claims
    }
    for cid, ac in authored.items():
        session_claim = _claim(
            cid, ac.summary, time=ac.time_reference, loc=ac.location_reference_id
        )
        assert places_someone(ac) == places_someone(session_claim)


# ---------------------------------------------------------------------------
# Default-off: the deterministic floor is unchanged
# ---------------------------------------------------------------------------

def test_layer_7_is_off_by_default():
    from app.llm.config import get_llm_config

    assert get_llm_config().claim_reasoning_enabled is False


def test_saving_unrelated_settings_does_not_switch_layer_7_off(monkeypatch):
    """The Settings modal has no Layer 7 control, so it posts no such field.
    An omitted flag must mean "unchanged" — a leak guard that silently disables
    itself when the operator renames a model is worse than one never enabled."""
    from app.llm.config import SavedLLMSettings

    saved = SavedLLMSettings(
        provider="openai_compatible",
        base_url="http://127.0.0.1:11434/v1",
        model="before",
        dialogue_enabled=True,
        claim_reasoning_enabled=True,
    )
    written: dict = {}
    monkeypatch.setattr("app.llm.config.load_saved_settings", lambda: saved)
    monkeypatch.setattr("app.llm.config.save_settings", lambda s: written.update(s.model_dump()))

    r = client.put("/api/llm-settings", json={
        "provider": "openai_compatible",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "after",
        "dialogue_enabled": True,
    })
    assert r.status_code == 200
    assert written["model"] == "after"
    assert written["claim_reasoning_enabled"] is True


def test_rewrite_without_claim_history_never_requires_a_citation(monkeypatch):
    """The shape of every existing caller: no claim history, a model that has
    never heard of source_claim_ids, and dialogue that must still come back."""
    case = get_case("case_001")
    clara = next(a for a in case.agents if a.agent_id == "agent_clara")
    monkeypatch.setattr(
        rewriter_module,
        "get_llm_client",
        lambda: FakeLLMClient(override_response={"rewritten_text": "I was by the fountain, as I said."}),
    )
    result = rewrite_interview_answer(
        case=case,
        agent=clara,
        question_text="Where were you?",
        deterministic_text="I was at the fountain.",
        allowed_facts=["I was at the fountain."],
        pressure_level=0.2,
    )
    assert result.fallback_used is False
    assert result.rewritten_text == "I was by the fountain, as I said."


def test_dangerous_pair_is_rejected_end_to_end(monkeypatch):
    """The whole path: a real recorded pair from case_001, cited by the model,
    refused by the sanitiser, degraded to the deterministic line."""
    case = get_case("case_001")
    clara = next(a for a in case.agents if a.agent_id == "agent_clara")
    table = build_danger_table(case)
    (a_id, b_id) = next(iter(table))

    by_id = {
        ac.claim_id: ac
        for pack in case.interview_packs
        for rule in pack.rules
        for ac in rule.claims
    }
    history = [
        _claim(cid, by_id[cid].summary,
               time=by_id[cid].time_reference, loc=by_id[cid].location_reference_id)
        for cid in (a_id, b_id)
    ]

    monkeypatch.setattr(
        rewriter_module,
        "get_llm_client",
        lambda: FakeLLMClient(override_response={
            "rewritten_text": "You keep circling the same two things, detective.",
            "source_claim_ids": [a_id, b_id],
        }),
    )
    result = rewrite_interview_answer(
        case=case,
        agent=clara,
        question_text="Isn't it odd, those two things together?",
        deterministic_text="I've nothing more to add.",
        allowed_facts=[],
        pressure_level=0.4,
        claim_history=history,
    )
    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"
    assert result.rewritten_text == "I've nothing more to add."


def _reasoning_config(**overrides):
    from app.llm.config import LLMConfig

    base = dict(
        provider="fake", base_url=None, api_key=None, model=None, timeout_seconds=60,
        configured=True, fallback_reason=None, dialogue_enabled=True,
        claim_reasoning_enabled=True,
    )
    base.update(overrides)
    return lambda: LLMConfig(**base)


def _ask_clara(monkeypatch, *, config, captured):
    """Drive the real interview engine and capture what it handed the rewriter."""
    import app.interview as interview_module
    from app.models import AskRequest
    from app.session import get_session

    case = get_case("case_001")
    monkeypatch.setattr(interview_module, "get_llm_config", config)

    def spy(**kwargs):
        captured.update(kwargs)
        return rewriter_module.RewriteResult(
            rewritten_text="Captured.", fallback_used=False
        )

    monkeypatch.setattr(interview_module, "rewrite_interview_answer", spy)
    session = get_session("case_001")
    return interview_module.answer_question(
        case, session, AskRequest(agent_id="agent_clara", question_type="alibi")
    )


def test_interview_supplies_the_agents_claim_history_when_reasoning_is_on(monkeypatch):
    """interview.py's half of Layer 7: the model is handed this agent's whole
    recorded claim store, not just the current turn's claim."""
    captured: dict = {}
    _ask_clara(monkeypatch, config=_reasoning_config(), captured=captured)

    history = captured.get("claim_history")
    assert history, "claim reasoning is on and the answer carried claims"
    assert all(c.speaker_agent_id == "agent_clara" for c in history), (
        "another suspect's claims are not this agent's to reason from"
    )


def test_interview_withholds_claim_history_when_reasoning_is_off(monkeypatch):
    """Default build: identical call shape to before Layer 7 existed."""
    captured: dict = {}
    _ask_clara(
        monkeypatch,
        config=_reasoning_config(claim_reasoning_enabled=False),
        captured=captured,
    )
    assert captured.get("claim_history") is None


def test_honest_single_citation_survives_the_whole_path(monkeypatch):
    case = get_case("case_001")
    clara = next(a for a in case.agents if a.agent_id == "agent_clara")
    monkeypatch.setattr(
        rewriter_module,
        "get_llm_client",
        lambda: FakeLLMClient(override_response={
            "rewritten_text": "I already told you where I was.",
            "source_claim_ids": ["claim_clara_fountain_alibi"],
        }),
    )
    result = rewrite_interview_answer(
        case=case,
        agent=clara,
        question_text="Where were you?",
        deterministic_text="I was at the fountain.",
        allowed_facts=["I was at the fountain."],
        pressure_level=0.2,
        claim_history=[_claim("claim_clara_fountain_alibi", "I was at the fountain.")],
    )
    assert result.fallback_used is False
    assert result.source_claim_ids == ["claim_clara_fountain_alibi"]


# ---------------------------------------------------------------------------
# An honest "I used none of them" is not silence
# ---------------------------------------------------------------------------
# The original schema defaulted a missing field to [], so the two were the same
# value and both were refused. Measured against real models, that punished the
# only one answering accurately: gemma4:latest cites the right claim 4/4 when
# the answer rests on one and returns [] 4/4 when it does not, while
# llama3.1:8b names every claim it was shown regardless of use. The naive rule
# rejected the honest model and passed the indiscriminate one.

def test_an_absent_citation_is_still_refused():
    """§9.3 unchanged for the case it was written for: the model said nothing
    about its sources at all."""
    ctx = CitationContext(citable={"claim_a": _claim("claim_a", "I was in early.")},
                          danger={}, required=True)

    assert _citation_leak(None, ctx) == "claim-grounded rewrite declared no sources"


def test_an_explicit_empty_list_is_an_honest_answer():
    """Most rewrites restate a single grounded line and rest on no prior claim.
    Saying so is correct, and must not be treated as evasion."""
    ctx = CitationContext(citable={"claim_a": _claim("claim_a", "I was in early.")},
                          danger={}, required=True)

    assert _citation_leak([], ctx) is None


def test_an_empty_citation_still_has_the_text_scan_behind_it():
    """Allowing [] is only safe because check 4b reads the prose independently
    — a model that combines two claims without declaring it is caught on its
    words. This pins that 4b is not gated on the citation."""
    from app import case_store
    from app.llm.dialogue_rewriter import _sanitise, _build_concept_facets

    case = case_store.get_case("case_001")
    facets = _build_concept_facets(case)
    motive_words = [g[0] for g in case.solution.motive.concept_groups][
        : case.solution.motive.min_groups
    ]
    leaky = " ".join(motive_words)

    reason = _sanitise(
        leaky, forbidden_facts=[], allowed_facts=[], case=case,
        allowed_context=["nothing relevant"], concept_facets=facets,
        source_claim_ids=[],
        citation=CitationContext(citable={}, danger={}, required=True),
    )

    assert reason is not None, "an undeclared combination slipped through on an empty citation"


def test_absent_is_fine_when_no_history_was_offered():
    """Layer 7 off: the model was shown nothing, so it has nothing to declare."""
    ctx = CitationContext(citable={}, danger={}, required=False)

    assert _citation_leak(None, ctx) is None
