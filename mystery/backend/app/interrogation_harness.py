"""Detective-style interview stress harness.

Runs the same natural-language interrogation battery — good cop rapport,
bad cop pressure, and the plain follow-ups in between — against every
playable character in every saved case. It deliberately uses fresh in-memory
sessions: the harness never reads or changes a player's investigation save.

Run from ``backend``::

    python -m app.interrogation_harness
    python -m app.interrogation_harness --case case_005 --live-dialogue --llm-critic

The default mode tests routing and deterministic safety only. ``--live-dialogue``
uses the configured local LLM for the exact answers a player would see;
``--llm-critic`` additionally asks that LLM to grade visible question/answer
pairs. Neither mode sends hidden solution data to the critic.
"""

from __future__ import annotations

import argparse
import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator
from unittest.mock import patch

from pydantic import BaseModel, Field

from .case_store import get_case, list_all_cases
from .free_text_api import handle_free_text
from .llm.client import get_llm_client
from .llm.config import LLMConfig
from .models import CaseData, FreeTextAskRequest, QuestionIntent
from .session import Session


GENERIC_FALLBACKS = (
    "i don't have much to say about that",
    "well... i don't have much to say about that",
    "nothing, really",
)


DetectiveStyle = str  # "good_cop" | "bad_cop" | "neutral"


@dataclass(frozen=True)
class DetectiveQuestion:
    """A natural question and the logical constraints it carries."""

    id: str
    question: str
    style: DetectiveStyle = "neutral"
    disallowed_intents: tuple[str, ...] = ()
    reject_generic: bool = False
    subject_name: str | None = None
    required_clue_agent_id: str | None = None


class LlmCritique(BaseModel):
    realism_score: int = Field(ge=1, le=5)
    grounded: bool
    follows_question: bool
    issue: str | None = None


def _first_name(name: str) -> str:
    return name.split()[0]


def detective_question_bank(case: CaseData, agent_id: str) -> list[DetectiveQuestion]:
    """Build a case-aware good-cop/bad-cop question bank for one interviewable agent.

    Ordered like a real interrogation: rapport first, pressure later, and a
    softer close — the same isolated session carries state across the list, so
    later questions can lean on pronouns ("them", "it") the way a follow-up
    actually would. The implications intentionally test reasoning rather than
    exact prose. For example, asking about another named person must never
    route to the victim's ``last_seen_victim`` answer just because a later
    follow-up uses ``him``, and a hard, specific bad-cop question must never
    be softened into small talk.

    Some questions are grounded in case truth the harness can see (the murder
    window, the murder location, the weapon) purely to construct a realistic,
    specific accusation — nothing here is ever surfaced to a player; this is
    the same trust boundary the deterministic engine itself operates behind.
    """
    agent = next(a for a in case.agents if a.agent_id == agent_id)
    victim = next(a for a in case.agents if a.agent_id == case.case.victim_id)
    other = next(
        a for a in case.agents
        if a.agent_id not in {agent.agent_id, victim.agent_id} and not a.is_background
    )
    murder_location = next(
        (loc for loc in case.locations if loc.location_id == case.case.murder_location_id), None
    )
    weapon = next(
        (obj for obj in case.objects if obj.object_id == case.case.weapon_id),
        case.objects[0] if case.objects else None,
    )
    window_start, window_end = case.case.murder_window

    questions = [
        DetectiveQuestion(
            id="greeting_contains_grief",
            question=(
                f"Hi {_first_name(agent.full_name)}, how are you coping with the loss "
                f"of {_first_name(victim.full_name)}?"
            ),
            style="good_cop",
            disallowed_intents=("greeting",),
            reject_generic=True,
        ),
        DetectiveQuestion(
            id="feelings_about_death",
            question=f"Take your time. How do you feel about {victim.full_name}'s death?",
            style="good_cop",
            reject_generic=True,
        ),
        DetectiveQuestion(
            id="good_cop_gentle_alibi",
            question=(
                "No pressure — I just need to understand your morning. "
                "Can you walk me through it, step by step?"
            ),
            style="good_cop",
            disallowed_intents=("greeting", "how_are_you"),
            reject_generic=True,
        ),
        DetectiveQuestion(
            id="last_seen_named_person",
            question=f"When did you last see {_first_name(other.full_name)}?",
            style="neutral",
            # A named non-victim must not be silently converted into "the victim".
            disallowed_intents=("last_seen_victim",),
            subject_name=_first_name(other.full_name),
        ),
        DetectiveQuestion(
            id="last_seen_follow_up",
            question="That wasn't the question — when did you last see them?",
            style="bad_cop",
            disallowed_intents=("last_seen_victim",),
            subject_name=_first_name(other.full_name),
        ),
        DetectiveQuestion(
            id="bad_cop_alibi_pressure",
            question=(
                f"Cut to it — where exactly were you between {window_start} and "
                f"{window_end} this morning? I want a straight answer, not a summary."
            ),
            style="bad_cop",
            disallowed_intents=("greeting", "how_are_you"),
            reject_generic=True,
        ),
        DetectiveQuestion(
            id="bad_cop_motive_press",
            question=f"Give me one good reason you'd want {_first_name(victim.full_name)} out of the picture.",
            style="bad_cop",
            disallowed_intents=("greeting", "how_are_you"),
            reject_generic=True,
        ),
        DetectiveQuestion(
            id="self_description",
            question="Let's back up for a second, just you and me — tell me about yourself. What do you love, and what do you hate?",
            style="good_cop",
            reject_generic=True,
        ),
        DetectiveQuestion(
            id="relationship_with_victim",
            question=f"What was your relationship with {victim.full_name}, really?",
            style="neutral",
            reject_generic=True,
            # A relationship answer can be revealing, but any clue it surfaces
            # must actually concern the person the detective named.
            required_clue_agent_id=victim.agent_id,
        ),
        DetectiveQuestion(
            id="bad_cop_one_word_motive",
            question="Motive?",
            style="bad_cop",
            disallowed_intents=("greeting", "how_are_you"),
            reject_generic=True,
        ),
        DetectiveQuestion(
            id="good_cop_closing_invite",
            question="Before I go — is there anything else you think I should know? Anything at all.",
            style="good_cop",
        ),
    ]

    if murder_location is not None:
        questions.insert(
            6,
            DetectiveQuestion(
                id="bad_cop_placed_at_scene",
                question=f"I've got someone putting you near {murder_location.name} right around then. Explain that to me.",
                style="bad_cop",
                disallowed_intents=("greeting", "how_are_you"),
                reject_generic=True,
            ),
        )

    if weapon is not None:
        questions.extend([
            DetectiveQuestion(
                id="object_named",
                question=f"What can you tell me about {weapon.name}?",
                style="neutral",
            ),
            DetectiveQuestion(
                id="object_pronoun_follow_up",
                question="Where was it, exactly, the last time you saw it?",
                style="bad_cop",
                # A named object must not be silently converted into a question
                # about the victim just because "it" needs resolving.
                disallowed_intents=("last_seen_victim",),
            ),
        ])

    return questions


def _disabled_llm_config() -> LLMConfig:
    return LLMConfig(
        provider="fake",
        base_url=None,
        api_key=None,
        model=None,
        timeout_seconds=1,
        configured=True,
        fallback_reason=None,
        dialogue_enabled=False,
        beliefs_enabled=False,
    )


@contextmanager
def _dialogue_mode(use_live_dialogue: bool) -> Iterator[None]:
    """Prevent a routine stress pass from accidentally consuming local LLM time."""
    if use_live_dialogue:
        yield
        return

    fallback_intent = lambda *args, **kwargs: QuestionIntent(
        intent="fallback_unknown", confidence=0.0, rewritten_structured_question="Unknown question"
    )
    with (
        patch("app.free_text_api.get_llm_config", _disabled_llm_config),
        patch("app.interview.get_llm_config", _disabled_llm_config),
        patch("app.free_text_api.classify_question_intent_llm", fallback_intent),
    ):
        yield


def _visible_answer(response: Any) -> str:
    if response.answer:
        return response.answer.get("answer_text", "")
    return response.fallback_message or ""


def _logical_findings(
    question: DetectiveQuestion,
    intent: str,
    answer: str,
    revealed_clues: list[dict[str, Any]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    lower_answer = answer.lower().strip()
    if intent in question.disallowed_intents:
        findings.append({
            "kind": "wrong_route",
            "detail": f"{question.id} was routed as {intent}, which contradicts its subject.",
        })
    if question.reject_generic and any(phrase in lower_answer for phrase in GENERIC_FALLBACKS):
        findings.append({
            "kind": "generic_fallback",
            "detail": f"{question.id} received a generic non-answer.",
        })
    if not answer.strip():
        findings.append({"kind": "empty_answer", "detail": f"{question.id} returned no visible answer."})
    if question.required_clue_agent_id:
        for clue in revealed_clues:
            if question.required_clue_agent_id not in clue.get("linked_agent_ids", []):
                findings.append({
                    "kind": "irrelevant_clue_reveal",
                    "detail": (
                        f"{question.id} revealed {clue.get('clue_id', 'a clue')} even though it does not "
                        "concern the person named in the question."
                    ),
                })
    return findings


def _critique(question: str, answer: str) -> dict[str, Any]:
    """Use only player-visible content; no solution, memories, or hidden clues."""
    prompt = f"""Question: {question!r}
Answer: {answer!r}

Grade this one detective-game answer. It should directly address the question,
sound like a grieving human character, and avoid pretending to reveal evidence.
Generic evasions such as "I don't have much to say about that" do not answer a
specific question: mark ``follows_question`` false and give them at most 2/5.
Return JSON only."""
    try:
        value = get_llm_client().generate_json(
            system_prompt="You are a strict dialogue playtester. Judge only the supplied visible text.",
            user_prompt=prompt,
            schema=LlmCritique,
            temperature=0.0,
        )
        return value.model_dump()
    except Exception as exc:  # A critic outage must not hide deterministic findings.
        return {"error": str(exc)}


def run_interrogation_harness(
    case_ids: list[str] | None = None,
    *,
    use_live_dialogue: bool = False,
    llm_critic: bool = False,
) -> dict[str, Any]:
    """Return a complete structured report for all requested cases."""
    chosen_case_ids = case_ids or [entry["case_id"] for entry in list_all_cases()]
    results: list[dict[str, Any]] = []

    with _dialogue_mode(use_live_dialogue):
        for case_id in chosen_case_ids:
            case = get_case(case_id)
            interviewable = [
                agent for agent in case.agents
                if agent.agent_id != case.case.victim_id and not agent.is_background
            ]
            for agent in interviewable:
                # New in-memory session per suspect: tests can build a short
                # conversation, but never touch Session.get_session() or disk.
                isolated_session = Session(f"harness_{case_id}_{agent.agent_id}")
                for item in detective_question_bank(case, agent.agent_id):
                    response = handle_free_text(
                        FreeTextAskRequest(agent_id=agent.agent_id, question=item.question),
                        case,
                        isolated_session,
                    )
                    answer = _visible_answer(response)
                    intent = response.intent.intent
                    revealed_clues = list(response.answer.get("revealed_clues", [])) if response.answer else []
                    finding = {
                        "case_id": case_id,
                        "agent_id": agent.agent_id,
                        "agent_name": agent.full_name,
                        "question_id": item.id,
                        "question": item.question,
                        "style": item.style,
                        "intent": intent,
                        "answer": answer,
                        "llm_rewrite_used": bool(response.answer and response.answer.get("llm_rewrite_used")),
                        "revealed_clue_ids": [clue.get("clue_id") for clue in revealed_clues],
                        "findings": _logical_findings(item, intent, answer, revealed_clues),
                    }
                    if llm_critic:
                        finding["critic"] = _critique(item.question, answer)
                    results.append(finding)

    issue_count = sum(len(item["findings"]) for item in results)
    issues_by_style: dict[str, int] = {}
    for item in results:
        if item["findings"]:
            issues_by_style[item["style"]] = issues_by_style.get(item["style"], 0) + len(item["findings"])
    return {
        "mode": {"live_dialogue": use_live_dialogue, "llm_critic": llm_critic},
        "cases_checked": chosen_case_ids,
        "questions_asked": len(results),
        "issues_found": issue_count,
        "issues_by_style": issues_by_style,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress-test all mystery interviews.")
    parser.add_argument("--case", action="append", dest="case_ids", help="Case ID to check (repeatable).")
    parser.add_argument("--live-dialogue", action="store_true", help="Use the configured LLM for player-visible answers.")
    parser.add_argument("--llm-critic", action="store_true", help="Ask the configured LLM to score each visible answer.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when detective-rule issues are found.")
    args = parser.parse_args()

    report = run_interrogation_harness(
        args.case_ids, use_live_dialogue=args.live_dialogue, llm_critic=args.llm_critic
    )
    print(json.dumps(report, indent=2))
    return 1 if args.strict and report["issues_found"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
