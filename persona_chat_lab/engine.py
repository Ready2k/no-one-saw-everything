"""Deterministic persona chat engine — no LLM, no network calls.

This is the sandboxed "next lever" from the shipped mystery engine's
dialogue_processor.py: instead of picking a scripted answer and prefixing a
filler word, each persona has a real rendering pipeline that restructures
sentences (hedge insertion at clause boundaries, sentence trimming/emphasis,
self-interruption) and a pressure state that escalates from how the
detective is actually pressing them — not just a per-question dice roll.
"""

from __future__ import annotations

import difflib
import hashlib
import re
import secrets
from dataclasses import dataclass, field

from personas import PERSONAS
import claims as claims_mod
import concepts as concepts_mod

CONFRONTATIONAL_WORDS = [
    "lying", "liar", "lie", "contradiction", "prove it",
    "come on", "don't believe you", "not true", "add up", "admit it",
    "confess", "bullshit", "really", "are you sure", "sure about that",
]

SMALL_TALK_KEYWORDS = {
    "greeting": ["hello", "hi", "hey", "good morning"],
    "name": ["your name", "who are you", "what's your name", "confirm your name", "what should i call you", "name"],
    "how_are_you": ["how are you", "how you are", "you doing okay", "you holding up", "you holding", "you ok"],
    "occupation": ["what do you do", "your job", "what's your work", "job"],
    "favorite_thing": ["what do you like", "favourite", "favorite"],
    "about_me": ["tell me about yourself"],
    "feelings": ["how do you feel about", "what makes you happy"],
    "age": ["how old are you", "what's your age", "your age"],
    "self_assessment": ["would you say you're", "how would you describe yourself", "what kind of person are you", "what kind of man are you"],
    "closing": ["thank you for your time", "thanks for your time", "that's all for now", "we're done here", "that'll be all"],
}

BAND_NAMES = {0: "composed", 1: "guarded", 2: "cornered", 3: "breaking"}


def _performance_for(persona_key: str, band: str, topic: str | None, emotion: str) -> str | None:
    """Choose a reviewed Owen performance from player-safe response state.

    This is deliberately a small authored vocabulary, not a random animation
    loop. It is selected only after the answer is safe to display and does
    not receive hidden-case information.
    """
    if persona_key not in {"owen", "owen_twin"} or topic is None:
        return None
    if band in {"cornered", "breaking"} or emotion in {"bristling", "fighting_hard", "defensive"}:
        return "guarded"
    if emotion in {"neutral", "weary", "regretful", "grim"}:
        return "considering"
    return "answering"

# Layer 6 tension detector (ENGINE_SPEC.md §8): deliberately bounded to the
# exact time phrasings this case's facts are actually authored with — not a
# general time parser. Minutes since midnight.
_TIME_PHRASES: dict[str, int] = {
    "7:05": 425, "07:05": 425, "five past seven": 425,
    "7:15": 435, "07:15": 435, "quarter past seven": 435,
}


def _find_time_refs(text: str) -> set[int]:
    return {minutes for phrase, minutes in _TIME_PHRASES.items() if _kw_present(phrase, text)}


def _stable_index(seed_parts, length: int) -> int:
    seed = "|".join(str(p) for p in seed_parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % length


_KEYWORD_PATTERN_CACHE: dict[str, re.Pattern] = {}


def _kw_present(kw: str, text: str) -> bool:
    """Word-boundary match, not a raw substring check.

    Plain `kw in text` has two failure modes: a short keyword like "hi"
    false-matches inside unrelated words ("this", "history"), and the
    trailing-space hack used to dodge that ("hi ") then fails to match the
    keyword when it's the *last* word typed with nothing after it — which is
    exactly how a real person opens a chat ("hi", no trailing space). Word
    boundaries fix both at once, and interior spaces in multi-word phrases
    ("how are you") are unaffected since \\b only cares about the ends.
    """
    kw = kw.strip()
    pattern = _KEYWORD_PATTERN_CACHE.get(kw)
    if pattern is None:
        # \b only makes sense on a side that's actually a word character —
        # a keyword ending in punctuation ("really?") can never satisfy a
        # trailing \b (no boundary forms between "?" and end-of-string), so
        # a blanket \b...\b would make that keyword silently unmatchable.
        left = r"\b" if kw[:1].isalnum() else ""
        right = r"\b" if kw[-1:].isalnum() else ""
        pattern = re.compile(left + re.escape(kw) + right)
        _KEYWORD_PATTERN_CACHE[kw] = pattern
    return pattern.search(text) is not None


def _kw_score(keywords, text: str) -> int:
    return sum(len(kw) for kw in keywords if _kw_present(kw, text))


_TEXT_SPEAK = {"u": "you", "ur": "your", "r": "are", "y": "why", "pls": "please", "thx": "thanks"}


def _build_vocab() -> set[str]:
    """Every word that appears in any keyword or concept surface form,
    across all personas — the dictionary the typo-tolerance pass is allowed
    to correct *into*. Typo normalization runs before either matcher, so
    both need equal coverage for the comparison to be fair."""
    vocab: set[str] = set()
    for source in (CONFRONTATIONAL_WORDS, *SMALL_TALK_KEYWORDS.values(), *concepts_mod.CONCEPTS.values()):
        for kw in source:
            vocab.update(re.findall(r"[a-z']+", kw.lower()))
    for persona in PERSONAS.values():
        for fact in persona["facts"]:
            for kw in fact.get("keywords", []):
                vocab.update(re.findall(r"[a-z']+", kw.lower()))
    return vocab


_VOCAB = _build_vocab()


def _fuzzy_correct(text: str) -> str:
    """Correct obvious typos in longer words against the keyword vocabulary
    ("marcuss" -> "marcus", "relatoinship" -> "relationship") before
    matching. Deliberately skips words under 5 letters: short words are
    where this gets dangerous — at a cutoff loose enough to fix "ma" -> "me"
    it also starts silently corrupting unrelated words ("who" -> "how",
    "she" -> "the"), which is worse than the original miss. That's a real
    ceiling on this approach, not a bug: a keyword matcher can't safely
    recover every typo the way something that's actually reading for
    meaning can.

    cutoff=0.85, not 0.78: at 0.78 this silently corrupted the ordinary
    word "going" into "owing" (ratio 0.80, both vocabulary members of
    MONEY) mid-sentence in a plain rapport line ("I'm not going anywhere"),
    which then wrongly re-triggered the debt fact. Every intended typo fix
    (yoursefl->yourself, marcuss->marcus, relatoinship->relationship,
    partnershp->partnership) scores 0.875+, so 0.85 keeps all of those
    while excluding "going"/"doing"->"owing" and "worry"->"sorry" (all
    0.80) — a real, measured gap, not an arbitrary number.
    """
    def repl(match: re.Match) -> str:
        word = match.group(0)
        if len(word) < 5 or word in _VOCAB:
            return word
        hit = difflib.get_close_matches(word, _VOCAB, n=1, cutoff=0.85)
        return hit[0] if hit else word

    return re.sub(r"[a-z']+", repl, text)


def _normalize(text: str) -> str:
    """Expand common texting shorthand, then correct likely typos, before
    matching. A real detective typing casually ("u know him?", "were u
    close") or with a typo shouldn't get worse matches than the same
    question typed formally and correctly."""
    text = re.sub(r"\b\w+\b", lambda m: _TEXT_SPEAK.get(m.group(0), m.group(0)), text)
    return _fuzzy_correct(text)


def _split_clauses(text: str) -> list[str]:
    # Split on sentence-ending punctuation, keeping the punctuation attached.
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


# ---------------------------------------------------------------------------
# Persona-specific rendering. Each archetype gets its own function rather
# than a shared parameterised one — the whole point of this sandbox is that
# "blunt" and "soft-spoken" shouldn't just be two settings of one dial, they
# should visibly be different *kinds* of transformation.
# ---------------------------------------------------------------------------

OWEN_CLOSERS = {
    2: ["That's the truth of it.", "Take it or don't.", "I've nothing to add."],
    3: ["I'm done answering that twice.", "Ask Col yourself if you don't believe me.", "That's the last I'll say on it."],
}
OWEN_ACTIONS = {
    0: ["*[Leaves a workman's pause before answering]*"],
    1: ["*[Arms cross]*", "*[Doesn't sit down]*"],
    2: ["*[Jaw tightens]*", "*[Leans forward, voice rising]*"],
    3: ["*[Slams a flat hand on the bench]*", "*[Voice cracks around the shout]*"],
}
OWEN_REPEAT = {
    1: "I already answered that.",
    2: "I'm not saying it twice.",
    3: "For the last time —",
}


def _render_owen(text: str, band: int, seed: str, repeat_count: int) -> str:
    if repeat_count >= 1:
        opener = OWEN_REPEAT[min(repeat_count, 3)]
        return f"{opener} {text}"

    clauses = _split_clauses(text)

    if band >= 2:
        # Gets louder rather than more careful: emphasise the shortest clause
        # by forcing an exclamation, rather than trimming detail away.
        idx = min(range(len(clauses)), key=lambda i: len(clauses[i]))
        emphasised = clauses[idx].rstrip(".!?") + "!"
        clauses[idx] = emphasised
        text = " ".join(clauses)
        if _stable_index((seed, "closer"), 10) < 6:
            pool = OWEN_CLOSERS[band]
            text = f"{text} {pool[_stable_index((seed, 'closer-pick'), len(pool))]}"

    action_pool = OWEN_ACTIONS[band]
    if _stable_index((seed, "action-roll"), 10) < {0: 3, 1: 5, 2: 7, 3: 9}[band]:
        action = action_pool[_stable_index((seed, "action-pick"), len(action_pool))]
        text = f"{action} {text}"

    return text


PRIYA_HEDGES = ["I think ", "maybe ", "I don't know, but "]
PRIYA_ACTIONS = {
    0: ["*[Watches your face as she answers]*"],
    1: ["*[Twists a loose thread on her sleeve]*", "*[Glances at the door]*"],
    2: ["*[Looks at the table]*", "*[Voice drops]*"],
    3: ["*[Voice barely above a whisper]*", "*[Hands pressed flat to stop them shaking]*"],
}
PRIYA_REPEAT = {
    1: "I already told you that.",
    2: "I'm not sure how else to say it —",
    3: "Please, I've said it twice now —",
}


def _render_priya(text: str, band: int, seed: str, repeat_count: int) -> str:
    if repeat_count >= 1:
        opener = PRIYA_REPEAT[min(repeat_count, 3)]
        return f"{opener} {text}"

    clauses = _split_clauses(text)

    # Insert a hedge at a clause boundary, not just at the very start — a
    # real hedger interrupts themselves mid-thought, not just opens with
    # "um" once and then speaks plainly. Rolled, not guaranteed, so a
    # pressured answer doesn't hedge on literally every single sentence.
    if band >= 1 and len(clauses) > 1 and _stable_index((seed, "hedge-roll"), 10) < 6:
        pos = _stable_index((seed, "hedge-pos"), len(clauses) - 1) + 1
        hedge = PRIYA_HEDGES[_stable_index((seed, "hedge-pick"), len(PRIYA_HEDGES))]
        clauses.insert(pos, hedge.strip().capitalize() + "...")
        text = " ".join(clauses)

    if band >= 2:
        # Self-interruption: cut the final sentence off with an em-dash
        # instead of letting it land clean.
        clauses = _split_clauses(text)
        if clauses:
            last = clauses[-1].rstrip(".!?")
            cut_words = last.split()
            if len(cut_words) > 4:
                cut = " ".join(cut_words[: len(cut_words) // 2]) + "—"
                clauses[-1] = cut
                text = " ".join(clauses)

    if band == 0 and _stable_index((seed, "opener-roll"), 10) < 4:
        # Lowercase the join unless the word is "I"/"I'm"/etc — "Um, I was"
        # reads fine, "Um, From" reads like a typo.
        first_word = text.split(" ", 1)[0]
        if first_word != "I" and not first_word.startswith("I'"):
            text = text[0].lower() + text[1:]
        text = "Um, " + text

    action_pool = PRIYA_ACTIONS[band]
    if _stable_index((seed, "action-roll"), 10) < {0: 3, 1: 5, 2: 7, 3: 9}[band]:
        action = action_pool[_stable_index((seed, "action-pick"), len(action_pool))]
        text = f"{action} {text}"

    return text


RENDERERS = {"agent_owen": _render_owen, "agent_priya": _render_priya, "agent_owen_twin": _render_owen}


@dataclass
class PersonaSession:
    persona_key: str
    # A fresh random value per playthrough. Without this, every new session
    # asking the same first questions produced byte-identical output forever
    # — everything was keyed only on (persona, turn number, exact question
    # text), with no notion of "which playthrough is this". Mixed into every
    # stable_index pick (fillers, hedges, body language, deflect-line choice,
    # and which `opening` variant plays), so a replay's *delivery* varies
    # even when it asks the same questions in the same order.
    session_seed: str = field(default_factory=lambda: secrets.token_hex(4))
    ask_counts: dict = field(default_factory=dict)
    pressure: float = 0.0
    turn: int = 0
    history: list = field(default_factory=list)
    consecutive_unmatched: int = 0
    # Layer 6 (ENGINE_SPEC.md §8): every fact with a time_reference that's
    # actually been revealed this session, logged as {topic: minutes} — the
    # tension detector may only reason over claims the player has already
    # earned, never ones authored-but-unasked.
    claims: dict = field(default_factory=dict)
    # Layer 2 (ENGINE_SPEC.md §4), finally wired into a running session: the
    # full claim log (topic + rendered text, not just time), for Layer 7 to
    # optionally reason over. `subject` is always SELF here — this sandbox
    # doesn't need Layer 3 entity resolution to log "what was said", only to
    # resolve "who a third-party question is about", which this never does.
    claim_store: claims_mod.ClaimStore = field(default_factory=claims_mod.ClaimStore)

    @property
    def persona(self):
        return PERSONAS[self.persona_key]

    def pressure_band(self) -> int:
        if self.pressure >= 0.85:
            return 3
        if self.pressure >= 0.55:
            return 2
        if self.pressure >= 0.25:
            return 1
        return 0

    def _match_fact(self, question_lower: str):
        persona = self.persona
        use_concepts = persona.get("matcher") == "concepts"
        present = concepts_mod.detected_concepts(question_lower) if use_concepts else None

        # Keyword engine scores by total matched-phrase *length* (a specific
        # phrase like "partnership letter" must outrank a shorter, more
        # generic keyword like "partnership" that happens to appear as a
        # substring of it). Concept engine scores by *count of concepts
        # matched* (a 2-concept hit like BUSY+WORK must outrank a 1-concept
        # hit) — a coarser, integer scale, so ties are more common than in
        # the keyword engine; that's a real, disclosed trade-off, not a bug.
        best_fact = None
        best_score = 0
        for fact in persona["facts"]:
            gate_topic = fact.get("gate_topic")
            if gate_topic and self.ask_counts.get(gate_topic, 0) < fact.get("gate_min_ask", 1):
                continue
            # Entity guard: a fact answering "your relationship with Marcus" /
            # "your reaction" must not fire when the question is actually
            # about a different named person ("what was ISABELLA's reaction")
            # — pattern-matching on topic shape alone doesn't check *who* the
            # question is about, and confidently answering as if it were
            # about the wrong person is worse than an honest miss.
            if use_concepts:
                exclude = fact.get("exclude_concepts")
                if exclude and (exclude & present.keys()):
                    continue
                score = concepts_mod.concept_group_score(fact["concept_groups"], present)
            else:
                exclude_kw = fact.get("exclude_keywords")
                if exclude_kw and _kw_score(exclude_kw, question_lower) > 0:
                    continue
                score = _kw_score(fact["keywords"], question_lower)
            if score > best_score:
                best_score = score
                best_fact = fact
        return best_fact, best_score

    def _is_confrontational(self, question_lower: str) -> bool:
        return any(_kw_present(w, question_lower) for w in CONFRONTATIONAL_WORDS)

    def _check_tension(self, question: str, question_norm: str, seed: str) -> dict | None:
        """Layer 6 (ENGINE_SPEC.md §8): fires only when the question
        references the times of two claims already revealed *this session*
        — arithmetic on facts the player already earned, never new
        information, and never triggered by claims still locked."""
        templates = self.persona.get("tension_response")
        if not templates:
            return None
        refs = _find_time_refs(question_norm)
        if len(refs) < 2:
            return None
        revealed = set(self.claims.values())
        matched = refs & revealed
        if len(matched) < 2:
            return None
        gap = max(matched) - min(matched)
        idx = _stable_index((self.session_seed, "tension"), len(templates))
        text = templates[idx].format(gap=gap)
        self.pressure = min(1.0, self.pressure + 0.15)
        rendered = RENDERERS[self.persona["agent_id"]](text, self.pressure_band(), seed, 0)
        return self._finish(question, rendered, topic="tension")

    def ask(self, question: str) -> dict:
        self.turn += 1
        q_lower = question.lower()
        q_norm = _normalize(q_lower)
        confrontational = self._is_confrontational(q_norm)
        persona = self.persona
        seed = f"{self.persona_key}:{self.session_seed}:{self.turn}:{question}"

        tension = self._check_tension(question, q_norm, seed)
        if tension is not None:
            return tension

        # Small-talk candidate: same length-weighted best match as facts,
        # e.g. "how are you holding up" must beat the shorter, more generic
        # "hi" inside an opening "Hi, how are you...". Small talk used to
        # unconditionally win whenever it scored *anything*, which let a
        # short fragment like "you ok" inside "did he pay you ok" steal a
        # question that a fact ("pay you" -> work_quality) fit better — so
        # small talk and facts now compete on the same score, not on which
        # one gets checked first.
        use_concepts = persona.get("matcher") == "concepts"
        small_talk_hit = None
        best_st_score = 0
        if use_concepts:
            present = concepts_mod.detected_concepts(q_norm)
            for key, concept_names in concepts_mod.SMALL_TALK_CONCEPTS.items():
                score = concepts_mod.concept_group_score([frozenset(concept_names)], present)
                if score > best_st_score:
                    best_st_score = score
                    small_talk_hit = key
        else:
            for key, phrases in SMALL_TALK_KEYWORDS.items():
                score = _kw_score(phrases, q_norm)
                if score > best_st_score:
                    best_st_score = score
                    small_talk_hit = key

        fact, fact_score = self._match_fact(q_norm)

        if small_talk_hit and small_talk_hit in persona["small_talk"] and best_st_score >= fact_score:
            variants = persona["small_talk"][small_talk_hit]
            repeat_count = self.ask_counts.get(f"smalltalk_{small_talk_hit}", 0)
            self.ask_counts[f"smalltalk_{small_talk_hit}"] = repeat_count + 1
            base_text = variants[min(repeat_count, len(variants) - 1)]
            self.pressure = min(1.0, self.pressure + 0.01)
            rendered = RENDERERS[persona["agent_id"]](
                base_text, self.pressure_band(), seed, repeat_count
            )
            return self._finish(question, rendered, topic=f"smalltalk_{small_talk_hit}")

        if fact is None:
            # A question landing outside the fact bank is not automatically
            # hostile ground — "did he like your work?" is a perfectly
            # reasonable follow-up with no authored fact behind it, and
            # snapping "ask me something that matters" at it reads as the
            # character being combative for no reason. Reserve the sharp
            # pool for actual confrontation or for fishing (several
            # unmatched questions in a row); a single stray question gets a
            # mild, in-character "don't know / not going there" instead.
            if confrontational:
                pool = persona["deflect_confrontational"]
                self.pressure = min(1.0, self.pressure + 0.1)
            elif self.consecutive_unmatched >= 2:
                pool = persona["deflect_unmatched"]
                self.pressure = min(1.0, self.pressure + 0.05)
            else:
                pool = persona["deflect_mild"]
                self.pressure = min(1.0, self.pressure + 0.01)
            self.consecutive_unmatched += 1
            idx = _stable_index((seed, "deflect"), len(pool))
            rendered = RENDERERS[persona["agent_id"]](pool[idx], self.pressure_band(), seed, 0)
            return self._finish(question, rendered, topic=None)

        self.consecutive_unmatched = 0
        topic = fact["topic"]
        repeat_count = self.ask_counts.get(topic, 0)
        self.ask_counts[topic] = repeat_count + 1

        if fact.get("time_reference") is not None:
            self.claims[topic] = fact["time_reference"]

        bump = 0.04
        if fact.get("sensitive"):
            bump += 0.15
        if fact.get("accusation"):
            bump += 0.35  # being told to your face you're the killer outweighs everything else
        if confrontational:
            bump += 0.12
        if fact.get("truthfulness") == "false":
            bump += 0.05  # lying costs composure even when it lands clean
        self.pressure = min(1.0, self.pressure + bump)

        if repeat_count == 0:
            # First time this topic comes up *this session*: pick among the
            # equally-complete opening variants using the playthrough seed
            # (not the per-turn seed) — same choice all conversation long if
            # you ask again out of order, different choice on a fresh
            # session's replay.
            opening = fact["opening"]
            idx = _stable_index((self.session_seed, "opening", topic), len(opening))
            fact_text = opening[idx]
            # Log the claim once, on first reveal — a repeat restates an
            # existing claim, it isn't a new one Layer 7 should get to cite
            # again as if it were freshly earned.
            fact_obj = claims_mod.fact_from_legacy(fact, subject=claims_mod.SELF)
            self.claim_store.record(fact_obj, persona["agent_id"], fact_text)
        else:
            repeat_texts = fact["repeat"]
            fact_text = repeat_texts[min(repeat_count - 1, len(repeat_texts) - 1)]
        rendered = RENDERERS[persona["agent_id"]](
            fact_text, self.pressure_band(), seed, repeat_count
        )
        return self._finish(question, rendered, topic=topic, fact=fact)

    def _finish(self, question: str, answer: str, topic: str | None, fact: dict | None = None) -> dict:
        self.history.append(("detective", question))
        self.history.append((self.persona_key, answer))
        emotion = (fact or {}).get("emotion", "neutral")
        band = BAND_NAMES[self.pressure_band()]
        return {
            "answer": answer,
            "topic": topic,
            "truthfulness": (fact or {}).get("truthfulness"),
            # Presentation metadata is deliberately derived only from the
            # already-selected, player-safe fact and session pressure.  A
            # face renderer must never receive hidden case state as a handy
            # shortcut for deciding how a suspect should look.
            "emotion": emotion,
            "pressure": round(self.pressure, 3),
            "band": band,
            "performance": _performance_for(self.persona_key, band, topic, emotion),
        }
