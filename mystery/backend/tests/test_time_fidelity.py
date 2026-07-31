"""A rewrite may drop a time. It may not move one.

Every other sanitiser check asks whether the rewrite said something forbidden.
This one asks whether what it said is still true to the grounded answer — the
only failure mode that leaks nothing, invents no one, uses no forbidden word,
and still ruins the game. `testimony.py` calls bilocation at five minutes'
tolerance; a rewrite that shifts an arrival by fifteen manufactures and
destroys contradictions with nothing on screen to say the clock moved.

The failing cases below are real output from `llama3.1:8b`, measured against
case_001's Clara on 2026-07-31 (four attempts, four wrong times).
"""

import pytest

from app.llm.numeric_fidelity import find_times, time_fidelity_violation

# Clara's authored answer. Ground truth: Clara from 06:30, Marcus at 06:45,
# Owen's scene around 07:00.
SOURCE = (
    "Down at half six, prep until Marcus arrived at a quarter to seven. "
    "He checked the till - he'd been doing that a lot lately. Owen turned up "
    "around seven and made a scene outside. After that, more prep."
)
NAMES = ["Marcus", "Owen", "Clara", "Elias", "Nadia", "Priya", "Ben"]


def check(text: str):
    return time_fidelity_violation(text, SOURCE, NAMES)


# ---------------------------------------------------------------------------
# Parsing: equivalent phrasings must compare equal, or the check cries wolf
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phrase,expected", [
    ("at 06:30", 390), ("at 6:30", 390), ("half six", 390),
    ("half past six", 390), ("six-thirty", 390), ("six thirty", 390),
    ("a quarter to seven", 405), ("six forty-five", 405), ("at 06:45", 405),
    ("around seven", 420), ("seven o'clock", 420), ("at 07:00", 420),
    ("twenty past six", 380), ("ten to seven", 410),
])
def test_clock_phrasings_normalise_to_the_same_minute(phrase, expected):
    assert [m for _pos, m in find_times(phrase)] == [expected], phrase


def test_a_longer_reading_wins_over_a_shorter_overlapping_one():
    """"from six-thirty" contains "from six". Resolving overlaps by earliest
    start would read 06:00 and reject a faithful rewrite for inventing it."""
    assert [m for _pos, m in find_times("from six-thirty")] == [390]
    assert [m for _pos, m in find_times("at a quarter to seven")] == [405]


def test_a_bare_count_is_not_a_clock_time():
    """Without a time preposition, a number is a quantity. "seven crates" must
    not register as 07:00 and drag an innocent rewrite into a rejection."""
    assert find_times("I unpacked seven crates of milk") == []


# ---------------------------------------------------------------------------
# Rule 1 — no invented times
# ---------------------------------------------------------------------------

def test_a_fabricated_time_is_refused():
    """llama3.1:8b, run 3 of 4. 07:15 appears nowhere in the source."""
    assert check("I started prepping at 6:30. Marcus arrived around 7:15.")


# ---------------------------------------------------------------------------
# Rule 2 — no reattributed times
# ---------------------------------------------------------------------------

def test_a_time_moved_onto_the_wrong_person_is_refused():
    """llama3.1:8b, runs 1, 2 and 4. This is why rule 1 is not sufficient:
    07:00 *is* in the source — it is when Owen turned up, not Marcus."""
    reason = check("I started prepping at 06:30. Marcus arrived around 07:00, checked the till.")

    assert reason is not None
    assert "marcus" in reason.lower()
    assert "07:00" in reason and "06:45" in reason, reason


def test_the_reattribution_rule_catches_a_vague_hedge_too():
    """gemma4's "near seven" for an authored 06:45 is still fifteen minutes of
    drift on the board, however softly it is phrased."""
    assert check("I was prepping from six-thirty until Marcus arrived near seven.")


def test_a_time_belonging_to_nobody_in_the_source_is_left_to_rule_one():
    """Conservative by design: if the source never times this person, rule 1
    has already confirmed the time exists, and guessing at attribution would
    invent violations."""
    assert check("Elias came by around seven.") is None


# ---------------------------------------------------------------------------
# What must still be accepted — the cost of a false positive is a lost rewrite
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    # gemma4's real output, all faithful
    "I was prepping the cafe from six-thirty until Marcus arrived at six forty-five. "
    "After Owen caused a commotion outside around seven, I continued.",
    "I was prepping since six-thirty, continuing until Marcus arrived near quarter to seven. "
    "After Owen made his scene outside around seven, I resumed.",
    # dropping detail is always allowed
    "I was prepping the cafe until Marcus arrived. Owen caused a scene later.",
    "I was in early doing prep, same as always.",
    "I don't remember. It was a normal morning.",
    # paraphrasing the clock is allowed when the minute survives
    "I was down at half past six for prep.",
    "I started at 6:30.",
    SOURCE,
])
def test_faithful_rewrites_are_not_rejected(text):
    assert check(text) is None, text


def test_no_times_anywhere_is_trivially_fine():
    assert time_fidelity_violation("I was there.", "No times here either.", NAMES) is None


# ---------------------------------------------------------------------------
# Wiring: the check is actually reachable through the sanitiser
# ---------------------------------------------------------------------------

def test_the_sanitiser_rejects_a_moved_time(monkeypatch):
    from app import case_store
    from app.llm.dialogue_rewriter import _sanitise

    case = case_store.get_case("case_001")
    reason = _sanitise(
        "Marcus arrived around 07:00.",
        forbidden_facts=[], allowed_facts=[], case=case,
        allowed_context=[SOURCE],
    )

    assert reason is not None
    assert "Alters a time" in reason, reason


def test_the_sanitiser_accepts_a_faithful_time(monkeypatch):
    from app import case_store
    from app.llm.dialogue_rewriter import _sanitise

    case = case_store.get_case("case_001")
    reason = _sanitise(
        "Marcus arrived at a quarter to seven.",
        forbidden_facts=[], allowed_facts=[], case=case,
        allowed_context=[SOURCE],
    )

    assert reason is None, reason
