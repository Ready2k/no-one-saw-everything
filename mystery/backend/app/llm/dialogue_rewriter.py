"""LLM dialogue rewriting module."""

# import json  # UNUSED — commented out during code review [2026-07-19]
import random
import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

from pydantic import BaseModel

from .client import get_llm_client
from . import rewrite_cache
from .numeric_fidelity import time_fidelity_violation
from .schemas import DialogueRewrite
from ..danger_table import (
    MAX_SOURCE_CLAIMS,
    DangerTable,
    get_danger_table,
    pair_key,
    places_someone,
)
from ..models import CaseData, Agent, Claim
from ..session import Session

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

class RewriteResult(BaseModel):
    rewritten_text: str
    fallback_used: bool
    fallback_reason: Optional[str] = None
    # Echoed back for the transcript/telemetry: which claims the model said it
    # used. Empty whenever the rewrite fell back, since a rejected rewrite's
    # citations are not something to record as though they were honoured.
    source_claim_ids: list[str] = []


@dataclass(frozen=True)
class CitationContext:
    """What `_citation_leak` needs to grade a rewrite's declared sources.

    `required` is the difference between the two regimes. When Layer 7 is off,
    the model is handed one pre-computed answer and no claim history, so it has
    nothing to cite and silence means nothing — but a citation it volunteers is
    still checked, because a model that names two claims is telling us what it
    combined whether or not we asked. When Layer 7 is on, the claim history went
    into the prompt and citations were demanded, so silence is a model that
    reasoned across the history and declined to say from where. §9.3 calls that
    maximally dangerous, and it is refused.
    """

    citable: dict[str, Claim]
    danger: DangerTable
    required: bool = False


def _citation_leak(
    source_claim_ids: Optional[List[str]], ctx: CitationContext
) -> Optional[str]:
    """Layer 7 §9.2–§9.4: is this rewrite's declared pair of sources safe?

    An O(1) lookup against the offline table, plus the two structural rules
    that make a table of *pairs* sufficient — the hard cap at two sources, and
    the carve-out that refuses a time/location pair outright.

    `None` (field absent) and `[]` (explicitly "I drew on none of them") are
    different answers and are graded differently — see `DialogueRewrite`.
    """
    if source_claim_ids is None and ctx.required:
        return "claim-grounded rewrite declared no sources"

    seen: set[str] = set()
    ids: List[str] = []
    for raw in source_claim_ids or []:
        cid = (raw or "").strip()
        if cid and cid not in seen:
            seen.add(cid)
            ids.append(cid)

    # §9.3 — the cap is what keeps the danger table pairwise. A barrister has to
    # build a combination across several turns rather than in one model leap.
    if len(ids) > MAX_SOURCE_CLAIMS:
        return f"cited {len(ids)} claims (cap {MAX_SOURCE_CLAIMS})"

    # A source that is not one of the claims we offered is a fabricated
    # citation, and there is no table entry that could vouch for it.
    unknown = [cid for cid in ids if cid not in ctx.citable]
    if unknown:
        return f"cited unknown claim(s): {', '.join(sorted(unknown))}"

    if not ids:
        # An explicit [] survives here. It is the honest answer for the common
        # case — a rewrite that restates one grounded line and rests on no prior
        # claim — and check 4b's live text scan still runs over the prose, so an
        # undeclared combination is caught on its words rather than its silence.
        return None

    if len(ids) < 2:
        # One claim cannot be a combination; the single-fact checks above own it.
        return None

    a, b = ctx.citable[ids[0]], ctx.citable[ids[1]]

    # §9.4 — identity narrowed by time and place is Layer 6's question, settled
    # deterministically by testimony.py. Layer 7 never gets to answer it.
    if places_someone(a) and places_someone(b):
        return "cited two time/location claims (Layer 6 scope)"

    facet = ctx.danger.get(pair_key(ids[0], ids[1]))
    if facet:
        return f"cited a combination that gives away {facet}"

    return None


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text("utf-8")


def _build_forbidden_facts(case: CaseData, agent: Agent) -> list[str]:
    """Extract hidden facts (full sentences/claims) that should never leak.

    Deliberately excludes solution.motive/method/opportunity.concept_groups —
    those are individual short words ("till", "mother", "committee"), not
    facts, and are handled separately by _build_concept_facets/_sanitise's
    group-count check. A word this common cannot be banned outright (an
    unrelated agent saying "my mother" in passing is not a leak), but the
    *combination* the solution actually scores on is."""
    forbidden = []

    # Hidden roles
    if case.solution.killer_id == agent.agent_id:
        forbidden.append(f"{agent.full_name} is the killer.")

    for conclusion in case.conclusions:
        forbidden.append(conclusion.summary)

    for mem in case.memories:
        if mem.owner_agent_id == agent.agent_id and mem.truth_status != "true":
            forbidden.append(mem.summary)

    return forbidden


def _build_concept_facets(case: CaseData) -> list[tuple[str, list[list[str]], int]]:
    """(facet name, concept_groups, min_groups) for motive/method/opportunity —
    the exact vocabulary/threshold judge.py uses to score a free-text
    accusation as correct (a facet counts once >= min_groups distinct groups
    are matched). _sanitise applies the identical threshold to a rewrite: one
    stray word from one group is unremarkable, but hitting enough distinct
    groups to itself count as a correct accusation is the model leaking the
    answer key, regardless of phrasing."""
    return [
        ("motive", case.solution.motive.concept_groups, case.solution.motive.min_groups),
        ("method", case.solution.method.concept_groups, case.solution.method.min_groups),
        ("opportunity", case.solution.opportunity.concept_groups, case.solution.opportunity.min_groups),
    ]


def _concept_combination_leak(
    text_lower: str,
    allowed_blob: str,
    concept_facets: list[tuple[str, list[list[str]], int]],
) -> Optional[str]:
    """True if `text_lower` hits enough distinct concept groups from any
    facet to itself clear that facet's min_groups bar — i.e. paraphrases the
    solution's answer key in its own grading vocabulary (see _sanitise's 4b
    for the full rationale). Shared by _sanitise and belief_updater's
    talking-point filter, which has the same forbidden-fact surface but
    never routes through _sanitise itself."""
    for facet_name, groups, min_groups in concept_facets:
        if not groups:
            continue
        matched_groups = 0
        for group in groups:
            hit = False
            for word in group:
                word_lower = word.lower().strip()
                if not word_lower or word_lower in allowed_blob:
                    continue
                pattern = rf"\b{re.escape(word_lower)}\b"
                if re.search(pattern, text_lower):
                    hit = True
                    break
            if hit:
                matched_groups += 1
        # Cap the bar at how many groups actually exist: a facet authored
        # with fewer groups than its own min_groups (or a single very
        # specific group) must still be reachable, not silently unblockable.
        threshold = max(1, min(min_groups, len(groups)))
        if matched_groups >= threshold:
            return f"{facet_name} ({matched_groups}/{len(groups)} concept groups)"
    return None


def _sanitise(
    text: str,
    forbidden_facts: list[str],
    allowed_facts: list[str],
    case: CaseData,
    allowed_context: list[str],
    concept_facets: Optional[list[tuple[str, list[list[str]], int]]] = None,
    source_claim_ids: Optional[List[str]] = None,
    citation: Optional[CitationContext] = None,
) -> Optional[str]:
    """
    Sanitises LLM text.
    Returns a rejection reason if invalid, else None.
    """
    # 0. Blank text. A syntactically valid but empty rewritten_text (a model
    # confused by an adversarial or off-topic question sometimes emits
    # {"rewritten_text": ""}) trivially passes every other check below —
    # nothing forbidden appears in an empty string — and would otherwise
    # reach the player as a blank chat bubble instead of falling back to the
    # canned deflection.
    if not text.strip():
        return "Empty rewrite"

    text_lower = text.lower()
    allowed_blob = " ".join(allowed_facts + allowed_context).lower()

    # 1. Role labels
    bad_labels = ["killer", "red_herring", "victim_role"]
    for label in bad_labels:
        if label in text_lower:
            return f"Contains raw role label: {label}"

    # 2. JSON leakage
    if "{" in text or "}" in text:
        return "Contains JSON syntax or schema leakage"

    # 3. Hidden Event IDs / Clue IDs
    # Rather than checking all IDs, we just look for typical ID formats if they leak,
    # but more robustly, we just check forbidden facts.

    # 4. Forbidden facts (single sentences/claims: the killer label sentence,
    # conclusion summaries, an agent's own lies)
    # Word-boundary match rather than a raw substring check, so a short entry
    # can't false-positive inside an unrelated word — the same style already
    # used for VIOLENCE_TERMS and agent names below.
    #
    # Exempt any forbidden phrase that is already visible in the deterministic
    # text/allowed context being rewritten: that word overlap is the scripted
    # answer doing its job, not the model smuggling in a new fact, so a
    # faithful paraphrase must not be rejected for reusing wording the player
    # could already see.
    for fact in forbidden_facts:
        fact_lower = fact.lower().strip()
        if not fact_lower or fact_lower in allowed_blob:
            continue
        pattern = rf"\b{re.escape(fact_lower)}\b"
        if re.search(pattern, text_lower):
            return f"Contains forbidden fact: {fact}"

    # 4b. Forbidden fact *combinations* — see _concept_combination_leak.
    leak = _concept_combination_leak(text_lower, allowed_blob, concept_facets or [])
    if leak:
        return f"Contains forbidden fact combination: {leak}"

    # 4c. Layer 7 §9.2 — the same question asked of the model's declared
    # *sources* rather than its finished prose. 4b and 4c deliberately both run
    # (§9.3): 4b catches a model that paraphrases into the grading vocabulary
    # without honestly citing what it combined, and 4c catches the reverse — a
    # model that combines two claims into an inference phrased carefully enough
    # to stay out of 4b's vocabulary. Neither is a superset of the other.
    if citation is not None:
        cite_leak = _citation_leak(source_claim_ids, citation)
        if cite_leak:
            return f"Unsafe claim citation: {cite_leak}"

    # 5. Unsupported facts
    # The rewrite may not introduce cast members that the grounded answer never
    # mentioned — that's how hallucinated sightings get invented. A name is only
    # allowed if it appears somewhere in the deterministic answer, the allowed
    # facts, or the question/claim context. Word-boundary match so "Ben" does
    # not trip on "been".
    for agent in case.agents:
        first_name = agent.full_name.split()[0].lower()
        pattern = rf"\b{re.escape(first_name)}\b"
        if re.search(pattern, text_lower) and not re.search(pattern, allowed_blob):
            return f"Contains unsupported fact: {agent.full_name.split()[0]}"

    # 6. Ungrounded violence vocabulary — the invented-confession guard.
    # A model can break character and confess on an agent's behalf ("Fine — I
    # killed him") without using any role label or authored forbidden phrase.
    # Words of killing are only allowed when the grounded text being rewritten
    # (or the visible context) already uses them — an authored confession beat
    # says "killed" and its paraphrase may too; a calm alibi answer must not
    # suddenly acquire the word. Word-boundary match so "skilled" never trips
    # "killed".
    # term -> stem: the term is allowed when its stem already appears anywhere
    # in the visible context ("murder window" in the question grounds
    # "murdered"; an authored "killed" grounds a paraphrased "kill").
    VIOLENCE_TERMS = {
        "kill": "kill", "killed": "kill", "killing": "kill",
        "murdered": "murder", "murdering": "murder",
        "strangled": "strangl", "stabbed": "stab", "poisoned": "poison",
        "i did it": "did it", "it was me": "it was me",
    }
    for term, stem in VIOLENCE_TERMS.items():
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, text_lower) and stem not in allowed_blob:
            return f"Contains ungrounded violence vocabulary: {term}"

    # 7. Factual fidelity of times — the one check here that is not about what
    # the rewrite was *allowed* to say, but whether what it said is still true
    # to its source. A shifted arrival leaks nothing and passes checks 1-6, yet
    # corrupts the timeline the player reasons from, on which `testimony.py`
    # calls bilocation at five minutes' tolerance. See numeric_fidelity.
    drift = time_fidelity_violation(
        text_lower, allowed_blob, [a.full_name.split()[0] for a in case.agents]
    )
    if drift:
        return f"Alters a time from the grounded answer: {drift}"

    return None


def _build_citation_context(
    case: CaseData, claim_history: Optional[list[Claim]]
) -> tuple[Optional[CitationContext], str]:
    """Turn the agent's recorded statements into (a) what the sanitiser grades
    citations against and (b) the id-tagged list the prompt shows the model.

    Callers supply `claim_history` only on a claim-grounded turn with Layer 7
    configured on, so its presence *is* the signal that citations were asked
    for and are therefore required (§9.3). An ordinary flavour rewrite passes
    None and gets the old behaviour exactly.
    """
    citable = {c.claim_id: c for c in (claim_history or []) if c.claim_id}
    if not citable:
        return None, "None"

    block = "\n".join(f"- [{cid}] {c.claim_text}" for cid, c in citable.items())
    return CitationContext(citable=citable, danger=get_danger_table(case), required=True), block


def _format_world_state(world_state: Optional[list[str]]) -> str:
    """World-state digest lines (spec 15 Phase A). Deliberately *not* added
    to the sanitiser's allowed context: the digest is atmosphere the model
    may allude to, but parroting its specifics (another suspect's name, a
    broken claim's content) back as first-person testimony must still be
    rejected by the unsupported-fact / forbidden-fact checks."""
    if not world_state:
        return "None"
    return "- " + "\n- ".join(world_state)


def _voice_card(agent: Agent) -> str:
    return agent.voice_card or "No particular mannerisms."


# Said when the agent is about to repeat a line the player has already heard. Rotated so a long
# interrogation doesn't hear the same stock phrase twice, and tiered by how hard the player is
# pressing.
_REPEAT_OPENERS_CALM = [
    "I've told you this already.",
    "As I said before.",
    "You've asked me that.",
    "Same answer as last time.",
]
_REPEAT_OPENERS_PRESSED = [
    "I'm not going to say it differently just because you ask it twice.",
    "You can keep asking. It doesn't change.",
    "Asking again won't make it a different morning.",
    "I've given you my answer. I'll give it to you again, word for word, if that helps.",
]


def _diegetic_fallback(
    deterministic_text: str,
    pressure_level: float,
    outcome: str | None = None,
    is_repeat: bool = False,
) -> str:
    """Return the authored line, framed as an interview beat only when that is what is happening.

    This wrapper used to fire on PRESSURE: once an agent was pressed past 0.3, every subsequent
    answer was prefixed "That's all I'll say about that:" — the same phrase, every time, whether
    or not the line was new. Because the wrapper also fires whenever the LLM rewrite is simply
    unavailable (and the default config points at a host that may not exist), that is what the
    game actually did out of the box:

        Q(relationship):     "That's all I'll say about that: He was exacting..."
        Q(last_seen_victim): "That's all I'll say about that: About twenty to eight..."
        Q(alibi):            "That's all I'll say about that: I was at the fountain..."

    Three identical prefixes in a row, several of them contradicting the line they introduce.

    The wrapper's real job is to stop a REPEATED line reading as a broken feature — so it now
    fires on repetition, not on pressure. A first-time answer is new information and is returned
    exactly as authored. A `contradiction_locked` outcome is the killer breaking, and is never
    adorned.
    """
    if outcome == "contradiction_locked":
        return deterministic_text
    if not is_repeat:
        return deterministic_text

    pool = _REPEAT_OPENERS_PRESSED if pressure_level >= 0.4 else _REPEAT_OPENERS_CALM
    opener = pool[hash(deterministic_text) % len(pool)]
    return f"{opener} {deterministic_text}"


def rewrite_interview_answer(
    case: CaseData,
    agent: Agent,
    question_text: str,
    deterministic_text: str,
    allowed_facts: list[str],
    pressure_level: float,
    recent_exchange: Optional[list[str]] = None,
    emotion: str = "neutral",
    world_state: Optional[list[str]] = None,
    is_repeat: bool = False,
    session: Optional[Session] = None,
    claim_history: Optional[list[Claim]] = None,
) -> RewriteResult:

    if session is not None and session.llm_unavailable:
        return RewriteResult(
            rewritten_text=_diegetic_fallback(deterministic_text, pressure_level, is_repeat=is_repeat),
            fallback_used=True,
            fallback_reason="provider_unavailable"
        )

    system_prompt = _load_prompt("dialogue_rewrite_system.txt")
    user_prompt_template = _load_prompt("interview_rewrite_user.txt")

    forbidden_facts = _build_forbidden_facts(case, agent)
    concept_facets = _build_concept_facets(case)

    # Layer 7. `claim_history` is only supplied when claim reasoning is
    # configured on; when it is absent the model is handed no history, so
    # `required` stays False and a rewrite that cites nothing is simply the
    # ordinary flavour rewrite this function has always done.
    citation, claim_history_block = _build_citation_context(case, claim_history)

    user_prompt = user_prompt_template.format(
        claim_history=claim_history_block,
        name=agent.full_name,
        occupation=agent.occupation,
        traits=", ".join(agent.traits),
        voice_card=_voice_card(agent),
        emotion=emotion or "neutral",
        pressure_level=pressure_level,
        question_text=question_text,
        recent_exchange="\n".join(recent_exchange) if recent_exchange else "None",
        world_state=_format_world_state(world_state),
        allowed_facts="- " + "\n- ".join(allowed_facts) if allowed_facts else "None",
        forbidden_facts="- " + "\n- ".join(forbidden_facts) if forbidden_facts else "None",
        deterministic_text=deterministic_text
    )

    # Keyed on the *whole* turn plus the model that would answer it, so a hit is
    # only possible when nothing that could change the answer has changed. See
    # rewrite_cache: this can move latency, never content.
    from .config import get_llm_config as _cfg
    cfg = _cfg()
    cache_key = rewrite_cache.make_key(
        kind="interview",
        agent_id=agent.agent_id,
        question_text=question_text,
        deterministic_text=deterministic_text,
        allowed_facts=allowed_facts,
        pressure_level=pressure_level,
        recent_exchange=recent_exchange,
        emotion=emotion,
        world_state=world_state,
        is_repeat=is_repeat,
        claim_history=[c.claim_id for c in (claim_history or [])],
        model=(cfg.provider, cfg.base_url, cfg.model, cfg.claim_reasoning_enabled),
    )
    cached = rewrite_cache.get(cache_key)
    if cached is not None:
        return cached

    client = get_llm_client()
    try:
        result = client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=DialogueRewrite
        )

        # Prior displayed dialogue is already on the player's screen, so
        # echoing it back is continuity, not a new leak.
        allowed_context = [question_text, deterministic_text, agent.full_name]
        if recent_exchange:
            allowed_context.extend(recent_exchange)
        rejection = _sanitise(
            result.rewritten_text, forbidden_facts, allowed_facts, case, allowed_context,
            concept_facets=concept_facets,
            source_claim_ids=result.source_claim_ids,
            citation=citation,
        )
        if rejection:
            logger.warning(f"Rewrite rejected: {rejection}")
            return RewriteResult(
                rewritten_text=_diegetic_fallback(deterministic_text, pressure_level, is_repeat=is_repeat),
                fallback_used=True,
                fallback_reason="validation_failed"
            )

        accepted = RewriteResult(
            rewritten_text=result.rewritten_text,
            fallback_used=False,
            source_claim_ids=list(result.source_claim_ids or []),
        )
        # Only successes are stored: a fallback is a transient provider failure
        # or a sanitiser rejection worth re-attempting, and caching one would
        # freeze a single bad moment into every future turn like it.
        rewrite_cache.put(cache_key, accepted)
        return accepted

    except Exception as e:
        logger.warning(f"Rewrite failed: {e}")
        if session is not None:
            session.llm_unavailable = True
        return RewriteResult(
            rewritten_text=_diegetic_fallback(deterministic_text, pressure_level, is_repeat=is_repeat),
            fallback_used=True,
            fallback_reason="provider_error"
        )


def rewrite_challenge_response(
    case: CaseData,
    agent: Agent,
    challenged_claim: str,
    evidence_clues: str,
    player_statement: str,
    outcome: str,
    deterministic_text: str,
    allowed_facts: list[str],
    pressure_level: float,
    emotion: str = "neutral",
    world_state: Optional[list[str]] = None,
    session: Optional[Session] = None,
) -> RewriteResult:

    if session is not None and session.llm_unavailable:
        return RewriteResult(
            rewritten_text=_diegetic_fallback(deterministic_text, pressure_level, outcome),
            fallback_used=True,
            fallback_reason="provider_unavailable"
        )

    system_prompt = _load_prompt("dialogue_rewrite_system.txt")
    user_prompt_template = _load_prompt("challenge_rewrite_user.txt")

    forbidden_facts = _build_forbidden_facts(case, agent)
    concept_facets = _build_concept_facets(case)

    user_prompt = user_prompt_template.format(
        name=agent.full_name,
        occupation=agent.occupation,
        traits=", ".join(agent.traits),
        voice_card=_voice_card(agent),
        emotion=emotion or "neutral",
        pressure_level=pressure_level,
        world_state=_format_world_state(world_state),
        challenged_claim=challenged_claim,
        evidence_clues=evidence_clues,
        player_statement=player_statement or "None",
        outcome=outcome,
        allowed_facts="- " + "\n- ".join(allowed_facts) if allowed_facts else "None",
        forbidden_facts="- " + "\n- ".join(forbidden_facts) if forbidden_facts else "None",
        deterministic_text=deterministic_text
    )

    client = get_llm_client()
    try:
        result = client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=DialogueRewrite
        )

        allowed_context = [
            challenged_claim,
            evidence_clues,
            player_statement or "",
            deterministic_text,
            agent.full_name,
        ]
        rejection = _sanitise(
            result.rewritten_text, forbidden_facts, allowed_facts, case, allowed_context,
            concept_facets=concept_facets,
        )
        if rejection:
            logger.warning(f"Rewrite rejected: {rejection}")
            return RewriteResult(
                rewritten_text=_diegetic_fallback(deterministic_text, pressure_level, outcome),
                fallback_used=True,
                fallback_reason="validation_failed"
            )

        return RewriteResult(
            rewritten_text=result.rewritten_text,
            fallback_used=False
        )

    except Exception as e:
        logger.warning(f"Rewrite failed: {e}")
        if session is not None:
            session.llm_unavailable = True
        return RewriteResult(
            rewritten_text=_diegetic_fallback(deterministic_text, pressure_level, outcome),
            fallback_used=True,
            fallback_reason="provider_error"
        )


def _get_open_ended_deflection(pressure_level: float) -> str:
    if pressure_level >= 0.6:
        return random.choice([
            "I'm done playing these games. Stick to the point.",
            "Are you trying to be funny? Because I'm not laughing.",
            "I don't have to sit here and listen to this nonsense.",
            "Stop wasting my time with these questions."
        ])
    elif pressure_level >= 0.3:
        return random.choice([
            "I don't see what that's got to do with your investigation, detective.",
            "I'd rather stick to the matter at hand, if you don't mind.",
            "Is that really relevant right now?",
            "Let's stay focused on the case, shall we?"
        ])
    else:
        return random.choice([
            "I'm sorry, my mind is a bit elsewhere with everything that's happened.",
            "I'm not quite sure what you mean.",
            "Hmm, I don't really know what to say to that.",
            "I'm afraid I don't have a good answer for that right now."
        ])


def generate_open_ended_response(
    case: CaseData,
    agent: Agent,
    question_text: str,
    pressure_level: float,
    recent_exchange: Optional[list[str]] = None,
    world_state: Optional[list[str]] = None,
    session: Optional[Session] = None,
) -> RewriteResult:
    """Handles free-text questions that match none of the fixed interview
    intents (spec 06) — e.g. "tell me about your childhood". Rather than a
    static "I don't understand" message, lets the LLM improvise a genuinely
    in-character reply: flavour when the topic is harmless, an in-character
    refusal when it reaches for hidden case truth. There is no deterministic
    ground truth to rewrite here, so the model is never given the case truth
    as context — only the same forbidden-facts list and the same sanitiser
    used for grounded rewrites, which is what still blocks a leak or an
    invented relationship to another named suspect."""

    if session is not None and session.llm_unavailable:
        return RewriteResult(
            rewritten_text=_get_open_ended_deflection(pressure_level),
            fallback_used=True,
            fallback_reason="provider_unavailable",
        )

    system_prompt = _load_prompt("open_ended_system.txt")
    user_prompt_template = _load_prompt("open_ended_user.txt")

    forbidden_facts = _build_forbidden_facts(case, agent)
    concept_facets = _build_concept_facets(case)

    user_prompt = user_prompt_template.format(
        name=agent.full_name,
        occupation=agent.occupation,
        traits=", ".join(agent.traits),
        voice_card=_voice_card(agent),
        routine_summary=agent.routine_summary or "Unknown",
        pressure_level=pressure_level,
        recent_exchange="\n".join(recent_exchange) if recent_exchange else "None",
        world_state=_format_world_state(world_state),
        forbidden_facts="- " + "\n- ".join(forbidden_facts) if forbidden_facts else "None",
        question_text=question_text,
    )

    client = get_llm_client()
    try:
        result = client.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=DialogueRewrite,
        )

        allowed_context = [question_text, agent.full_name]
        if recent_exchange:
            allowed_context.extend(recent_exchange)
        rejection = _sanitise(
            result.rewritten_text, forbidden_facts, [], case, allowed_context,
            concept_facets=concept_facets,
        )
        if rejection:
            logger.warning(f"Open-ended response rejected: {rejection}")
            return RewriteResult(
                rewritten_text=_get_open_ended_deflection(pressure_level),
                fallback_used=True,
                fallback_reason="validation_failed",
            )

        return RewriteResult(rewritten_text=result.rewritten_text, fallback_used=False)

    except Exception as e:
        logger.warning(f"Open-ended response failed: {e}")
        if session is not None:
            session.llm_unavailable = True
        return RewriteResult(
            rewritten_text=_get_open_ended_deflection(pressure_level),
            fallback_used=True,
            fallback_reason="provider_error",
        )
