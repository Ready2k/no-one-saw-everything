"""Shared concept vocabulary for the concept-matching engine variant.

Instead of each fact enumerating its own literal phrases, a fact declares
which *concepts* must be present in the question. A concept is a named
cluster of surface synonyms (single words or short phrases) written once and
reused across every fact that needs it — recognising "is business slow"
shouldn't require every money-adjacent fact to separately anticipate that
exact wording.

Deliberate exception: ACCUSATION stays a bounded set of precise literal
phrases rather than loose synonyms. Being told "you're the killer" carries
the single biggest pressure spike in the engine — false positives and false
negatives both matter more here than for something like "are you busy",
where a miss just means a mild deflect. Concept clustering buys reach at the
cost of precision, and that trade isn't worth it on the highest-stakes
intent.
"""

import re

CONCEPTS: dict[str, set[str]] = {
    "MONEY": {"money", "cash", "pay", "paid", "owe", "owed", "owing", "debt", "broke", "skint", "fund", "funds", "loan", "afford"},
    "QUANTITY": {"how much", "amount", "sum", "total", "number"},
    "BUSY": {"busy", "quiet", "slow", "steady", "hectic", "slack"},
    "WORK": {"work", "job", "business", "yard", "trade"},
    "VIOLENCE": {"violent", "aggressive", "aggresive", "fist", "fists", "temper", "hostile", "fighter", "hot-tempered", "hottempered", "defensive"},
    "SIT": {"sit", "sitting", "stand", "standing", "pacing", "calm down"},
    "DEATH": {"died", "death", "dead", "murder happened", "found out he was dead"},
    # Bare "feel"/"feeling" is too generic — "are you feeling confused"
    # isn't asking about his reaction to the murder, and used to wrongly
    # trigger reaction_to_murder just because the word "feeling" appeared.
    # Full phrases only, matching the discipline already used for
    # ACCUSATION and ALIBI_PHRASE.
    "FEELING": {"how did you feel", "when you heard", "your reaction", "how you felt", "how did that feel"},
    "RELATIONSHIP": {"relationship", "friend", "friends", "friendship", "close", "terms", "get along"},
    "KNOW": {"know", "knew", "knowing", "met", "meet", "how did you know"},
    # "him"/"her" are deliberately NOT in VICTIM_NAME — a pronoun that
    # generic would collide with nearly every question about the victim in
    # the whole case. This narrow bigram is the one place a pronoun-inclusive
    # phrasing is common enough ("do you know him?") to earn its own entry.
    "KNOW_HIM": {"know him", "knew him"},
    "VICTIM_NAME": {"marcus", "victim", "deceased"},
    "WITNESS": {"witness", "vouch", "prove", "corroborate", "corroboration", "corroborated", "corroborating", "alone", "by yourself", "delivery driver", "col"},
    # Named third parties, used only as an exclusion signal on facts that
    # answer for Owen-and-Marcus specifically — never as a positive trigger
    # on their own (there's no fact that *should* fire just because "col" or
    # "isabella" was said).
    "COL": {"col"},
    # Bounded, precision-scoped phrases (not loose synonyms) so this beats
    # WITNESS's bare "col" via length-weighting instead of tying with it —
    # same fix applied to the keyword engine's alibi_corroboration fact.
    "COL_RELATIONSHIP": {
        "how do you know col", "how you know col", "is he family",
        "is col family", "family member", "who is col", "relationship with col",
    },
    "WHERE": {"where"},
    # Bare "window" is an ordinary word (a literal window in a building) as
    # often as it's the investigative term "murder window" — the keyword
    # engine already used the full phrase "murder window" for exactly this
    # reason. "murder window" here matches that discipline.
    "TIME_WINDOW": {"morning", "murder window", "7:45", "07:45", "8am", "quarter to eight"},
    # A bare "where" fallback would over-fire ("where's Col?" would wrongly
    # hit the alibi fact) — this stays a bounded, explicit phrase pair,
    # mirroring exactly what the keyword engine's alibi fact needs too.
    "ALIBI_PHRASE": {"where were you", "where you were", "alibi", "alibis"},
    "LAST_SEEN": {"last see", "last time you saw", "last seen"},
    "QUALITY": {"good job", "happy with your work", "satisfied", "complain", "quality of your work", "pleased with", "did a good job"},
    "PAYMENT": {"pay you", "paid you"},
    "CLARA": {"clara", "cafe girl", "counter"},
    "ISABELLA": {"isabella"},
    "ACCUSATION": {
        "you killed him", "did you kill him", "you murdered him", "think you killed",
        "you did it", "killed marcus", "murdered marcus", "kill marcus", "murder marcus",
        "you're the killer", "youre the killer", "you're guilty", "youre guilty",
        "why did you kill", "why did you do it", "why did you murder",
    },
    # Small-talk concepts — kept in the same shared table so nothing about
    # "mood" accidentally overlaps with "business status" the way a raw
    # keyword list could (that was a real bug earlier this session).
    "GREETING": {"hello", "hi", "hey", "good morning"},
    "NAME_ASK": {"your name", "who are you", "what's your name", "confirm your name", "what should i call you", "name"},
    "MOOD": {"how are you", "how you are", "you doing okay", "you holding up", "you holding", "you ok"},
    "JOB_ASK": {"what do you do", "your job", "what's your work", "job"},
    "LIKES": {"what do you like", "favourite", "favorite"},
    "SELF_ASK": {"tell me about yourself"},
    "EMOTION_ASK": {"how do you feel about", "what makes you happy"},
    "AGE_ASK": {"how old are you", "what's your age", "your age"},
    "SELF_ASSESS_ASK": {"would you say you're", "how would you describe yourself", "what kind of person are you", "what kind of man are you"},
    "CLOSING_ASK": {"thank you for your time", "thanks for your time", "that's all for now", "we're done here", "that'll be all"},
}

SMALL_TALK_CONCEPTS = {
    "greeting": {"GREETING"},
    "name": {"NAME_ASK"},
    "how_are_you": {"MOOD"},
    "occupation": {"JOB_ASK"},
    "favorite_thing": {"LIKES"},
    "about_me": {"SELF_ASK"},
    "feelings": {"EMOTION_ASK"},
    "age": {"AGE_ASK"},
    "self_assessment": {"SELF_ASSESS_ASK"},
    "closing": {"CLOSING_ASK"},
}

_PATTERN_CACHE: dict[str, re.Pattern] = {}


def _present(phrase: str, text: str) -> bool:
    phrase = phrase.strip()
    pattern = _PATTERN_CACHE.get(phrase)
    if pattern is None:
        left = r"\b" if phrase[:1].isalnum() else ""
        right = r"\b" if phrase[-1:].isalnum() else ""
        pattern = re.compile(left + re.escape(phrase) + right)
        _PATTERN_CACHE[phrase] = pattern
    return pattern.search(text) is not None


def detected_concepts(text: str) -> dict[str, int]:
    """Every concept present in `text`, mapped to the character length of
    the *longest* surface form that actually matched.

    Originally this returned a bare set and group_score counted concepts,
    not characters — which meant a 1-concept match via a long, specific
    phrase ("how do you know col", 20 chars) tied dead-even with a
    1-concept match via a short, generic word ("col", 3 chars) from a
    completely different fact, and the tie broke on fact declaration order,
    not relevance. That's ENGINE_SPEC.md finding #10, and it was hit for
    real (col_relationship vs alibi_corroboration both scoring 1). Scoring
    by matched length instead makes this the concept-level equivalent of
    the keyword engine's length-weighting, which already handles this
    correctly.
    """
    result: dict[str, int] = {}
    for name, forms in CONCEPTS.items():
        best_len = 0
        for form in forms:
            if _present(form, text):
                best_len = max(best_len, len(form))
        if best_len:
            result[name] = best_len
    return result


def concept_group_score(groups: list[frozenset], present: dict[str, int]) -> int:
    """Best-scoring group for one fact: the group whose matched surface
    forms sum to the most characters, so "how do you know col" (20 chars,
    one concept) outranks "col" (3 chars, one concept) even though both
    satisfy exactly one concept each."""
    best = 0
    present_names = present.keys()
    for group in groups:
        if group <= present_names:
            total = sum(present[name] for name in group)
            best = max(best, total)
    return best
