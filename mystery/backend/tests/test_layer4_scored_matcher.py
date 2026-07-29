"""Layer 4 (ENGINE_SPEC §6, §14.1) — the scored hybrid matcher.

`classify_question` used to `return` from the first rule that matched anything,
so the earliest rule won regardless of how little of the question it explained:
a four-letter "know" beat a named piece of evidence, and the only available
remedy was another hand-written guard. Rules now compete on how much of the
question they account for, with precision-literal performatives ("I accuse
you") overriding the scoring outright per §5.3.

These tests are the standing regression suite §12 requires — every category
that was found to break something, asserted rather than assumed.
"""

import pytest

from app.case_store import get_case, set_active_start_time
from app.question_classifier import _coverage, classify_question
from app.session import Session

CASE_IDS = [f"case_{i:03d}" for i in range(1, 8)]


@pytest.fixture(autouse=True)
def _case_clock():
    case = get_case("case_001")
    set_active_start_time(case.case.sim_start_time)


def _intent(question, case_id="case_001", agent_id="agent_clara", discovered=True):
    case = get_case(case_id)
    set_active_start_time(case.case.sim_start_time)
    session = Session(case_id=case_id)
    if discovered:
        session.discovered_clue_ids = {c.clue_id for c in case.clues}
    result = classify_question(question, case, session, agent_id=agent_id)
    return result.intent if result else None


# ---------------------------------------------------------------------------
# §14.1 — the failure this change exists to fix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "did the till weight belong to him as far as you know?",
    "what do you know about him and the ledger page?",
    "do you trust what he said about the till weight?",
    "did you know about the blue coat?",
    "tell me what you know about the fountain",
    "I know you were in the storage room",
])
def test_a_named_entity_beats_an_incidental_generic_phrase(question):
    """The measured bug: `RELATIONSHIP_PHRASES` contains the bare word "know",
    and sat ahead of the entity rules, so four characters of politeness
    discarded a resolved object/location."""
    assert _intent(question) in {"object", "evidence", "location"}


def test_the_exact_pair_from_the_spec():
    """Adding "as far as you know" must not change what the question is about."""
    assert _intent("did the till weight belong to him?") == "object"
    assert _intent("did the till weight belong to him as far as you know?") == "object"


@pytest.mark.parametrize("question", [
    "did you know him well?",
    "were you close to him?",
    "did you trust him?",
    "what was your relationship with Marcus?",
    "you two didn't exactly get along, did you?",
])
def test_a_real_relationship_question_is_still_a_relationship_question(question):
    """The fix must not overshoot: with no competing entity, the generic
    trigger is the whole substance of the question and should still win."""
    assert _intent(question) == "relationship"


# ---------------------------------------------------------------------------
# §5.3 — precision-literal overrides
# ---------------------------------------------------------------------------

def test_an_accusation_outranks_a_longer_vaguer_phrase():
    """"I accuse you of lying — Clara saw you." was decided by "saw you"
    being one character longer than "accuse". An explicit performative is what
    the player is *doing*; it is not a topic to be outweighed."""
    assert _intent("I accuse you of lying — Clara saw you.") == "explicit_challenge"


@pytest.mark.parametrize("question", [
    "just admit it",
    "come clean with me",
    "stop lying to me",
    "we both know what really happened here",
])
def test_confession_adjacent_language_is_never_small_talk(question):
    assert _intent(question) == "explicit_challenge"


def test_naming_an_object_is_not_by_itself_an_accusation():
    """The override needs its own trigger. Scoring the named entity alongside
    the challenge phrase must never let the entity *be* the whole score —
    otherwise every mention of an object reads as a confrontation."""
    assert _intent("tell me about the till weight") == "object"
    assert _intent("was the till weight moved?") == "object"
    assert _intent("what happened at the fountain?") == "location"


def test_an_accusation_about_an_object_is_still_an_accusation():
    assert _intent("I accuse you of lying about the ledger page") == "explicit_challenge"


# ---------------------------------------------------------------------------
# Scoring mechanics
# ---------------------------------------------------------------------------

def test_coverage_counts_characters_not_matches():
    assert _coverage(["know"], "do you know him") == 4
    assert _coverage(["till weight"], "was the till weight moved") == 11


def test_coverage_does_not_double_count_overlapping_phrases():
    """RELATIONSHIP_PHRASES spells the same idea three ways ("get along",
    "got along", "getting along"). A list must not score higher merely for
    carrying more spellings of the one match."""
    assert _coverage(["get along", "get along with"], "did you get along") == 9
    assert _coverage(["close", "close to"], "were you close to him") == 8


def test_declaration_order_still_breaks_genuine_ties():
    """Order survives as the tiebreak — it is only no longer the decider.
    "get along" is in both RELATIONSHIP_PHRASES and GENERAL_RELATIONSHIPS_PHRASES
    and covers identical characters, so the earlier, more specific rule wins."""
    assert _intent("you two didn't exactly get along, did you?") == "relationship"


def test_greeting_loses_to_the_substantive_half_by_scoring_not_by_placement():
    assert _intent("hi") == "greeting"
    assert _intent("hi Col, how are you coping with the loss of Marcus?") == "how_are_you"
    assert _intent("hello, what were you doing that morning?") == "timeline"


# ---------------------------------------------------------------------------
# §12 categories that must not regress
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question,expected", [
    ("where were you?", "alibi"),
    ("what's your alibi?", "alibi"),
    ("what were you doing that morning?", "timeline"),
    ("when did you last see Marcus?", "last_seen_victim"),
    ("did you argue with him?", "relationship"),
    ("why would you want him dead?", "motive"),
    ("how are you?", "how_are_you"),
    ("what's your job?", "occupation"),
    ("tell me about yourself", "about_me"),
])
def test_core_intents_still_route(question, expected):
    assert _intent(question) == expected


@pytest.mark.parametrize("question", ["", "   ", "?????", "asdkjhasd", "🙂"])
def test_nonsense_is_an_honest_miss_not_a_hallucinated_match(question):
    """§12.7 — no crash, and no confident intent invented out of noise."""
    assert _intent(question) is None


def test_corrected_typos_score_as_the_word_they_became():
    """Layer 1 feeds Layer 4: correction happens before scoring, so a repaired
    word must compete as the word it was corrected into."""
    assert _intent("what was your realtionship with Marcus") == "relationship"
    assert _intent("what do you know about the strage room") == "location"


@pytest.mark.parametrize("question", ["where wer you", "did you knwo him"])
def test_short_word_typos_stay_an_honest_miss(question):
    """§12.2 asks for the miss to be *asserted*, not skipped. "wer" and "knwo"
    are under the >=5-letter fuzzy threshold, and §13 accepts that by
    measurement: any cutoff loose enough to repair them corrupts real short
    words. Scoring changes nothing here, and must not appear to."""
    assert _intent(question) is None


def test_a_motive_question_naming_someone_else_does_not_answer_about_the_victim():
    assert _intent("why would you want Isabella dead?") == "fallback_unknown"
    assert _intent("why would you want him dead?") == "motive"


def test_scoring_does_not_override_layer_3s_coreference_guard():
    """Layer 3 decides *who* a question is about before Layer 4 scores *what*
    it asks. Once the player has named another suspect, a bare "him" is
    genuinely ambiguous and the classifier must keep refusing to guess — a
    higher-scoring relationship match is not a licence to answer confidently
    about the wrong person."""
    from app.models import InterviewMessage

    case = get_case("case_001")
    session = Session(case_id="case_001")
    session.discovered_clue_ids = {c.clue_id for c in case.clues}
    assert classify_question("did you know him well?", case, session,
                             agent_id="agent_clara").intent == "relationship"

    session.transcript_for("agent_clara").messages.append(
        InterviewMessage(speaker="player", text="what do you think of Owen?")
    )
    assert classify_question("did you know him well?", case, session,
                             agent_id="agent_clara") is None


def test_undiscovered_entities_are_not_referenceable():
    """The truth firewall outranks scoring: an object the player has not
    discovered cannot win a competition it is not allowed to enter."""
    assert _intent("was the till weight moved?", discovered=False) != "object"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_case_routes_the_core_battery_identically(case_id):
    """Scoring must not become case-sensitive: entity names differ per case,
    but these questions name no entity and must route the same everywhere."""
    case = get_case(case_id)
    suspect = next(a for a in case.agents if not a.is_victim and not a.is_background)
    for question, expected in [
        ("where were you?", "alibi"),
        ("what were you doing that morning?", "timeline"),
        ("did you know him well?", "relationship"),
        ("just admit it", "explicit_challenge"),
        ("how are you?", "how_are_you"),
        ("hi", "greeting"),
    ]:
        assert _intent(question, case_id=case_id, agent_id=suspect.agent_id) == expected
