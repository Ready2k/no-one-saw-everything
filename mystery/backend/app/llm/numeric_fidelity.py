"""Times must survive a rewrite unchanged, or be dropped — never altered.

Every other check in `_sanitise` asks whether the rewrite said something it was
not *allowed* to say. This one asks a different question, and it is the only
one that does: is what it said still *true to the source*?

The gap is specific to this game. A rewrite that moves an arrival from 06:45 to
07:00 leaks nothing, invents no cast member, and uses no forbidden word — it
passes every existing gate — but the player's entire method is building a
timeline from testimony and finding where two accounts cannot both be true, and
`testimony.py` adjudicates bilocation on a *five minute* tolerance. Fifteen
minutes of drift manufactures and destroys contradictions in the layer the game
is about, and the player has no way to know the clock moved. Measured against
`llama3.1:8b`, Clara's authored "Marcus arrived at a quarter to seven" came
back as 07:00 three times and 07:15 once, in four attempts.

Two rules, because one is not enough:

1. **No invented times.** A clock time in the rewrite must appear in the source.
   This alone catches the fabricated 07:15.
2. **No reattributed times.** The times a rewrite attaches to a named person
   must be times the source attached to *that* person. This is what catches the
   07:00 — the source really does say "around seven", but about Owen's scene,
   not Marcus's arrival. Rule 1 is blind to it.

Deliberately conservative, per the tolerance philosophy in `testimony.py`: a
detector that cries wolf is worse than none, because the fallback text is
perfectly good and a rewrite rejected for nothing is pure loss. So a time is
bound to a person only when the name is in the same sentence and precedes it —
pronouns are never resolved, and an unattached time is checked by rule 1 alone.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# Hour words. Cases run inside a single part of the day, so times are compared
# modulo 12 hours: "seven" and "19:00" are the same clock face, and nothing in
# the game turns on am/pm that the surrounding prose doesn't already fix.
_HOURS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_MINUTE_WORDS = {
    "o'clock": 0, "oclock": 0, "five": 5, "ten": 10, "quarter": 15,
    "twenty": 20, "twenty-five": 25, "twenty five": 25, "half": 30,
    "fifteen": 15, "thirty": 30, "forty": 40, "forty-five": 45,
    "forty five": 45, "fifty": 50,
}

_HOUR_WORD = "|".join(_HOURS)
_DAY_MINUTES = 12 * 60

# Prepositions that make a bare hour a *clock reference* rather than a count.
# "at seven", "around seven", "until seven" are times; "seven crates" is not.
_TIME_PREP = r"(?:at|around|near|about|by|until|till|from|after|before|past|to|toward|towards)"

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 06:30 / 6.30 / 6:30 pm
    (re.compile(r"\b(\d{1,2})[:.](\d{2})\s*(a\.?m\.?|p\.?m\.?)?", re.I), "digits"),
    # quarter to seven / twenty past six / half past six
    (re.compile(rf"\b(quarter|half|five|ten|twenty|twenty[- ]five)\s+(past|to)\s+({_HOUR_WORD})\b", re.I), "rel"),
    # half six  (British idiom: 6:30)
    (re.compile(rf"\bhalf\s+({_HOUR_WORD})\b", re.I), "half_bare"),
    # six-thirty / six forty-five / seven fifteen
    (re.compile(rf"\b({_HOUR_WORD})[- ](thirty|fifteen|forty[- ]five|forty|fifty|ten|five|twenty|twenty[- ]five)\b", re.I), "compound"),
    # seven o'clock
    (re.compile(rf"\b({_HOUR_WORD})\s*o'?clock\b", re.I), "oclock"),
    # around seven / at six  (bare hour, only with a time preposition)
    (re.compile(rf"\b{_TIME_PREP}\s+({_HOUR_WORD})\b", re.I), "bare"),
    # 7am / 7 pm
    (re.compile(r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)", re.I), "digit_ampm"),
]


def _norm(hour: int, minute: int) -> int:
    return ((hour % 12) * 60 + minute) % _DAY_MINUTES


def _extract(match: re.Match[str], kind: str) -> Optional[int]:
    g = [x.lower() if isinstance(x, str) else x for x in match.groups()]
    try:
        if kind == "digits":
            hour, minute = int(g[0]), int(g[1])
            if hour > 23 or minute > 59:
                return None
            return _norm(hour, minute)
        if kind == "rel":
            amount = _MINUTE_WORDS[g[0].replace(" ", "-")] if g[0].replace(" ", "-") in _MINUTE_WORDS else _MINUTE_WORDS.get(g[0])
            hour = _HOURS[g[2]]
            if amount is None:
                return None
            return _norm(hour - 1, 60 - amount) if g[1] == "to" else _norm(hour, amount)
        if kind == "half_bare":
            return _norm(_HOURS[g[0]], 30)
        if kind == "compound":
            key = g[1].replace(" ", "-")
            minute = _MINUTE_WORDS.get(key, _MINUTE_WORDS.get(g[1]))
            if minute is None:
                return None
            return _norm(_HOURS[g[0]], minute)
        if kind == "oclock":
            return _norm(_HOURS[g[0]], 0)
        if kind == "bare":
            return _norm(_HOURS[g[0]], 0)
        if kind == "digit_ampm":
            hour = int(g[0])
            if hour > 23:
                return None
            return _norm(hour, 0)
    except (KeyError, ValueError, IndexError, TypeError):
        return None
    return None


def find_times(text: str) -> list[tuple[int, int]]:
    """Every clock reference in `text`, as (position, minutes-mod-12h).

    Overlapping matches are resolved **longest-first**, which is load-bearing
    rather than cosmetic. In "from six-thirty" the bare-hour rule matches
    "from six" (06:00) and the compound rule matches "six-thirty" (06:30);
    resolving by earliest start would keep 06:00 and reject a faithful rewrite
    for inventing a time it never stated. Length is the reliable signal for
    which reading is the real one, so the longest match claims its span and
    anything overlapping it is discarded.
    """
    found: list[tuple[int, int, int]] = []  # (start, end, minutes)
    for pattern, kind in _PATTERNS:
        for m in pattern.finditer(text):
            minutes = _extract(m, kind)
            if minutes is None:
                continue
            found.append((m.start(), m.end(), minutes))

    found.sort(key=lambda f: (-(f[1] - f[0]), f[0]))
    kept: list[tuple[int, int]] = []
    claimed: list[tuple[int, int]] = []
    for start, end, minutes in found:
        if any(start < c_end and end > c_start for c_start, c_end in claimed):
            continue
        claimed.append((start, end))
        kept.append((start, minutes))
    kept.sort()
    return kept


_SENTENCE_SPLIT = re.compile(r"[.!?\n]+")


def _associations(text: str, names: Iterable[str]) -> set[tuple[str, int]]:
    """(name, time) pairs the text asserts, by nearest preceding name in the
    same sentence. Pronouns are never resolved — an unbound time yields no pair
    and is left to the no-invented-times rule."""
    lowered = text.lower()
    names = [n.lower() for n in names if n]
    pairs: set[tuple[str, int]] = set()

    offset = 0
    for sentence in _SENTENCE_SPLIT.split(lowered):
        if sentence.strip():
            name_at: list[tuple[int, str]] = []
            for name in names:
                for m in re.finditer(rf"\b{re.escape(name)}\b", sentence):
                    name_at.append((m.start(), name))
            name_at.sort()
            for pos, minutes in find_times(sentence):
                preceding = [n for p, n in name_at if p < pos]
                if preceding:
                    pairs.add((preceding[-1], minutes))
        offset += len(sentence) + 1
    return pairs


def time_fidelity_violation(text: str, source: str, names: Iterable[str]) -> Optional[str]:
    """Does `text` assert a clock time that `source` does not support?

    Returns a rejection reason, or None when the rewrite is faithful. Dropping a
    time is always fine; only asserting a new or reattributed one is not.
    """
    source_times = {minutes for _pos, minutes in find_times(source.lower())}
    rewrite_times = find_times(text.lower())
    if not rewrite_times:
        return None

    def fmt(minutes: int) -> str:
        return f"{minutes // 60 or 12:02d}:{minutes % 60:02d}"

    # Rule 1 — no invented times.
    for _pos, minutes in rewrite_times:
        if minutes not in source_times:
            return f"states a time the source does not ({fmt(minutes)})"

    # Rule 2 — no reattributed times.
    names = list(names)
    source_pairs = _associations(source, names)
    for name, minutes in sorted(_associations(text, names)):
        if (name, minutes) in source_pairs:
            continue
        theirs = sorted(m for n, m in source_pairs if n == name)
        if not theirs:
            continue  # source never times this person; rule 1 already vouched
        return (
            f"moves {name.title()} to {fmt(minutes)} "
            f"(source says {', '.join(fmt(m) for m in theirs)})"
        )

    return None
