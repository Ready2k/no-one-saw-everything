import re
from typing import NamedTuple, Optional
from app.models import CaseData
from app.session import Session
from app.models import QuestionIntent
from app.reference_resolver import (
    resolve_reference_matches,
    resolve_references,
    normalize_text,
    case_vocabulary,
)

_PHRASE_PATTERN_CACHE: dict[str, re.Pattern] = {}


def _phrase_present(phrase: str, q_norm: str) -> bool:
    """Word-boundary phrase match, not a raw substring check.

    Every rule below used to test `phrase in q_norm`, a plain substring
    check — which matches "know" inside "acknowledged" and "unknown", "sad"
    inside "sadistic", "cry" inside "crystal", silently misrouting any
    question containing one of those unrelated words to the wrong intent
    (verified: "is it acknowledged that you spoke with him yesterday" was
    classified as "relationship" purely because of "know" inside
    "acknowledged"). `\\b` on both sides where both sides are word
    characters fixes this without needing per-phrase exceptions."""
    pattern = _PHRASE_PATTERN_CACHE.get(phrase)
    if pattern is None:
        left = r"\b" if phrase[:1].isalnum() else ""
        right = r"\b" if phrase[-1:].isalnum() else ""
        pattern = re.compile(left + re.escape(phrase) + right)
        _PHRASE_PATTERN_CACHE[phrase] = pattern
    return pattern.search(q_norm) is not None


def _any_phrase(phrases: list[str], q_norm: str) -> bool:
    return any(_phrase_present(p, q_norm) for p in phrases)


def _coverage(phrases, q_norm: str) -> int:
    """How much of the question a phrase list actually accounts for, in
    characters — ENGINE_SPEC §6's length-weighted score.

    Counting *covered characters* rather than summing matched phrase lengths
    is what makes overlapping entries safe: `RELATIONSHIP_PHRASES` holds
    "get along", "got along" and "getting along", and a list must not score
    higher merely for spelling the same match three ways. It also means a
    four-letter "know" scores 4 against "till weight"'s 11, which is the
    whole point — see §14.1.
    """
    covered: set[int] = set()
    for phrase in phrases:
        pattern = _PHRASE_PATTERN_CACHE.get(phrase)
        if pattern is None:
            _phrase_present(phrase, q_norm)  # populates the cache
            pattern = _PHRASE_PATTERN_CACHE[phrase]
        for m in pattern.finditer(q_norm):
            covered.update(range(m.start(), m.end()))
    return len(covered)


def _explicit_victim_reference(q_norm: str, q_words: set[str], victim) -> bool:
    """An unambiguous victim reference: the victim's own name, or the words
    "victim"/"deceased". Excludes bare pronouns, which are ambiguous the
    moment another person has already been named in the same conversation —
    see `_last_named_other_agent`."""
    if not victim:
        return False
    if normalize_text(victim.full_name.split()[0]) in q_norm:
        return True
    return bool({"victim", "deceased"} & q_words)


_DUAL_SUBJECT_PHRASES = ("you two", "the two of you", "between you two")


def _refers_to_victim(q_norm: str, q_words: set[str], victim) -> bool:
    """Word-boundary check for a victim reference, including ambiguous ones:
    bare pronouns ("him"/"her"/"them") and implicit dual-subject phrasing
    ("you two", "the two of you") — a leading question like "you two didn't
    get along, did you?" never names its second subject, but in an
    interrogation about a murder it defaults to meaning the victim. Pronouns
    must be whole words — a plain substring check matches "her" inside
    "there", "gathered", "weather" etc. and silently misroutes any question
    containing one of those, e.g. "what happened back there"."""
    if _explicit_victim_reference(q_norm, q_words, victim):
        return True
    if q_words & {"him", "her", "them"}:
        return True
    return _any_phrase(_DUAL_SUBJECT_PHRASES, q_norm)


def _last_named_other_agent(case: CaseData, session: Session, agent_id: Optional[str]) -> Optional[str]:
    """The most recent non-victim agent the player explicitly named in this
    suspect's own conversation, provided the victim hasn't been named more
    recently than that. Used to stop an ambiguous reference (a bare pronoun,
    or "you two didn't get along, did you?") from silently defaulting to the
    victim right after the player asked about someone else by name — "When
    did you last see Owen?" / "when did you last see them?" must stay about
    Owen, not become a confident (and wrong) answer about the victim."""
    if not agent_id:
        return None
    victim_id = next((a.agent_id for a in case.agents if a.is_victim), None)
    for message in reversed(session.transcript_for(agent_id).messages):
        if message.speaker != "player":
            continue
        referenced = resolve_references(message.text, case, session).get("referenced_agent_id")
        if referenced == victim_id:
            return None
        if referenced:
            return referenced
    return None


def _confidently_about_victim(
    q_norm: str, q_words: set[str], victim, case: CaseData, session: Session, agent_id: Optional[str]
) -> bool:
    """True only when a reference to "the victim" can safely resolve to the
    victim specifically. An explicit reference (their name, "victim",
    "deceased") always can. An ambiguous one (a bare pronoun, or "you two")
    can too — unless the player just named a different suspect in this same
    conversation, in which case defaulting to the victim would confidently
    answer about the wrong person instead of admitting the question is
    ambiguous."""
    if not victim:
        return False
    if _explicit_victim_reference(q_norm, q_words, victim):
        return True
    if not _refers_to_victim(q_norm, q_words, victim):
        return False
    return _last_named_other_agent(case, session, agent_id) is None


# ---------------------------------------------------------------------------
# Trigger phrase vocabulary — every phrase list classify_question matches
# against, hoisted to module level (previously several were inline literals
# or locals) so a static typo-correction vocabulary can be built from all of
# them at import time, ENGINE_SPEC.md §4.1's "full vocabulary extraction"
# approach: correction may only ever land on a word that's actually part of
# some real trigger, never a fixed dictionary. Every list below is byte-
# identical in content to what was previously inline — this is a hoist, not
# a behaviour change.
# ---------------------------------------------------------------------------

ALIBI_PHRASES = ["where were you", "where was you", "your alibi"]

TIMELINE_PHRASES = ["what were you doing", "what did you do", "where did you go"]

LAST_SEEN_PHRASES = ["last see", "last saw", "when did you see"]

# "get along"/"getting along" covers leading questions like "you two didn't
# exactly get along, did you?" — without this they fell all the way through
# to the small-talk "general_relationships" catch-all below and got a
# generic non-answer instead of being treated as the real relationship probe
# they are.
RELATIONSHIP_PHRASES = [
    "know", "relationship", "how did you feel about", "feel about", "first met",
    "how you met", "get along", "get on with", "got along", "got on with",
    "getting along", "on good terms", "on bad terms", "think of", "think about",
    "friends with", "friendly with", "close to", "close with", "trust",
]

# "argu" was a deliberately truncated stem to catch argue/argues/arguing/
# argued/argument/arguments via substring — under word-boundary matching a
# truncated stem can't match its own inflections (no boundary between "argu"
# and "ing"), so it's spelled out explicitly instead.
CONFLICT_PHRASES = [
    "argue", "argues", "arguing", "argued", "argument", "arguments",
    "fight with", "fought with", "disagreement", "falling out", "quarrel",
]

# "you're lying" (with apostrophe) could never match: normalize_text strips
# apostrophes, so q_norm always reads "youre lying" — this phrase was dead
# code before that was accounted for.
CONFRONTATIONAL_BLUFF_PHRASES = [
    "we both know", "we know what happened", "just admit", "just confess",
    "come clean", "tell me the truth", "stop lying", "youre lying", "why not just tell me",
]

CHALLENGE_PHRASES = [
    "challenge", "challenging", "challenged", "confront", "confronting",
    "confronted", "accuse", "accusing", "accused",
]

CONTRADICTION_PHRASES = [
    "why did", "how come", "but you said", "but they said", "someone said",
    "someone saw", "says you", "said you", "saw you", "claims you", "claimed you",
]

MOTIVE_PHRASES = ["why would you", "want dead", "reason to hurt", "angry with"]

# "how's it going" (apostrophe) could never match — normalize_text strips
# apostrophes, so q_norm reads "hows it going".
HOW_ARE_YOU_PHRASES = [
    "how are you", "how are things", "how do you do", "are you ok", "are you alright", "hows it going",
]

OCCUPATION_PHRASES = [
    "what do you do", "your job", "your occupation", "where do you work", "what is your work",
]

HOW_CAN_HELP_PHRASES = ["how can you help", "can you help", "what can you do", "help me out"]

FAVORITE_PHRASES = ["favorite", "favourite", "what do you like", "hobbies", "hobby"]

ABOUT_ME_PHRASES = ["tell me about yourself", "who are you", "your background", "where are you from"]

# Bare "sad"/"cry" under a raw substring check matched inside
# "sadistic"/"crystal" — word-boundary fixes that, but a truncated stem
# can't match its own inflections once bounded (no boundary between "sad"
# and "ness"), so the common inflections are spelled out explicitly to keep
# the original breadth.
EMOTION_WORDS = [
    "happy", "happiness", "unhappy", "sad", "sadness", "sadly", "saddened",
    "smile", "smiling", "smiled", "cry", "crying", "cried", "tears", "tearful",
]
EMOTION_TRIGGER_PHRASES = ["what makes", "do you", "are you"]

GENERAL_RELATIONSHIPS_PHRASES = [
    "friend", "friends", "friendship", "friendly", "get along", "do you like people", "relationships",
]

GREETING_WORDS = {"hi", "hello", "hey", "greetings"}

_ALL_PHRASE_LISTS = (
    ALIBI_PHRASES, TIMELINE_PHRASES, LAST_SEEN_PHRASES, RELATIONSHIP_PHRASES,
    CONFLICT_PHRASES, CONFRONTATIONAL_BLUFF_PHRASES, CHALLENGE_PHRASES,
    CONTRADICTION_PHRASES, MOTIVE_PHRASES, HOW_ARE_YOU_PHRASES, OCCUPATION_PHRASES,
    HOW_CAN_HELP_PHRASES, FAVORITE_PHRASES, ABOUT_ME_PHRASES, EMOTION_WORDS,
    EMOTION_TRIGGER_PHRASES, GENERAL_RELATIONSHIPS_PHRASES, list(GREETING_WORDS),
    list(_DUAL_SUBJECT_PHRASES),
)


def _build_static_vocab() -> frozenset[str]:
    words: set[str] = set()
    for phrases in _ALL_PHRASE_LISTS:
        for phrase in phrases:
            words.update(normalize_text(phrase).split())
    return frozenset(words)


# Built once at import time — this is the investigation-vocabulary half of
# typo correction. The dynamic half (a case's own proper nouns) comes from
# `case_vocabulary(case)` and is merged in per-call, since it varies by case.
_STATIC_VOCAB = _build_static_vocab()


# ENGINE_SPEC §2 calls Layer 4 "concept clusters + precision-literal
# overrides", and §5.3 names the intents that get the override: accusation and
# confession-adjacent language. The distinction is real and not just weighting.
# "I accuse you" is the player *performing* an act, not naming a topic — so it
# must not be outscored by a longer, vaguer phrase that happens to sit in the
# same sentence ("I accuse you of lying — Clara saw you." was decided by "saw
# you" being one character longer than "accuse"). Overrides are exact,
# unambiguous performatives with no loose synonym cluster behind them, which is
# precisely why they are safe to promote and why nothing else may join them.
_TIER_SCORED = 0
_TIER_PRECISION_LITERAL = 1


class _Candidate(NamedTuple):
    """One intent that fits the question, and how much of it that fit explains."""

    tier: int       # precision-literal overrides outrank scored matches outright
    score: int      # characters of the question this candidate accounts for
    order: int      # rule declaration order — the tiebreak, no longer the decider
    intent: str
    confidence: float
    rewritten: str


def classify_question(
    question: str, case: CaseData, session: Session, agent_id: Optional[str] = None
) -> Optional[QuestionIntent]:
    """Route a free-text question to a grounded intent, or None to let the LLM try.

    Every rule below used to `return` the moment it matched, so the earliest
    one always won no matter how little of the question it explained — four
    characters of "know" beat a named piece of evidence, and the only remedy
    was to keep bolting per-rule guards on (ENGINE_SPEC §14.1). Rules now
    *compete*: each scores the characters it accounts for (§6's length
    weighting), and the best fit wins. Declaration order survives only as the
    tiebreak, which is what keeps every deliberate precedence decision below
    intact for the genuinely ambiguous questions it was written for.
    """
    matches = resolve_reference_matches(question, case, session)
    refs = {key: value[0] for key, value in matches.items()}
    surface = {key: value[1] for key, value in matches.items()}
    vocab = _STATIC_VOCAB | case_vocabulary(case)
    q_norm = normalize_text(question, vocab=vocab)
    q_words = set(q_norm.split())
    victim = next((a for a in case.agents if a.is_victim), None)
    about_victim = _confidently_about_victim(q_norm, q_words, victim, case, session, agent_id)

    candidates: list[_Candidate] = []

    def offer(
        score: int, intent: str, confidence: float, rewritten: str,
        tier: int = _TIER_SCORED,
    ) -> None:
        if score > 0:
            candidates.append(
                _Candidate(tier, score, len(candidates), intent, confidence, rewritten)
            )

    def ref_score(key: str) -> int:
        # A resolved entity always accounts for at least one character, even if
        # the surface form somehow came back empty.
        return len(surface.get(key) or "") if refs.get(key) else 0

    # 1. Alibi
    offer(_coverage(ALIBI_PHRASES, q_norm), "alibi", 0.9,
          "Where were you during the murder window?")

    # 2. Timeline
    offer(_coverage(TIMELINE_PHRASES, q_norm), "timeline", 0.8,
          "What were you doing at that time?")

    # 3. Last seen victim
    if about_victim:
        offer(_coverage(LAST_SEEN_PHRASES, q_norm), "last_seen_victim", 0.9,
              "When did you last see the victim?")

    # 4. Relationship.
    # "where"/"when" questions are about whereabouts even if they mention knowing
    # someone ("do you know where Clara was?") — leave those to the later rules.
    if "where" not in q_words and "when" not in q_words:
        relationship_score = _coverage(RELATIONSHIP_PHRASES, q_norm)
        if about_victim:
            offer(relationship_score, "relationship", 0.85,
                  "What was your relationship with the victim?")
        elif refs.get("referenced_agent_id"):
            # A relationship question about another villager. The grounded engine only
            # answers relationship-with-the-victim, so route this to the open-ended
            # path (or its honest fallback) — never to a location that happens to be
            # named after the person ("Elias" is not "Elias Grant's House").
            offer(relationship_score, "fallback_unknown", 0.6, "What do you make of them?")

    # 4b. Conflict/argument with the victim. "Argued", "fought", "disagreement"
    # etc. are not "when did you last see" phrasing (rule 3) and describe a
    # relationship dynamic, not a sighting — routing them to last_seen_victim
    # forces the dialogue rewriter to bridge an unrelated topic, which is how
    # it ends up inventing an incident ("we had a disagreement") that was
    # never in the seeded truth. The relationship answer is the nearest real
    # grounded topic.
    if about_victim:
        offer(_coverage(CONFLICT_PHRASES, q_norm), "relationship", 0.85,
              "What was your relationship with the victim?")

    # 4c. Confrontational bluff ("we both know what happened", "just admit
    # it") demands a confession without necessarily naming a piece of
    # evidence. It must not fall through to the small-talk buckets below —
    # a suspect should react with suspicion or denial, not recite a generic
    # relationship blurb as if nothing happened.
    offer(_coverage(CONFRONTATIONAL_BLUFF_PHRASES, q_norm), "explicit_challenge", 0.6,
          "Why not just tell me the truth?", tier=_TIER_PRECISION_LITERAL)

    # 5. Explicit Challenge or Contradiction.
    # These two are §5.3's "precision-literal, high-stakes" intents: the player
    # is confronting, not chatting, and a confrontation misread as small talk
    # is the most jarring failure the interview has. They therefore score the
    # named entity they are *about* alongside their own trigger — the entity is
    # the substance of the accusation ("you lied about the LEDGER PAGE"), not a
    # competing subject, so it must not hand the turn to a flat description of
    # that same object.
    # The entity only adds to the score; it can never *be* the score. Both
    # rules still require their own trigger phrase, exactly as before — without
    # that guard, naming any object at all would read as an accusation.
    challenge_trigger = _coverage(CHALLENGE_PHRASES, q_norm)
    challenge_target = max(
        ref_score("referenced_agent_id"),
        ref_score("referenced_clue_id"),
        ref_score("referenced_object_id"),
    )
    if challenge_trigger and challenge_target:
        offer(challenge_trigger + challenge_target,
              "explicit_challenge", 0.85, "I challenge you on this.",
              tier=_TIER_PRECISION_LITERAL)

    contradiction_trigger = _coverage(CONTRADICTION_PHRASES, q_norm)
    contradiction_target = max(ref_score("referenced_agent_id"), ref_score("referenced_clue_id"))
    if contradiction_trigger and contradiction_target:
        offer(contradiction_trigger + contradiction_target,
              "contradiction", 0.8, "Can you explain this contradiction?")

    # 6. Motive. The grounded engine only answers motive-toward-the-victim
    # (it degrades to a "relationship" AnswerRule, which is hardcoded to the
    # victim) — a motive question that explicitly names someone else ("why
    # would you want ISABELLA dead?") must not be silently answered as if it
    # asked about the victim. Verified this was live: that exact question
    # returned Owen's relationship-with-Marcus confession. An untargeted or
    # victim-targeted question keeps defaulting to victim motive, same as
    # today — "did you have a motive" in a murder interrogation is read as
    # "to kill the person who's dead" absent a different explicit target,
    # and a bare pronoun ("why would you want him dead?") never resolves to
    # an agent id here, so it isn't caught by this check.
    motive_score = _coverage(MOTIVE_PHRASES, q_norm)
    referenced_agent_id = refs.get("referenced_agent_id")
    if referenced_agent_id and (not victim or referenced_agent_id != victim.agent_id):
        offer(motive_score, "fallback_unknown", 0.6, "What do you make of them?")
    else:
        offer(motive_score, "motive", 0.9, "Did you have a motive?")

    # 7-9. The entity the question actually names. Scored by the length of the
    # name the player used, which is what lets "the till weight" outrank an
    # incidental "as far as you know".
    offer(ref_score("referenced_object_id"), "object", 0.9,
          "What do you know about this object?")
    offer(ref_score("referenced_clue_id"), "evidence", 0.9,
          "What do you know about this evidence?")
    offer(ref_score("referenced_location_id"), "location", 0.9,
          "What do you know about this location?")

    # Small talk.
    offer(_coverage(HOW_ARE_YOU_PHRASES, q_norm), "how_are_you", 0.9, "How are you?")
    offer(_coverage(OCCUPATION_PHRASES, q_norm), "occupation", 0.9, "What is your occupation?")
    offer(_coverage(HOW_CAN_HELP_PHRASES, q_norm), "how_can_help", 0.9, "How can you help?")
    offer(_coverage(FAVORITE_PHRASES, q_norm), "favorite_thing", 0.9, "What is your favorite thing?")
    offer(_coverage(ABOUT_ME_PHRASES, q_norm), "about_me", 0.9, "Tell me about yourself.")

    if _any_phrase(EMOTION_WORDS, q_norm) and _any_phrase(EMOTION_TRIGGER_PHRASES, q_norm):
        offer(_coverage(EMOTION_WORDS + EMOTION_TRIGGER_PHRASES, q_norm), "emotions", 0.9,
              "What makes you happy or sad?")

    offer(_coverage(GENERAL_RELATIONSHIPS_PHRASES, q_norm), "general_relationships", 0.8,
          "Tell me about your relationships.")

    # Greetings score last and score low, which is now the mechanism rather
    # than a hand-placed exception: "hi" accounts for two characters, so a
    # compound opener ("Hi Col, how are you coping?") is decided by its
    # substantive half without needing a rule about where greetings sit.
    offer(_coverage(list(GREETING_WORDS), q_norm), "greeting", 0.9, "Hello.")

    if not candidates:
        # Low confidence -> Return None to let LLM handle it
        return None

    best = max(candidates, key=lambda c: (c.tier, c.score, -c.order))
    return QuestionIntent(
        intent=best.intent,
        confidence=best.confidence,
        **refs,
        rewritten_structured_question=best.rewritten,
    )
