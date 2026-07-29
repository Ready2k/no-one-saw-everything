"""Layer 1 (ENGINE_SPEC.md §3) — typo tolerance and text-speak expansion.

The adversarial vocabulary sweep §12 item 9 calls for: run on every change
to the phrase/vocabulary tables, not just once. This asserts against the
REAL merged vocabulary (question_classifier.py's phrase lists + case_001's
proper nouns), not a mocked one, so it actually catches a future vocabulary
change that reopens a corruption the way "strange"->"storage" did here.
"""
import difflib

from app.case_store import get_case
from app.question_classifier import _STATIC_VOCAB, classify_question
from app.reference_resolver import _FUZZY_CUTOFF, case_vocabulary, normalize_text
from app.session import Session

# Common English words that must never get "corrected" into something in the
# vocabulary. Mirrors the sandbox's finding #13 list, extended with the word
# that actually broke at 0.85 for THIS vocabulary ("strange" -> "storage").
# Deliberately excludes "thing": it corrects to "things" (from HOW_ARE_YOU_
# PHRASES' "how are things"), which is a harmless same-word pluralisation,
# not a cross-word collision like "strange"/"storage" — no phrase list
# checks the bare singular "thing", so this correction changes nothing.
ADVERSARIAL_WORDS = [
    "going", "doing", "being", "having", "seeing", "coming", "looking", "working",
    "sorry", "worry", "money", "family", "father", "mother", "brother", "sister",
    "morning", "evening", "yesterday", "tomorrow", "always", "never", "sometimes",
    "quickly", "slowly", "quietly", "loudly", "really", "actually", "probably",
    "because", "before", "after", "during", "while", "since", "until",
    "thinking", "feeling", "hearing", "talking", "walking", "running", "standing",
    "answer", "question", "person", "people", "place", "moment",
    "remember", "forget", "understand", "explain", "describe", "mention",
    "certain", "sure", "clear", "obvious", "strange", "normal", "usual",
]

# Real typos, and the word they must correct to, that finding #4/#13-class
# bugs actually looked like.
KNOWN_TYPOS = [
    ("yoursefl", "yourself"),
    ("relatoinship", "relationship"),
    ("occupatoin", "occupation"),
    ("frendship", "friendship"),
    ("arguement", "argument"),
]


def _merged_vocab():
    case = get_case("case_001")
    return _STATIC_VOCAB | case_vocabulary(case)


def test_adversarial_words_are_never_corrupted():
    vocab = _merged_vocab()
    corrupted = []
    for word in ADVERSARIAL_WORDS:
        if word in vocab or len(word) < 5:
            continue
        hit = difflib.get_close_matches(word, vocab, n=1, cutoff=_FUZZY_CUTOFF)
        if hit:
            corrupted.append((word, hit[0]))
    assert corrupted == [], f"cutoff {_FUZZY_CUTOFF} corrupts common words: {corrupted}"


def test_known_typos_are_corrected_when_target_is_in_vocab():
    vocab = _merged_vocab()
    for typo, target in KNOWN_TYPOS:
        if target not in vocab:
            continue  # target isn't part of this vocabulary right now; not this test's job
        hit = difflib.get_close_matches(typo, vocab, n=1, cutoff=_FUZZY_CUTOFF)
        assert hit and hit[0] == target, f"{typo!r} should correct to {target!r}, got {hit}"


def test_short_words_are_never_corrected():
    """Finding #5: any cutoff loose enough to fix a short word also corrupts
    unrelated short words. Below the length floor, correction must not run
    at all — assert the miss, don't just skip testing it."""
    vocab = _merged_vocab()
    for word in ("who", "she", "ma", "hi"):
        result = normalize_text(word, vocab=vocab)
        assert result == word, f"{word!r} (< 5 letters) must never be corrected, got {result!r}"


def test_text_speak_expansion():
    vocab = _merged_vocab()
    assert normalize_text("u know him", vocab=vocab).split()[0] == "you"
    assert normalize_text("were ur friends", vocab=vocab).split()[1] == "your"


def test_typo_in_live_classification_still_resolves_alibi_intent():
    """End-to-end: a real typo in a real question still classifies correctly
    through classify_question, not just at the normalize_text unit level."""
    case = get_case("case_001")
    session = Session(case_id=case.case.case_id)
    agent_id = next(a.agent_id for a in case.agents if not a.is_victim)
    # "wher" (typo of "where") + "alibi" is well within the fixable range.
    intent = classify_question("what's your alibii", case, session, agent_id=agent_id)
    assert intent is not None
    assert intent.intent == "alibi"
