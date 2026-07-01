"""
File: chat_resolver.py
Description: Conversation initiation is the one place in the cognitive
pipeline where one persona's cognition needs to mutate another persona's
state (see plan.py's _chat_propose). To keep agent cognition side-effect
free so it can run concurrently, that mutation is split into two phases:

  1. During cognition (may run in a worker thread): _chat_propose computes
     everything both personas would need written, but writes nothing. It
     returns a ChatProposal.
  2. After a tick's cognition completes (main thread only): ChatResolver
     applies every ChatProposal it accepts to both personas' scratch in one
     call each, or rejects the proposal and applies nothing. A proposal is
     never partially applied.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ReactSideEffect:
  """What _create_react used to write directly to one persona's scratch,
  captured as data instead of an in-place mutation."""
  persona_name: str
  schedule_start_index: Optional[int]
  schedule_end_index: Optional[int]
  schedule_replacement: Optional[list]
  add_new_action_kwargs: dict


@dataclass
class ChatProposal:
  tick_id: int
  initiator: str
  target: str
  init_side: ReactSideEffect
  target_side: ReactSideEffect


def apply_react_side_effect(persona, side_effect):
  """Applies a single ReactSideEffect to persona.scratch. Self-only reactions
  (e.g. _wait_react) call this directly; cross-persona chat proposals go
  through ChatResolver instead so both sides commit together."""
  if side_effect.schedule_replacement is not None:
    persona.scratch.f_daily_schedule[
      side_effect.schedule_start_index:side_effect.schedule_end_index
    ] = side_effect.schedule_replacement
  persona.scratch.add_new_action(**side_effect.add_new_action_kwargs)


class ChatResolver:
  """Applies or rejects ChatProposals collected from a tick's cognition pass.
  Deterministic ordering: tick_id, then initiator name. A persona can only
  be committed to one chat per tick; the first proposal touching a persona
  (by that ordering) wins, later ones referencing the same persona are
  rejected wholesale."""

  def __init__(self, log=None):
    self._log = log

  def resolve_and_apply(self, proposals, personas):
    accepted, rejected = [], []
    committed = set()

    for proposal in sorted(proposals, key=lambda p: (p.tick_id, p.initiator)):
      if self._has_conflict(proposal, personas, committed):
        rejected.append(proposal)
        if self._log:
          self._log.chat_rejected(proposal)
        continue

      apply_react_side_effect(personas[proposal.initiator], proposal.init_side)
      apply_react_side_effect(personas[proposal.target], proposal.target_side)
      committed.add(proposal.initiator)
      committed.add(proposal.target)
      accepted.append(proposal)
      if self._log:
        self._log.chat_accepted(proposal)

    return accepted, rejected

  def _has_conflict(self, proposal, personas, committed):
    if proposal.initiator in committed or proposal.target in committed:
      return True
    target_scratch = personas[proposal.target].scratch
    if target_scratch.chatting_with:
      # Target already mid-conversation (from a prior tick or an earlier
      # proposal this tick) -- don't disrupt it.
      return True
    return False
