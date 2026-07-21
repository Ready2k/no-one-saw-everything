"""Background-simulation prompt inputs (spec 15).

Phase A: `build_world_state_digest` — a handful of short, already-public
lines about the state of the investigation, fed into rewrite prompts as
atmosphere. Built purely from static authored templates and case/session
flags; raw player input (e.g. a challenge's player_statement) is never
included, so one suspect's prompt can't be injected through another's
interview.

Phase B: `build_conversation_context` — replaces the flat last-6-message
window with that window plus an extractive summary of everything before
it, so a long interrogation doesn't forget its own opening. The summary
keeps only the agent's own lines: `deterministic_text` where present
(leak-safe by construction) or the displayed text for open-ended replies
(already sanitised and already shown to the player).

Simulation informs flavour, never facts: nothing produced here goes into
`allowed_facts`, and nothing here is read by the deterministic engines.
"""

from __future__ import annotations

from .models import Agent, AgentBeliefState, CaseData
from .session import Session

# Challenge outcomes that visibly damaged a suspect's story in front of the
# player — the only challenge results other suspects are allowed to "hear
# about" as village gossip.
_STORY_DAMAGED_OUTCOMES = {"contradiction_locked", "partial_admission"}

# Another suspect's private stress level is never exposed as a number —
# only a coarse village-wide mood once anyone else is rattled enough.
_TENSION_THRESHOLD = 0.4

RECENT_WINDOW = 6
_MAX_SUMMARY_LINES = 10
_MAX_SUMMARY_CHARS = 160


def build_world_state_digest(
    case: CaseData,
    session: Session,
    agent_id: str,
    include_beliefs: bool = True,
) -> list[str]:
    """Short, factual, already-public lines for the `world_state` prompt
    field. Empty when nothing has happened yet, so behaviour with a fresh
    session is identical to having no digest at all."""
    lines: list[str] = []

    discovered = len(session.discovered_clue_ids)
    if discovered:
        plural = "piece" if discovered == 1 else "pieces"
        lines.append(
            f"The detective has discovered {discovered} {plural} of evidence so far."
        )

    named: set[str] = set()
    for record in session.challenges.values():
        # An agent's own challenges are already in their transcript window.
        if record.target_agent_id == agent_id:
            continue
        if record.outcome not in _STORY_DAMAGED_OUTCOMES:
            continue
        target = next(
            (a for a in case.agents if a.agent_id == record.target_agent_id), None
        )
        if target is None or target.full_name in named:
            continue
        named.add(target.full_name)
        lines.append(
            f"Word has gone around that {target.full_name}'s account was "
            "directly challenged by the detective and did not hold up."
        )

    others_pressure = [
        p for other_id, p in session.pressure.items() if other_id != agent_id
    ]
    if others_pressure and max(others_pressure) >= _TENSION_THRESHOLD:
        lines.append(
            "Several people in the village seem tense; the investigation is escalating."
        )

    if include_beliefs:
        belief = session.belief_states.get(agent_id)
        if belief is not None:
            lines.extend(belief_flavour_lines(case, belief))

    return lines


def belief_flavour_lines(case: CaseData, belief: AgentBeliefState) -> list[str]:
    """Turns a stored belief state (spec 15 Phase C) into the same kind of
    atmosphere lines as the digest. The state was already validated when it
    was stored (suspicion of the real killer nullified, talking points
    filtered), so this is pure formatting."""
    lines: list[str] = []
    if belief.worry_level >= 0.7:
        lines.append("Privately, you are deeply worried about where this investigation is heading.")
    elif belief.worry_level >= 0.4:
        lines.append("Privately, this investigation has started to weigh on you.")

    if belief.current_suspicion_target:
        target = next(
            (a for a in case.agents if a.agent_id == belief.current_suspicion_target),
            None,
        )
        if target is not None:
            lines.append(
                f"Privately, you have started to wonder whether {target.full_name} "
                "is telling the whole truth."
            )

    for point in belief.talking_points[:3]:
        lines.append(f"It has been on your mind lately: {point}")
    return lines


def build_conversation_context(session: Session, agent: Agent) -> list[str]:
    """The `recent_exchange` prompt lines: an extractive summary of the
    interview's earlier turns (agent's own statements only) followed by the
    last few messages verbatim, exactly as before."""
    messages = session.transcript_for(agent.agent_id).messages
    recent = messages[-RECENT_WINDOW:]
    earlier = messages[:-RECENT_WINDOW] if len(messages) > RECENT_WINDOW else []

    lines: list[str] = []
    summary: list[str] = []
    for m in earlier:
        if m.speaker != "agent":
            continue
        text = m.deterministic_text or m.text
        if not text:
            continue
        if len(text) > _MAX_SUMMARY_CHARS:
            text = text[: _MAX_SUMMARY_CHARS - 1] + "…"
        summary.append(f"{agent.full_name} (earlier in this interview): {text}")
    if summary:
        lines.append(
            "Your own earlier statements in this interview (stay consistent with them):"
        )
        lines.extend(summary[-_MAX_SUMMARY_LINES:])

    lines.extend(
        f"{'Detective' if m.speaker == 'player' else agent.full_name}: {m.text}"
        for m in recent
    )
    return lines
