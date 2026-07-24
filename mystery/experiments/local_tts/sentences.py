"""Sentence splitting for future sentence-by-sentence synthesis (phase 3).

Not used by the v1 complete-response flow, but written and tested now because
the boundary rules (UK abbreviations, £ amounts, quoted dialogue, hesitation)
were part of the investigation brief. Run `python sentences.py` for a
self-check against the tricky cases.
"""

from __future__ import annotations

import re

# Tokens a full stop does NOT end a sentence after (case-sensitive where it
# matters: 'St.' as in street/saint, police ranks, honorifics, latinisms).
_ABBREVIATIONS = {
    "Mr", "Mrs", "Ms", "Dr", "Rev", "Prof", "Capt", "Col", "Sgt", "Insp",
    "Det", "Supt", "PC", "DC", "DS", "DI", "DCI", "St", "Ave", "Rd",
    "no", "No", "approx", "vs", "etc", "e.g", "i.e", "cf",
}

# A sentence ends at . ! or ? possibly followed by closing quotes/brackets,
# then whitespace, then something that starts a new sentence. An ellipsis is
# deliberately NOT a terminator: in dialogue it marks hesitation ("I… I
# wasn't there") and the pause must stay inside the spoken chunk.
_BOUNDARY = re.compile(
    r"""
    (?P<end>[.!?])
    (?P<close>["'”’\)\]]*)
    \s+
    (?=[“"'\(A-Z0-9])
    """,
    re.VERBOSE,
)


def _is_protected(text: str, dot_index: int) -> bool:
    """True if the '.' at dot_index is an abbreviation, initial or decimal."""
    before = text[:dot_index]
    after = text[dot_index + 1 : dot_index + 3]
    # Decimal or amount: £3.50, 7.45am — digit on both sides.
    if before and before[-1].isdigit() and after[:1].isdigit():
        return True
    match = re.search(r"([A-Za-z][A-Za-z.]*)$", before)
    if match:
        token = match.group(1).rstrip(".")
        # Single-letter initial ("J. Whitcombe") or known abbreviation.
        if len(token) == 1 and token.isupper():
            return True
        if token in _ABBREVIATIONS:
            return True
    return False


def split_sentences(text: str) -> list[str]:
    """Split display text into speakable sentences, respecting UK
    abbreviations, decimals/amounts, initials, quoted dialogue and ellipses.
    Hesitation dashes and ellipses stay inside their sentence."""
    sentences: list[str] = []
    start = 0
    for m in _BOUNDARY.finditer(text):
        if m.group("end") == "." and _is_protected(text, m.start("end")):
            continue
        end = m.end("close")
        sentence = text[start:end].strip()
        if sentence:
            sentences.append(sentence)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def chunk_for_synthesis(text: str, max_chars: int = 220) -> list[str]:
    """Group sentences into chunks below max_chars — per-sentence synthesis
    resets prosody, so we keep chunks as large as latency allows."""
    chunks: list[str] = []
    current = ""
    for sentence in split_sentences(text):
        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


if __name__ == "__main__":
    cases = [
        (
            'Mr. Whitcombe paid £3.50 at 7.45am. He seemed calm. "Too calm," Dr. Hale said.',
            [
                "Mr. Whitcombe paid £3.50 at 7.45am.",
                "He seemed calm.",
                '"Too calm," Dr. Hale said.',
            ],
        ),
        (
            "I… I don't— I wasn't there. Ask Insp. Reed! He knows.",
            ["I… I don't— I wasn't there.", "Ask Insp. Reed!", "He knows."],
        ),
        (
            "She lives on St. Mary's Rd. near the green. That's all I know.",
            ["She lives on St. Mary's Rd. near the green.", "That's all I know."],
        ),
        ("No.", ["No."]),
        (
            "DCI Marsh arrived at no. 4 at half past nine. J. Fletcher let him in.",
            ["DCI Marsh arrived at no. 4 at half past nine.", "J. Fletcher let him in."],
        ),
    ]
    failures = 0
    for text, expected in cases:
        got = split_sentences(text)
        status = "ok " if got == expected else "FAIL"
        if got != expected:
            failures += 1
        print(f"[{status}] {text!r}\n       -> {got}")
    raise SystemExit(1 if failures else 0)
