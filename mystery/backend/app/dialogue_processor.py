import hashlib
from typing import Optional
from .models import Agent
from .behavioural_tells import pressure_band


def _stable_index(seed_parts, length: int) -> int:
    """Deterministic pick, same pattern as behavioural_tells._stable_index.

    Humanizing filters used to call `random` directly, which meant the same
    character's manner flickered from one answer to the next instead of
    reading as a consistent voice, and made playtests non-reproducible. Every
    choice below is instead a stable hash of (agent, seed, ...call-site
    context), so a given question to a given agent always renders the same
    way, and re-asking (a new seed) can render differently on its own terms.
    """
    seed = "|".join(str(part) for part in seed_parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % length


# ---------------------------------------------------------------------------
# Voice-card archetypes
#
# `Agent.voice_card` is authored specifically as a speech-mannerism
# description, but the deterministic (no-LLM) path never read it — only the
# LLM rewrite prompts did. Hand-authored cases reuse a small, fairly closed
# library of voice_card phrasings (see cases 001-007), so a bounded keyword
# match against that phrasing is a reliable signal, not a guess at arbitrary
# prose. Unmatched or absent voice_card (procedurally generated agents, minor
# cast without one) falls through to the old dial-based heuristics below —
# this is a bonus layer, never a requirement.
# ---------------------------------------------------------------------------

_ARCHETYPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("decisive", ("ledgers and verdicts", "ledger")),
    ("clipped", ("clipped", "clips her sentence", "clips his sentence")),
    ("rambling", ("rambles", "over-explain")),
    ("measured", ("measured", "rehearsed")),
    ("blunt", ("blunt", "no hedging")),
    ("soft_spoken", ("soft-spoken", "trails off", "qualifies everything")),
    ("sparing", ("speaks sparingly", "answers exactly the question")),
    ("warm_evasive", ("warm and talkative", "goes vague")),
    ("plain_anxious", ("plain, direct answers", "looking for reassurance")),
    ("legalistic", ("legal qualifications", "can and cannot be disclosed")),
    ("clinical", ("clinical",)),
    ("lecturing", ("lecturing", "rhetorical question")),
]

_ARCHETYPES: dict[str, dict[str, list[str]]] = {
    "decisive": {
        "fillers": [],
        "actions": ["*[States it like a ruling.]*", "*[Doesn't leave room for a follow-up.]*"],
        "deflect": [
            "That's my judgment on it, and I'll leave it there.",
            "I've said what I intend to say.",
            "That verdict's already in. I'm not revisiting it.",
        ],
    },
    "clipped": {
        "fillers": [],
        "actions": ["*[Answers without moving.]*", "*[Keeps their hands folded, still.]*"],
        "deflect": [
            "That's not something I discuss.",
            "I'd rather not elaborate.",
            "That's all I have to say on it.",
        ],
    },
    "rambling": {
        "fillers": ["So, right — ", "Oh, well — ", "Funny you ask, because — "],
        "actions": ["*[Gestures as they talk.]*", "*[Leans in, warming to the story.]*"],
        "deflect": [
            "Oh, I really couldn't say — best not to guess, don't you think?",
            "Honestly, I try to stay out of that sort of thing.",
            "I wouldn't know where to start with that one.",
        ],
    },
    "measured": {
        "fillers": ["Give me a moment. ", "Let me think about how to put this. "],
        "actions": ["*[Pauses before answering.]*", "*[Chooses the words carefully.]*"],
        "deflect": [
            "I'd rather choose my words on that more carefully, later.",
            "That's not something I want to answer without thinking it through.",
            "I won't answer that hastily.",
        ],
    },
    "blunt": {
        "fillers": [],
        "actions": ["*[Meets your eyes flatly.]*", "*[Doesn't soften it.]*"],
        "deflect": [
            "None of your business.",
            "Not answering that.",
            "Ask something that matters.",
        ],
    },
    "soft_spoken": {
        "fillers": ["I think... ", "Um, maybe — ", "I'm not sure, but — "],
        "actions": ["*[Looks down.]*", "*[Voice drops.]*"],
        "deflect": [
            "I really don't think I should say.",
            "I'm sorry, I'd rather not.",
            "I don't know that I can talk about that.",
        ],
    },
    "sparing": {
        "fillers": [],
        "actions": ["*[Answers, then stops.]*", "*[Offers nothing beyond the question asked.]*"],
        "deflect": [
            "No.",
            "Not something I'll go into.",
            "That's all there is to say.",
        ],
    },
    "warm_evasive": {
        "fillers": ["Oh, well, you know how it is — ", "Funny you'd ask — "],
        "actions": ["*[Brightens, then catches themselves.]*", "*[Waves a hand vaguely.]*"],
        "deflect": [
            "Oh, I really couldn't say — I try not to pry into people's business.",
            "That's getting a bit personal, isn't it?",
            "I wouldn't know anything about that, not really.",
        ],
    },
    "plain_anxious": {
        "fillers": ["Right, so — ", "Well, I— "],
        "actions": ["*[Looks for a nod back.]*", "*[Repeats himself, checking your face.]*"],
        "deflect": [
            "I don't know, is that— is that a problem?",
            "I've always tried to do right. Isn't that enough?",
            "Please, that's not something I can talk about.",
        ],
    },
    "legalistic": {
        "fillers": [],
        "actions": ["*[Chooses each word like it might be quoted back.]*"],
        "deflect": [
            "I'm not in a position to disclose that.",
            "I'd want to think about what I can and can't say there.",
            "That's not something I'll confirm or deny.",
        ],
    },
    "clinical": {
        "fillers": [],
        "actions": ["*[States it plainly, like a note.]*"],
        "deflect": [
            "That's outside what I observed.",
            "I have nothing recorded on that.",
            "Not something I can speak to.",
        ],
    },
    "lecturing": {
        "fillers": ["Well, as anyone could tell you — ", "Put simply — "],
        "actions": ["*[Raises a finger to make the point.]*", "*[Waits, as if for a slower student to catch up.]*"],
        "deflect": [
            "That's hardly worth discussing.",
            "I'd have thought that was obvious.",
            "Ask a better question.",
        ],
    },
}


def _voice_archetype(agent: Agent) -> Optional[str]:
    card = (agent.voice_card or "").lower()
    if not card:
        return None
    for archetype, keywords in _ARCHETYPE_KEYWORDS:
        if any(kw in card for kw in keywords):
            return archetype
    return None


def apply_repetition_frustration(text: str, count: int, agent: Agent, seed: str) -> str:
    if count == 2:
        prefixes = [
            "I already told you. ",
            "We just went over this. ",
            "As I said before, "
        ]
    elif count >= 3:
        prefixes = [
            "Are you even listening to me? ",
            "I don't know why you keep asking me that. ",
            "For the last time: "
        ]
    else:
        return text
    idx = _stable_index((agent.agent_id, seed, "repeat", count), len(prefixes))
    return prefixes[idx] + text


def apply_personality_fillers(text: str, agent: Agent, seed: str) -> str:
    archetype = _voice_archetype(agent)
    if archetype is not None:
        fillers = _ARCHETYPES[archetype]["fillers"]
        if not fillers:
            return text
        # Roughly half the time, same rate as the old dial-based defaults.
        if _stable_index((agent.agent_id, seed, "filler-roll"), 10) >= 5:
            return text
        idx = _stable_index((agent.agent_id, seed, "filler-pick"), len(fillers))
        return fillers[idx] + text

    # No authored voice_card matched (or none set) — fall back to the
    # dial-based heuristics that predate voice_card-aware flavoring.
    if agent.conflict_avoidance > 0.7:
        if _stable_index((agent.agent_id, seed, "nervous-filler"), 10) < 5:
            text = "Um... " + text
        if _stable_index((agent.agent_id, seed, "trail-off"), 10) < 3:
            text = text.replace(". ", "... ")

    if agent.honesty_baseline < 0.5:
        if _stable_index((agent.agent_id, seed, "stall-filler"), 10) < 4:
            text = "Well... " + text

    return text


def apply_body_language(text: str, agent: Agent, seed: str, pressure: float = 0.0) -> str:
    # How often a stage direction appears at all scales with pressure, so a
    # suspect's very first, calm answer doesn't open with "*[Wrings hands]*"
    # while the separate observable-tells panel correctly reports nothing —
    # the two systems used to be able to visibly contradict each other.
    band = pressure_band(pressure)
    show_threshold = {0: 3, 1: 5, 2: 7, 3: 8, 4: 9}[band]
    if _stable_index((agent.agent_id, seed, "body-roll"), 10) >= show_threshold:
        return text

    calm_actions = ["*[Nods]*", "*[Pauses]*", "*[Takes a breath]*"]
    archetype = _voice_archetype(agent)

    if band == 0:
        # At true baseline, keep it neutral regardless of personality — there
        # is nothing yet to read a nervous or hostile tell into.
        actions = calm_actions
    elif archetype is not None and _ARCHETYPES[archetype]["actions"]:
        actions = _ARCHETYPES[archetype]["actions"]
    elif agent.honesty_baseline < 0.5:
        actions = ["*[Avoids your gaze]*", "*[Shifts uncomfortably]*", "*[Looks away]*"]
    elif agent.conflict_avoidance < 0.3:
        actions = ["*[Crosses arms]*", "*[Glares]*", "*[Sighs impatiently]*"]
    elif agent.conflict_avoidance > 0.7:
        actions = ["*[Fidgets]*", "*[Looks down]*", "*[Wrings hands]*"]
    else:
        actions = calm_actions

    idx = _stable_index((agent.agent_id, seed, "body-pick"), len(actions))
    return f"{actions[idx]} {text}"


# Temperament deflection pools, for the cast with no recognisable voice card to
# derive an archetype from — 70 agents across the shipped cases, mostly
# background NPCs but not only. Hoisted to module level (rather than left inline
# in apply_deflection) so `ALL_CANNED_DEFLECTIONS` can enumerate the complete
# set of lines the deterministic path can produce: a no-leak test needs to
# recognise a canned refusal without hard-coding its wording, and one that knows
# only about _ARCHETYPES passes or fails depending on which agent it happens to
# interview.
_DEFLECTIONS_HOSTILE = [
    "That's none of your business.",
    "I don't see how that's relevant to anything.",
    "Ask a sensible question, Detective.",
]
_DEFLECTIONS_TIMID = [
    "I... I don't really know anything about that.",
    "Maybe you should ask someone else.",
    "I'm sorry, I can't help you with that.",
]
_DEFLECTIONS_NEUTRAL = [
    "I'd prefer not to discuss that.",
    "I have nothing to say on the matter.",
    "Let's stay focused on the facts, please.",
]

ALL_CANNED_DEFLECTIONS = frozenset(
    _DEFLECTIONS_HOSTILE
    + _DEFLECTIONS_TIMID
    + _DEFLECTIONS_NEUTRAL
    + [line for archetype in _ARCHETYPES.values() for line in archetype["deflect"]]
)


def apply_deflection(agent: Agent, seed: str = "deflect") -> str:
    # Called when trust is too low, or it's a fallback intent that they refuse to answer
    archetype = _voice_archetype(agent)
    if archetype is not None:
        options = _ARCHETYPES[archetype]["deflect"]
    elif agent.conflict_avoidance < 0.3:
        options = _DEFLECTIONS_HOSTILE
    elif agent.conflict_avoidance > 0.7:
        options = _DEFLECTIONS_TIMID
    else:
        options = _DEFLECTIONS_NEUTRAL
    idx = _stable_index((agent.agent_id, seed, "deflect-pick"), len(options))
    return options[idx]


def default_small_talk_line(agent: Agent, intent: str) -> str:
    """A per-agent default for small talk when the case has not authored one
    (`Agent.small_talk` is empty for most cast members in most cases), built
    only from fields every agent already has — occupation, first trait, and
    the numeric temperament dials — never a fixed vocabulary of specific
    trait words, since traits are freeform text authored per case. Replaces
    one universal "I don't have much to say about that." shared by every
    character in every case regardless of who they are."""
    occupation = agent.occupation.strip()
    article = "an" if occupation[:1].lower() in "aeiou" else "a"
    trait = agent.traits[0] if agent.traits else None

    if intent == "occupation":
        return f"I'm {article} {occupation}."
    if intent == "favorite_thing":
        base = f"Can't say I've got much time for hobbies, between the {occupation.lower()} and everything else."
        if trait:
            return f"{base} Ask around and people would call me {trait} before anything else."
        return base
    if intent == "about_me":
        first_name = agent.full_name.split()[0]
        base = f"I'm {first_name}, {article} {occupation.lower()} here."
        if trait:
            return f"{base} {trait.capitalize()}, if you ask anyone who knows me."
        return base
    if intent == "general_relationships":
        if agent.conflict_avoidance > 0.65:
            return "I keep out of most people's business, truth be told."
        if agent.gossip_tendency > 0.65:
            return "You hear things, working where I do. I don't chase it, but it finds you."
        return "I get on well enough with most people around here."
    if intent == "emotions":
        if agent.conflict_avoidance > 0.65:
            return "I'd rather keep things calm than make a show of how I feel."
        return "I don't make a show of it, but today's been hard on everyone."
    if intent == "how_are_you":
        if agent.conflict_avoidance > 0.65:
            return "As well as can be expected, I suppose. I'd rather just get on with it."
        return "Shaken, if I'm honest. It's not every day something like this happens."
    return "I don't have much to say about that."


def humanize_response(text: str, agent: Agent, count: int, seed: str = "", pressure: float = 0.0) -> str:
    """Passes deterministic text through humanizing filters."""
    text = apply_repetition_frustration(text, count, agent, seed)
    text = apply_personality_fillers(text, agent, seed)
    text = apply_body_language(text, agent, seed, pressure)
    return text


# ---------------------------------------------------------------------------
# Stall fillers — covering generation latency without lying to the player
# ---------------------------------------------------------------------------
# A rewrite takes ~1.5s on a good local model and occasionally much longer. Dead
# air reads as a machine thinking; a line of speech reads as a person. So the UI
# can play one of these the instant a question is asked and swap in the real
# answer when it lands.
#
# The constraint that shapes every line below is specific to this game, and it
# is why these are NOT the deflections in `_ARCHETYPES[...]["deflect"]`.
# Hesitation here is *diegetic evidence*: `Agent.baseline`, the pressure bands,
# and `observable_tells` all teach the player to read hesitation as signal, and
# docs/17 makes that a deliberate authoring surface. If a suspect stalls because
# a GPU is busy and the player files it as evasion, the game has manufactured a
# tell out of infrastructure — unfair in a way a spinner never is, because it is
# not grounded in case truth and will not reproduce.
#
# Hence two rules, both enforced by tests:
#   1. A stall filler is never a deflection. "I'd rather not elaborate" is a
#      refusal and reads as guilt; "So — where was I" is a verbal tic and reads
#      as nothing.
#   2. A stall filler never varies with pressure, emotion, or session state.
#      `stall_fillers_for` takes only the agent, so a stall can carry no signal
#      about how the interview is going — structurally, not by convention.
#
# They stay in-voice per archetype, because a character who stalls in someone
# else's register is its own kind of tell.
_STALL_FILLERS: dict[str, list[str]] = {
    "decisive": ["Right.", "Let me be clear about this.", "One moment."],
    "clipped": ["Hm.", "One moment.", "Right."],
    "rambling": ["Oh — now, let me see.", "So, right, where do I start.", "Well now."],
    "measured": ["Let me think how to put this.", "Give me a moment.", "Hm — one second."],
    "blunt": ["Right.", "Hold on.", "Give me a second."],
    "soft_spoken": ["Oh — um.", "Let me think.", "Sorry, one moment."],
    "sparing": ["Hm.", "One moment.", "Give me a second."],
    "warm_evasive": ["Oh, let me see now.", "Well.", "Give me a moment."],
    "plain_anxious": ["Um — let me think.", "Sorry, one second.", "Right, um."],
    "legalistic": ["Let me be precise about this.", "One moment.", "Let me think."],
    "clinical": ["One moment.", "Let me recall.", "Hm."],
    "lecturing": ["Well now.", "Let me put it this way.", "One moment."],
}

# Anyone whose voice card matches no archetype still needs something to say.
_STALL_FILLERS_DEFAULT: list[str] = ["One moment.", "Let me think.", "Hm."]

ALL_STALL_FILLERS = frozenset(
    line for pool in _STALL_FILLERS.values() for line in pool
) | frozenset(_STALL_FILLERS_DEFAULT)


def stall_fillers_for(agent: Agent) -> list[str]:
    """In-voice lines the UI may play while a rewrite is being generated.

    Takes the agent and nothing else, deliberately: see the note above. A stall
    that varied with pressure would be a tell the case never authored.
    """
    archetype = _voice_archetype(agent)
    return list(_STALL_FILLERS.get(archetype, _STALL_FILLERS_DEFAULT))
