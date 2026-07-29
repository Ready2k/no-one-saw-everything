import difflib
import re
from typing import Optional
from app.models import CaseData
from app.session import Session

# Common texting shorthand, expanded before matching so a casually-typed
# question ("u know him?", "were u close") doesn't score worse than the same
# question typed formally. Word-boundary tokenised, applied unconditionally —
# unlike fuzzy typo correction below, this needs no vocabulary and carries no
# false-positive risk worth gating.
_TEXT_SPEAK = {"u": "you", "ur": "your", "r": "are", "y": "why", "pls": "please", "thx": "thanks"}

# Bounded fuzzy typo correction, ENGINE_SPEC.md §3's discipline: only words
# >=5 letters are eligible (a cutoff loose enough to fix a short word like
# "ma"->"me" also corrupts unrelated short words — "who"->"how", "she"->"the"
# — which is worse than the original miss), and correction only ever lands on
# a word that's actually in the caller-supplied vocabulary, never a fixed
# dictionary — so a typo can never "correct" into something nothing would
# have matched anyway.
#
# 0.86, not the sandbox's own 0.85 — empirically re-validated against THIS
# vocabulary (question_classifier.py's phrase lists + case proper nouns), not
# assumed to carry over. At 0.85, "strange" wrongly corrected to "storage" —
# a real collision the sandbox's smaller vocabulary never had, because
# case_001 (The Storage Room Murder) puts "storage" in the vocabulary as a
# location name. 0.86 removes that corruption while still catching every
# real typo tested, including "yoursefl" -> "yourself". Re-validate this
# number whenever the vocabulary changes meaningfully, per §3 — don't just
# assume it still holds.
_FUZZY_MIN_LEN = 5
_FUZZY_CUTOFF = 0.86


def _correct_typos(text: str, vocab: frozenset[str]) -> str:
    def repl(match: re.Match) -> str:
        word = match.group(0)
        if len(word) < _FUZZY_MIN_LEN or word in vocab:
            return word
        hit = difflib.get_close_matches(word, vocab, n=1, cutoff=_FUZZY_CUTOFF)
        return hit[0] if hit else word

    return re.sub(r"[a-z0-9]+", repl, text)


def normalize_text(text: str, vocab: frozenset[str] | None = None) -> str:
    """Normalize text by lowercasing and removing non-alphanumeric chars
    (except spaces), expanding text-speak, and — only when `vocab` is
    supplied — correcting bounded typos into that vocabulary.

    `vocab` is opt-in and per-call rather than a module-level default on
    purpose: normalizing an *authored* name (a candidate to match against,
    not player input) must never get "corrected" — there's nothing to
    correct in text that's already right. Only pass `vocab` when
    normalizing what the player actually typed.
    """
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r"\b\w+\b", lambda m: _TEXT_SPEAK.get(m.group(0), m.group(0)), text)
    if vocab:
        text = _correct_typos(text, vocab)
    return text.strip()


def case_vocabulary(case: CaseData) -> frozenset[str]:
    """Every word in this case's public, spellable proper nouns — agent
    names, location names, object names, discovered-or-not clue titles.
    None of this is hidden truth (agents/locations/objects are all
    player-visible; a clue *title* being in a spelling-correction vocabulary
    reveals nothing a player didn't already type themselves), so it's safe
    to build from the whole case rather than gating on discovery state.

    This is the dynamic half of the typo-correction vocabulary — the
    static half (investigation phrase vocabulary) lives in
    question_classifier.py, which merges the two.
    """
    words: set[str] = set()
    for agent in case.agents:
        words.update(normalize_text(agent.full_name).split())
    for location in case.locations:
        words.update(normalize_text(location.name).split())
    for obj in case.objects:
        words.update(normalize_text(obj.name).split())
    for clue in case.clues:
        words.update(normalize_text(clue.title).split())
    return frozenset(words)


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


def _match_by_name_or_alias(
    candidates: list, name_attr: str, q_norm: str, exclude_alias_tokens: set[str] | None = None
):
    """candidates must already be sorted longest-name-first. A full
    canonical name match wins first (most specific, and matches prior
    behaviour exactly); otherwise fall back to a single-word alias that
    uniquely identifies one candidate among the rest.

    Returns `(candidate, matched_surface_text)` — the surface form is what
    Layer 4's scoring weighs a reference by, so "till weight" can outrank an
    incidental four-letter "know". `(None, "")` when nothing matched.

    `exclude_alias_tokens` removes words from the alias fallback only — a
    location named after a person ("Elias Grant's House") must not be matched
    by the person's bare name ("how did you and Elias get along?" is about the
    man, not his house). Saying the full location name still matches."""
    names = [getattr(c, name_attr) for c in candidates]
    for candidate, name in zip(candidates, names):
        name_norm = normalize_text(name)
        if name_norm in q_norm:
            return candidate, name_norm

    q_words = set(q_norm.split())
    for candidate, aliases in zip(candidates, _distinguishing_tokens(names)):
        if exclude_alias_tokens:
            aliases = aliases - exclude_alias_tokens
        hits = aliases & q_words
        if hits:
            return candidate, max(hits, key=len)
    return None, ""


def resolve_references(
    question: str, case: CaseData, session: Session, extra_text: str = ""
) -> dict[str, Optional[str]]:
    """The entity ids referenced by a question — see `resolve_reference_matches`,
    of which this is the id-only view every existing caller wants."""
    return {k: v[0] for k, v in resolve_reference_matches(question, case, session, extra_text).items()}


def resolve_reference_matches(
    question: str, case: CaseData, session: Session, extra_text: str = ""
) -> dict[str, tuple[Optional[str], str]]:
    """
    Resolve words in the player's question to known/discovered entities.
    Must not expose hidden truth.

    Returns `key -> (entity_id, matched_surface_text)`. The surface text is
    what Layer 4 weighs a reference by: an entity named in full is a stronger
    signal about what the question is *about* than a short generic phrase that
    happens to appear alongside it.

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
    vocab = case_vocabulary(case)
    q_norm = normalize_text(f"{question} {extra_text}".strip(), vocab=vocab)

    agent_id = None
    agent_surface = ""
    # Prioritize longest names (e.g. "clara vane" before "clara")
    agents = sorted(case.agents, key=lambda a: len(a.full_name), reverse=True)
    for a in agents:
        name_norm = normalize_text(a.full_name)
        first_name = normalize_text(a.full_name.split()[0])
        # Visible agents only. Assuming all agents in case.agents are visible/public known for now.
        if name_norm in q_norm:
            agent_id, agent_surface = a.agent_id, name_norm
            break
        if first_name and first_name in q_norm.split():
            agent_id, agent_surface = a.agent_id, first_name
            break

    # Common ways players refer to the victim without naming them. The victim's
    # identity is public knowledge, so this resolves no hidden truth.
    if agent_id is None:
        VICTIM_SYNONYMS = ("deceased", "victim", "dead man", "dead woman", "the body")
        hits = [syn for syn in VICTIM_SYNONYMS if syn in q_norm]
        if hits:
            victim = next((a for a in case.agents if a.is_victim), None)
            if victim:
                agent_id, agent_surface = victim.agent_id, max(hits, key=len)

    location_id = None
    locations = sorted(case.locations, key=lambda loc: len(loc.name), reverse=True)
    # A person's name never stands in for a place named after them: "Elias" is
    # Elias, not "Elias Grant's House". (Full location names still match.)
    # Include possessive forms: "Grant's House" normalizes to "grants house",
    # and "grants" must be excluded just like "grant".
    agent_name_tokens = {
        form
        for a in case.agents
        for tok in normalize_text(a.full_name).split()
        for form in (tok, tok + "s")
    }
    match, location_surface = _match_by_name_or_alias(
        locations, "name", q_norm, exclude_alias_tokens=agent_name_tokens
    )
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
    match, object_surface = _match_by_name_or_alias(known_objects, "name", q_norm)
    if match:
        object_id = match.object_id

    clue_id = None
    clue_surface = ""
    clues = sorted(case.clues, key=lambda c: len(c.title), reverse=True)
    for clue in clues:
        if clue.clue_id in session.discovered_clue_ids:
            title_norm = normalize_text(clue.title)
            if title_norm in q_norm:
                clue_id, clue_surface = clue.clue_id, title_norm
                break

    return {
        "referenced_agent_id": (agent_id, agent_surface),
        "referenced_location_id": (location_id, location_surface if location_id else ""),
        "referenced_object_id": (object_id, object_surface if object_id else ""),
        "referenced_clue_id": (clue_id, clue_surface),
    }
