"""Deterministic behavioural observations for interviews and challenges.

These tells make interrogation feel observable without turning the UI into a
lie detector. The generator may use hidden truth to bias whether a cue appears,
but every returned cue is player-safe: visible behaviour only.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, Optional

from .models import Agent, BehaviouralBaseline, ObservableTell, QuestionType, TruthStatus


TELL_INTENSITIES = ("subtle", "noticeable", "strong")

# A suspect's calm manner: the thing the detective files away early and measures
# change against later. Chosen by seeded identity only — never by guilt — so the
# baseline itself can never leak who the killer is.
BASELINE_HABITS: list[tuple[str, str]] = [
    ("hands", "their hands do half the talking, carrying each answer along"),
    ("overexplaining", "they round every answer up into a small story, one detail more than you asked for"),
    ("timing", "they answer almost before the question is finished, quick and unguarded"),
    ("gaze", "they hold your eyes comfortably and let the silences sit"),
    ("voice", "their voice runs level and unhurried, like someone reading minutes"),
    ("posture", "they sit loose in the chair, taking up all the room they need"),
]

# One-to-one with BASELINE_HABITS: the "different from earlier" phrasing. Says
# that the manner has changed; never says why.
BASELINE_DEVIATION_CUES: dict[str, str] = {
    "hands": "The hands that carried their first answers along have gone flat and still.",
    "overexplaining": "The easy extra detail from their first answers has been trimmed to nothing.",
    "timing": "They used to answer before you had finished asking. Now every reply waits a beat.",
    "gaze": "They held your eyes when this began. They are finding other places to look now.",
    "voice": "The level, unhurried voice from earlier keeps having to be re-levelled.",
    "posture": "They sat loose when this began. Now they are arranged, joint by joint.",
}


def baseline_habit(agent: Agent, case_id: str) -> tuple[str, str, Optional[str]]:
    """(category, habit_text, deviation_cue) for this agent's calm manner.

    An authored spec on the agent wins — writers should give each principal a
    distinct manner; the seeded pick (stable per case) is the fallback so every
    generated or unauthored character still has one."""
    if agent.baseline is not None:
        return (
            agent.baseline.habit_category,
            agent.baseline.habit_text,
            agent.baseline.deviation_cue,
        )
    category, habit_text = BASELINE_HABITS[
        _stable_index((case_id, agent.agent_id, "baseline-habit"), len(BASELINE_HABITS))
    ]
    return category, habit_text, None


def pressure_band(pressure: float) -> int:
    """0 composed / 1 guarded / 2 rattled / 3 cornered / 4 breaking.

    Matches the frontend demeanour bands; baseline deviation is measured in band
    steps so it tracks what the player can already see on the meter."""
    if pressure >= 0.85:
        return 4
    if pressure >= 0.6:
        return 3
    if pressure >= 0.35:
        return 2
    if pressure >= 0.1:
        return 1
    return 0

FALSEY_TRUTH = {"false", "mistaken", "rumour"}
HIGH_STRESS = {
    "broken",
    "shattered",
    "breaking",
    "crumbling",
    "floundering",
    "cornered",
    "raw",
    "distressed",
    "rattled",
    "brittle",
    "defensive",
    "nervous",
    "shifty",
    "hardening",
    "fighting_hard",
}
LOW_STRESS = {"steady", "composed", "level", "warm", "fond", "amused", "clarifying"}


def _norm(value: Optional[str]) -> str:
    return (value or "").strip().lower().replace(" ", "_")


def _stable_index(seed_parts: Iterable[object], length: int) -> int:
    seed = "|".join(str(part) for part in seed_parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % length


def _tell_id(agent: Agent, source: str, seed: str, slot: int) -> str:
    digest = hashlib.sha1(f"{agent.agent_id}:{source}:{seed}:{slot}".encode("utf-8")).hexdigest()
    return f"tell_{digest[:10]}"


def _pick(agent: Agent, source: str, seed: str, options: list[tuple[str, str]]) -> tuple[str, str]:
    return options[_stable_index((agent.agent_id, source, seed), len(options))]


def _intensity(score: float) -> str:
    if score >= 1.6:
        return "strong"
    if score >= 0.75:
        return "noticeable"
    return "subtle"


# Shared with open_ended_tells below: small talk, unmatched questions, and an
# unevidenced confrontation have no truthfulness/emotional_shift to react to,
# but a suspect under pressure still shows something even answering those.
EVASIVE_TELLS: list[tuple[str, str]] = [
    ("gaze", "Their eyes leave yours for a beat before the answer arrives."),
    ("timing", "They answer a fraction too quickly, then repeat the detail as if setting it in place."),
    ("hands", "Their hands go still on the table while they give that detail."),
    ("overexplaining", "They add a tidy extra detail you did not ask for."),
]
EMOTIONAL_TELLS: list[tuple[str, str]] = [
    ("voice", "Their voice tightens around the last sentence."),
    ("posture", "Their shoulders pull in before they make themselves sit still again."),
    ("hands", "A thumb worries at a cuff seam while they keep talking."),
    ("gaze", "They glance away at the named place before looking back."),
]
STEADY_TELLS: list[tuple[str, str]] = [
    ("voice", "They take a breath and keep their voice carefully level."),
    ("posture", "They hold themselves very still, almost too deliberately."),
    ("timing", "They pause long enough to choose each word."),
]


def open_ended_tells(
    *, agent: Agent, pressure: float, seed: str, guarded: bool = False
) -> list[ObservableTell]:
    """0-1 observation for small talk, an unmatched question, or an
    unevidenced confrontation — paths with no deterministic truthfulness to
    react to. Driven by pressure alone: a composed suspect gives nothing
    away, a pressured one shows it even answering a harmless question.
    `guarded` marks a question the agent has real reason to dodge (a bluff
    or confrontation) even without hard evidence behind it."""
    stress = pressure + (0.2 if guarded else 0.0)
    if stress < 0.38:
        return []
    options = EVASIVE_TELLS if guarded else (EMOTIONAL_TELLS if stress >= 0.6 else STEADY_TELLS)
    category, cue = _pick(agent, "open-ended", seed, options)
    return [
        ObservableTell(
            tell_id=_tell_id(agent, "open-ended", seed, 0),
            agent_id=agent.agent_id,
            cue=cue,
            category=category,
            intensity=_intensity(stress),
            source="interview",
        )
    ]


def interview_tells(
    *,
    agent: Agent,
    question_type: QuestionType,
    truthfulness: TruthStatus,
    emotional_shift: Optional[str],
    pressure: float,
    seed: str,
    baseline: Optional[BehaviouralBaseline] = None,
    note_baseline_shift: bool = False,
) -> list[ObservableTell]:
    """Generate 0-2 observations for an interview answer.

    When `note_baseline_shift` is set (the first answer after the suspect enters a
    new pressure band), one tell is the baseline comparison — "different from
    earlier" — which lands even if the answer itself is too flat to cue anything."""

    emotion = _norm(emotional_shift)
    falsey = truthfulness in FALSEY_TRUTH
    emotionally_loud = emotion in HIGH_STRESS
    emotionally_quiet = emotion in LOW_STRESS or not emotion

    stress = pressure
    if falsey:
        stress += 0.45 + (1.0 - agent.honesty_baseline) * 0.25
    if emotionally_loud:
        stress += 0.35
    if question_type in {"alibi", "timeline", "evidence"}:
        stress += 0.12
    if emotionally_quiet and not falsey and pressure < 0.3:
        stress -= 0.25

    wants_baseline_tell = baseline is not None and note_baseline_shift
    if stress < 0.38 and not wants_baseline_tell:
        return []

    if falsey:
        options = EVASIVE_TELLS
    elif emotionally_loud:
        options = EMOTIONAL_TELLS
    else:
        options = STEADY_TELLS

    tells: list[ObservableTell] = []
    if stress >= 0.38:
        category, cue = _pick(agent, "interview", f"{seed}:{question_type}:{truthfulness}:{emotion}", options)
        tells.append(
            ObservableTell(
                tell_id=_tell_id(agent, "interview", seed, 0),
                agent_id=agent.agent_id,
                cue=cue,
                category=category,
                intensity=_intensity(stress),
                source="interview",
            )
        )

    if stress >= 1.45 and falsey:
        category2, cue2 = _pick(
            agent,
            "interview-extra",
            f"{seed}:{question_type}:{emotion}",
            [
                ("voice", "The denial lands flat, with no warmth behind it."),
                ("posture", "They lean back as soon as the answer is out."),
                ("gaze", "They check your face before deciding they have said enough."),
            ],
        )
        tells.append(
            ObservableTell(
                tell_id=_tell_id(agent, "interview", seed, 1),
                agent_id=agent.agent_id,
                cue=cue2,
                category=category2,
                intensity="noticeable",
                source="interview",
            )
        )

    if wants_baseline_tell:
        baseline_tell = ObservableTell(
            tell_id=_tell_id(agent, "interview-baseline", seed, 0),
            agent_id=agent.agent_id,
            cue=baseline.deviation_cue or BASELINE_DEVIATION_CUES[baseline.habit_category],
            category=baseline.habit_category,
            intensity="strong" if pressure >= 0.6 else "noticeable",
            source="interview",
        )
        # The comparison is the more valuable read: keep the 0-2 contract by
        # letting it displace the second generic cue.
        if len(tells) >= 2:
            tells[1] = baseline_tell
        else:
            tells.append(baseline_tell)

    return tells


def observe_read(
    *,
    agent: Agent,
    pressure: float,
    last_tells: list[ObservableTell],
    seed: str,
    baseline: Optional[BehaviouralBaseline] = None,
    first_observe: bool = False,
) -> tuple[str, str, str, Optional[str]]:
    """A deliberate, spent-action study of a suspect:
    (text, category, intensity, baseline_state).

    Observe sharpens what the player could already see — it is built ONLY from
    player-visible signals (cumulative pressure, the tells already shown with the
    last answer, public traits, and the remembered calm baseline). It never touches
    truthfulness or hidden state, so it can never become a lie detector: a composed
    liar reads as composed, and "different from earlier" tracks pressure, which an
    innocent under strain shows too.
    """

    trait = agent.traits[0] if agent.traits else "guarded"

    if pressure >= 0.85:
        band_options = [
            "They are barely holding the room. Every question lands somewhere soft now, and they know you can see it.",
            "The composure is gone; what is left is effort. They are working for every level sentence.",
        ]
        band_intensity = "strong"
    elif pressure >= 0.6:
        band_options = [
            "The stillness has gone brittle. They answer you, but part of them is somewhere else, checking the story for cracks.",
            "They have started managing themselves — breath, hands, voice — and management is not the same as calm.",
        ]
        band_intensity = "strong"
    elif pressure >= 0.35:
        band_options = [
            "There is a new economy to them: shorter answers, smaller movements, nothing volunteered.",
            "They are listening to your questions differently now — for where the next one is going.",
        ]
        band_intensity = "noticeable"
    elif pressure >= 0.1:
        band_options = [
            "They are careful, the way people get when a conversation stops being casual.",
            "Nothing dramatic — just a beat more thought before each answer than the questions deserve.",
        ]
        band_intensity = "noticeable"
    else:
        band_options = [
            f"Their breathing is even and their hands are quiet. Whatever this is costing them, it does not show. They read as {trait}.",
            "They meet your eyes without effort. If something is being held back, it is being held well.",
        ]
        band_intensity = "subtle"

    band_text = band_options[_stable_index((agent.agent_id, "observe-band", seed), len(band_options))]

    # The baseline comparison: how this manner sits against the one you filed away
    # when they were calm. Measured in meter bands, so it says "different from
    # earlier" exactly when the player can feel the difference — never "lying".
    baseline_state: Optional[str] = None
    baseline_clause = ""
    if baseline is not None:
        delta = pressure_band(pressure) - pressure_band(baseline.captured_at_pressure)
        habit = baseline.habit_text
        if delta >= 2:
            baseline_state = "broken"
            variants = [
                f"At ease, {habit} — that was your first read of them. Every piece of it has been packed away now. It is not proof of anything, but they are not the person you first sat down with.",
                f"Set it against your first read of them — {habit} — and the change is the loudest thing in the room.",
            ]
        elif delta == 1:
            baseline_state = "shifted"
            variants = [
                f"At ease, {habit} — that was your first read of them. There is less of it now; a small difference, but a real one.",
                f"Your first read of them still mostly holds — {habit} — but it is fraying at the edges.",
            ]
        elif first_observe:
            baseline_state = "noted"
            variants = [
                f"Worth filing away: at ease, {habit}. If that ever changes, you will want to know.",
                f"Note the manner while it is unforced: {habit}. That is your measure of this person.",
            ]
        else:
            baseline_state = "consistent"
            variants = [
                f"Still the manner you filed away — {habit} — the same as when this began.",
                f"Nothing has moved them off their baseline: {habit}, now as at the start.",
            ]
        baseline_clause = " " + variants[
            _stable_index((agent.agent_id, "observe-baseline", seed), len(variants))
        ]

    sharpen = {
        "gaze": [
            "Watch the eyes: they keep returning to the same fixed point between answers, as if checking something is still where they left it.",
            "Their glance does a small circuit — you, the table, the door — and it is the door that gets the extra beat.",
        ],
        "timing": [
            "The rhythm gives more away than the words: the pauses come before the details, not after them.",
            "Their answers arrive a fraction rehearsed — the cadence of something said before, in private, for practice.",
        ],
        "hands": [
            "The hands are the tell: too still when the questions get specific, busy again the moment the subject moves on.",
            "Watch the knuckles when a place or a time is named — a small grip, released a moment too late.",
        ],
        "voice": [
            "The voice holds its level, but the register drops a shade on certain names, as if lowering them out of reach.",
            "Listen under the words: the breath support falters just before the sentences that matter most.",
        ],
        "posture": [
            "They keep re-settling into the same composed position — composure as a place they have to keep walking back to.",
            "The shoulders answer before the mouth does: a small brace at some questions, none at others.",
        ],
        "overexplaining": [
            "Count the detail: it thickens exactly where you pressed, padding the story where it is thinnest.",
            "They keep furnishing the answer — one more particular, one more aside — the way people decorate a room they don't want searched.",
        ],
    }

    latest = last_tells[0] if last_tells else None
    if latest is not None and latest.category in sharpen:
        options = sharpen[latest.category]
        detail = options[_stable_index((agent.agent_id, "observe-detail", seed), len(options))]
        category = latest.category
        order = {"subtle": 0, "noticeable": 1, "strong": 2}
        intensity = TELL_INTENSITIES[min(2, max(order[latest.intensity], order[band_intensity]))]
        return f"{band_text}{baseline_clause} {detail}", category, intensity, baseline_state

    quiet_options = [
        "You watch them through a long silence, and they let you. Nothing surfaces worth the name of a tell.",
        "For a held moment you study them openly. Either there is nothing underneath, or it is buried past watching.",
    ]
    detail = quiet_options[_stable_index((agent.agent_id, "observe-quiet", seed), len(quiet_options))]
    return f"{band_text}{baseline_clause} {detail}", "posture", band_intensity, baseline_state


def challenge_tells(
    *,
    agent: Agent,
    outcome: str,
    emotional_shift: Optional[str],
    pressure_delta: float,
    pressure_after: float,
    seed: str,
) -> list[ObservableTell]:
    """Generate observations for a resolved challenge."""

    emotion = _norm(emotional_shift)
    landed = pressure_delta > 0.001
    severe = outcome in {"contradiction_locked", "partial_admission"} or emotion in HIGH_STRESS
    score = pressure_after + max(0.0, pressure_delta) * 1.2
    if severe:
        score += 0.55
    if not landed and outcome == "deny":
        score -= 0.35

    if score < 0.42:
        return []

    if outcome == "contradiction_locked":
        options = [
            ("posture", "The evidence lands; they stop moving altogether."),
            ("voice", "Their reply starts controlled, then thins on the crucial word."),
            ("gaze", "They look at the evidence before they can stop themselves."),
        ]
    elif outcome == "partial_admission":
        options = [
            ("timing", "The answer comes late, after a silence they cannot quite fill."),
            ("hands", "Their fingers spread on the table, then curl back in."),
            ("voice", "They concede the point in a lower voice."),
        ]
    elif landed:
        options = [
            ("posture", "They sit back as if the question has found a bruise."),
            ("hands", "Their hand moves toward the evidence, then stops short."),
            ("gaze", "Their attention fixes on the clue longer than it should."),
        ]
    else:
        options = [
            ("voice", "They keep their tone even, but the answer has gone colder."),
            ("posture", "They give you nothing except a tighter jaw."),
        ]

    category, cue = _pick(agent, "challenge", f"{seed}:{outcome}:{emotion}", options)
    return [
        ObservableTell(
            tell_id=_tell_id(agent, "challenge", seed, 0),
            agent_id=agent.agent_id,
            cue=cue,
            category=category,
            intensity=_intensity(score),
            source="challenge",
        )
    ]
