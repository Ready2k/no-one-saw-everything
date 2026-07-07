import re
from typing import Optional
from app.models import CaseData
from app.session import Session

def normalize_text(text: str) -> str:
    """Normalize text by lowercasing and removing non-alphanumeric chars (except spaces)."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text.strip()


_GENERIC_WORDS = {"the", "a", "an", "of", "and", "s"}


def _distinguishing_tokens(names: list[str]) -> list[set[str]]:
    """For each name (same order as given), the set of its whitespace tokens
    that appear in no other name in the list, after stripping generic filler
    words. This lets a player say "the alley" and resolve "Rear Alley"
    without requiring the full canonical name — but a word several
    candidates share (e.g. "cafe" across four locations) is deliberately
    left out of every candidate's set rather than guessed at, so an
    ambiguous mention still resolves to nothing rather than the wrong place.
    """
    token_lists = [
        {t for t in normalize_text(name).split() if t not in _GENERIC_WORDS and len(t) > 2}
        for name in names
    ]
    counts: dict[str, int] = {}
    for tokens in token_lists:
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1
    return [{t for t in tokens if counts[t] == 1} for tokens in token_lists]


def _match_by_name_or_alias(candidates: list, name_attr: str, q_norm: str):
    """candidates must already be sorted longest-name-first. A full
    canonical name match wins first (most specific, and matches prior
    behaviour exactly); otherwise fall back to a single-word alias that
    uniquely identifies one candidate among the rest."""
    names = [getattr(c, name_attr) for c in candidates]
    for candidate, name in zip(candidates, names):
        if normalize_text(name) in q_norm:
            return candidate

    q_words = set(q_norm.split())
    for candidate, aliases in zip(candidates, _distinguishing_tokens(names)):
        if aliases & q_words:
            return candidate
    return None


def resolve_references(
    question: str, case: CaseData, session: Session, extra_text: str = ""
) -> dict[str, Optional[str]]:
    """
    Resolve words in the player's question to known/discovered entities.
    Must not expose hidden truth.

    `extra_text` optionally widens the matching surface to include text the
    player has already seen on screen this interview (recent transcript
    lines) — e.g. so "What did you see from there?" can resolve "there" via
    an earlier turn that named the alley directly. It adds no leak surface
    since it is always text already displayed to the player, never hidden
    case data.

    Returns a dict with:
        referenced_agent_id
        referenced_location_id
        referenced_object_id
        referenced_clue_id
    """
    q_norm = normalize_text(f"{question} {extra_text}".strip())

    agent_id = None
    # Prioritize longest names (e.g. "clara vane" before "clara")
    agents = sorted(case.agents, key=lambda a: len(a.full_name), reverse=True)
    for a in agents:
        name_norm = normalize_text(a.full_name)
        first_name = normalize_text(a.full_name.split()[0])
        # Visible agents only. Assuming all agents in case.agents are visible/public known for now.
        if name_norm in q_norm or (first_name and first_name in q_norm.split()):
            agent_id = a.agent_id
            break

    # Common ways players refer to the victim without naming them. The victim's
    # identity is public knowledge, so this resolves no hidden truth.
    if agent_id is None:
        VICTIM_SYNONYMS = ("deceased", "victim", "dead man", "dead woman", "the body")
        if any(syn in q_norm for syn in VICTIM_SYNONYMS):
            victim = next((a for a in case.agents if a.is_victim), None)
            if victim:
                agent_id = victim.agent_id

    location_id = None
    locations = sorted(case.locations, key=lambda loc: len(loc.name), reverse=True)
    match = _match_by_name_or_alias(locations, "name", q_norm)
    if match:
        location_id = match.location_id

    object_id = None
    objects = sorted(case.objects, key=lambda o: len(o.name), reverse=True)
    known_objects = []
    for obj in objects:
        # Check if the object is known. An object is known if it has been discovered.
        # Discovered objects could be those touched by discovered clues.
        is_known = False
        for clue_id in session.discovered_clue_ids:
            clue = next((c for c in case.clues if c.clue_id == clue_id), None)
            if clue and obj.object_id in clue.linked_object_ids:
                is_known = True
                break
        if is_known:
            known_objects.append(obj)
    match = _match_by_name_or_alias(known_objects, "name", q_norm)
    if match:
        object_id = match.object_id

    clue_id = None
    clues = sorted(case.clues, key=lambda c: len(c.title), reverse=True)
    for clue in clues:
        if clue.clue_id in session.discovered_clue_ids:
            if normalize_text(clue.title) in q_norm:
                clue_id = clue.clue_id
                break

    return {
        "referenced_agent_id": agent_id,
        "referenced_location_id": location_id,
        "referenced_object_id": object_id,
        "referenced_clue_id": clue_id,
    }
