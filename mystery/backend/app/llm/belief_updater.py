"""Offline belief-state batch updates (spec 15 Phase C).

After specific session events (a challenge resolves, a clue is discovered)
a single LLM call per *affected* agent produces a small AgentBeliefState —
worry level, an optional private suspicion target, and a few talking
points. Strictly asynchronous: `schedule_belief_updates` fires a daemon
thread after the triggering endpoint's work is done, and readers simply use
whatever state was last stored, so the player-facing request path never
waits on this.

Safety: the model is only ever given public information (persona, the
world-state digest, the agent's own prior statements) — never the truth.
Its output is validated before being stored: a suspicion target that
happens to match the real killer is nullified (not the whole update, to
avoid a meta-leak where absent suspicion fingers the killer), and talking
points that touch forbidden facts or name other cast members are dropped.
The stored state is only ever read back as prompt flavour via
`world_state.belief_flavour_lines` — never by the deterministic engines,
and never as allowed facts, so the downstream sanitiser still applies.
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Optional

from ..models import Agent, AgentBeliefState, CaseData
from ..session import Session
from .client import get_llm_client
from .config import get_llm_config
from .dialogue_rewriter import _build_forbidden_facts

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

_MAX_TALKING_POINTS = 3
_MAX_TALKING_POINT_CHARS = 160


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text("utf-8")


def _candidates(case: CaseData, agent_id: str) -> list[Agent]:
    """Other living suspects this agent could privately wonder about."""
    return [
        a
        for a in case.agents
        if a.agent_id != agent_id
        and not a.is_victim
        and a.agent_id != case.case.victim_id
    ]


def _validate_belief(
    case: CaseData, agent: Agent, state: AgentBeliefState
) -> AgentBeliefState:
    """Clamp and sanitise a raw belief update before it is stored."""
    worry = max(0.0, min(1.0, state.worry_level))

    # Suspicion target must be a real, living, other suspect — and if it
    # resolves toward the actual killer it is nullified (the rest of the
    # update is kept, per spec, so absent updates don't fingerprint anyone).
    target: Optional[str] = state.current_suspicion_target
    valid_ids = {a.agent_id for a in _candidates(case, agent.agent_id)}
    if target not in valid_ids:
        target = None
    if target == case.solution.killer_id:
        target = None

    forbidden = [f.lower() for f in _build_forbidden_facts(case, agent) if len(f) > 10]
    first_names = [a.full_name.split()[0] for a in case.agents]

    points: list[str] = []
    for point in state.talking_points:
        text = point.strip()
        if not text:
            continue
        lowered = text.lower()
        if "{" in text or "}" in text:
            continue
        if any(label in lowered for label in ("killer", "red_herring", "victim_role")):
            continue
        if any(fact in lowered for fact in forbidden):
            continue
        # Talking points are self-focused colour; one that names another
        # cast member is how an invented sighting would smuggle itself in.
        if any(re.search(rf"\b{re.escape(n.lower())}\b", lowered) for n in first_names):
            continue
        points.append(text[:_MAX_TALKING_POINT_CHARS])
        if len(points) >= _MAX_TALKING_POINTS:
            break

    if target is None and state.current_suspicion_target is not None:
        # Generic fallback state instead of a silent hole where suspicion
        # used to be.
        points = points or ["I don't know who to trust in this village anymore."]

    return AgentBeliefState(
        worry_level=worry, current_suspicion_target=target, talking_points=points
    )


def update_belief_state(
    case: CaseData, session: Session, agent_id: str, trigger_summary: str
) -> Optional[AgentBeliefState]:
    """One synchronous belief update for one agent. Returns the stored state,
    or None if the update failed (previous state, if any, is kept)."""
    from ..world_state import build_world_state_digest

    agent = next((a for a in case.agents if a.agent_id == agent_id), None)
    if agent is None or agent.is_victim or agent_id == case.case.victim_id:
        return None

    previous = session.belief_states.get(agent_id)
    digest = build_world_state_digest(case, session, agent_id, include_beliefs=False)
    candidates = _candidates(case, agent_id)

    user_prompt = _load_prompt("belief_update_user.txt").format(
        name=agent.full_name,
        occupation=agent.occupation,
        traits=", ".join(agent.traits),
        pressure_level=session.pressure_for(agent_id),
        trigger_summary=trigger_summary,
        world_state="- " + "\n- ".join(digest) if digest else "Nothing notable yet.",
        previous_state=(
            f"worry_level={previous.worry_level}, talking_points={previous.talking_points}"
            if previous
            else "None recorded."
        ),
        candidates="\n".join(f"- {a.agent_id} ({a.full_name})" for a in candidates),
    )

    try:
        raw = get_llm_client().generate_json(
            system_prompt=_load_prompt("belief_update_system.txt"),
            user_prompt=user_prompt,
            schema=AgentBeliefState,
        )
    except Exception as e:
        logger.warning(f"Belief update failed for {agent_id}: {e}")
        return None

    state = _validate_belief(case, agent, raw)
    session.belief_states[agent_id] = state
    return state


def schedule_belief_updates(
    case: CaseData, session: Session, agent_ids: list[str], trigger_summary: str
) -> Optional[threading.Thread]:
    """Fire-and-forget belief updates for the affected agents. No-op unless
    both dialogue rewriting and the beliefs flag are enabled. Returns the
    thread (for tests); callers ignore it."""
    config = get_llm_config()
    if not (config.dialogue_enabled and config.beliefs_enabled):
        return None
    ids = list(dict.fromkeys(agent_ids))  # de-dupe, keep order
    if not ids:
        return None

    def _run() -> None:
        for agent_id in ids:
            try:
                update_belief_state(case, session, agent_id, trigger_summary)
            except Exception:
                logger.exception(f"Belief update crashed for {agent_id}")

    thread = threading.Thread(target=_run, daemon=True, name="belief-updates")
    thread.start()
    return thread
