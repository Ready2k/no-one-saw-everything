"""Pays for the *next* turn while the player is still reading this one.

The interview UI offers a small, fixed set of structured questions, so the
player's next move is drawn from a handful of known options. Each one's answer
can be generated in the background during the seconds a player spends reading
the last reply, and by the time they click, the rewrite is already in
`rewrite_cache` and the turn returns at deterministic speed.

This removes latency rather than masking it, which is why it is worth more than
the stall fillers it complements: a filler makes a 3s wait tolerable, a cache
hit means there was no wait.

**It runs the real engine against a deep copy of the session.** That is the
whole safety design, and it is deliberate rather than lazy. Answering a question
mutates a lot — `record_claim`, revealed clues, the per-agent transcript, ask
counts, telemetry — and a warmer that tried to skip those mutations would be
re-implementing `answer_question`, drifting from it silently, and eventually
corrupting a real session by forgetting one. Against a copy, every mutation
lands somewhere that is thrown away, and the only thing that escapes is the
memoised rewrite — which is keyed on its own inputs and so can only ever be
served to a turn that matches it exactly.

Consequences worth stating plainly:

* A prefetch that guesses wrong costs one wasted model call and nothing else.
* A prefetch that guesses right is invisible: the player gets the same words
  they would have got, sooner.
* Prefetch can never change an answer. If the player does something first that
  alters the turn — discovers a clue, applies pressure, asks something else —
  the inputs differ, the key differs, and the warmed entry is simply never read.
"""

from __future__ import annotations

import copy
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from .models import AskRequest, CaseData
from .session import Session

logger = logging.getLogger(__name__)

# The structured questions the UI actually offers. `evidence`/`location`/
# `timeline` need a topic or a time the player has not chosen yet, so they are
# not predictable and are left out — guessing a topic would burn model calls on
# answers nobody asked for.
PREFETCHABLE_QUESTION_TYPES = ("alibi", "relationship", "last_seen_victim")

# One worker: prefetch is opportunistic and must never contend with the turn the
# player is actually waiting on, nor stack up requests against a local model
# that serves them one at a time anyway.
_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()
_inflight: set[tuple[str, str]] = set()
_enabled = True


def _pool() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prefetch")
        return _executor


def set_enabled(enabled: bool) -> None:
    """Tests and playtests turn this off to keep timing deterministic."""
    global _enabled
    _enabled = enabled


def is_enabled() -> bool:
    return _enabled


def _warm_one(case: CaseData, session_copy: Session, agent_id: str, question_type: str) -> None:
    from .interview import answer_question

    try:
        answer_question(case, session_copy, AskRequest(agent_id=agent_id, question_type=question_type))
    except Exception as exc:  # noqa: BLE001 - a warmer must never surface an error
        logger.debug("prefetch %s/%s skipped: %s", agent_id, question_type, exc)
    finally:
        _inflight.discard((agent_id, question_type))


def warm_agent(case: CaseData, session: Session, agent_id: str, just_asked: Optional[str] = None) -> int:
    """Generate the likely next answers for this agent in the background.

    Returns how many were scheduled — 0 when there is nothing to gain (no LLM
    configured, dialogue rewriting off, or the session has already degraded to
    the written script, in which case the answers are instant anyway).
    """
    if not _enabled:
        return 0

    from .llm.config import get_llm_config

    config = get_llm_config()
    if not (config.configured and config.dialogue_enabled):
        return 0
    if session.llm_unavailable:
        return 0

    scheduled = 0
    for question_type in PREFETCHABLE_QUESTION_TYPES:
        if question_type == just_asked:
            continue
        token = (agent_id, question_type)
        if token in _inflight:
            continue
        # One copy per job: the jobs run sequentially but must not observe each
        # other's mutations, or the second would be warmed against a state the
        # player will never be in.
        try:
            session_copy = copy.deepcopy(session)
        except Exception as exc:  # noqa: BLE001
            logger.debug("prefetch could not copy session: %s", exc)
            return scheduled
        _inflight.add(token)
        _pool().submit(_warm_one, case, session_copy, agent_id, question_type)
        scheduled += 1

    return scheduled


def wait_idle(timeout: float = 10.0) -> bool:
    """Block until scheduled warms finish. Tests only — the game never waits."""
    import time

    deadline = time.monotonic() + timeout
    while _inflight and time.monotonic() < deadline:
        time.sleep(0.01)
    return not _inflight


def reset() -> None:
    _inflight.clear()
