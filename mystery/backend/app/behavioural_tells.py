"""Deterministic behavioural observations for interviews and challenges.

These tells make interrogation feel observable without turning the UI into a
lie detector. The generator may use hidden truth to bias whether a cue appears,
but every returned cue is player-safe: visible behaviour only.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, Optional

from .models import Agent, ObservableTell, QuestionType, TruthStatus


TELL_INTENSITIES = ("subtle", "noticeable", "strong")

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


def interview_tells(
    *,
    agent: Agent,
    question_type: QuestionType,
    truthfulness: TruthStatus,
    emotional_shift: Optional[str],
    pressure: float,
    seed: str,
) -> list[ObservableTell]:
    """Generate 0-2 observations for an interview answer."""

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

    if stress < 0.38:
        return []

    evasive_options = [
        ("gaze", "Their eyes leave yours for a beat before the answer arrives."),
        ("timing", "They answer a fraction too quickly, then repeat the detail as if setting it in place."),
        ("hands", "Their hands go still on the table while they give that detail."),
        ("overexplaining", "They add a tidy extra detail you did not ask for."),
    ]
    emotional_options = [
        ("voice", "Their voice tightens around the last sentence."),
        ("posture", "Their shoulders pull in before they make themselves sit still again."),
        ("hands", "A thumb worries at a cuff seam while they keep talking."),
        ("gaze", "They glance away at the named place before looking back."),
    ]
    steady_options = [
        ("voice", "They take a breath and keep their voice carefully level."),
        ("posture", "They hold themselves very still, almost too deliberately."),
        ("timing", "They pause long enough to choose each word."),
    ]

    if falsey:
        options = evasive_options
    elif emotionally_loud:
        options = emotional_options
    else:
        options = steady_options

    category, cue = _pick(agent, "interview", f"{seed}:{question_type}:{truthfulness}:{emotion}", options)
    tells = [
        ObservableTell(
            tell_id=_tell_id(agent, "interview", seed, 0),
            agent_id=agent.agent_id,
            cue=cue,
            category=category,
            intensity=_intensity(stress),
            source="interview",
        )
    ]

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

    return tells


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
