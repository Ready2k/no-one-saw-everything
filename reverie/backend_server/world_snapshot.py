"""
File: world_snapshot.py
Description: A persona's own state is only ever written by that persona's
own cognition task, so it's safe for cognition to read its own `scratch`
live. But conversation-gating logic (lets_talk/lets_react in plan.py,
execute()'s persona-to-persona pathing) needs to read a handful of fields
off OTHER personas -- and those personas may be concurrently running their
own cognition task in another worker thread, mutating those same fields.
WorldSnapshot freezes just those fields once per tick, before any cognition
runs, so cross-persona reads never race a concurrent writer.
"""
from collections import namedtuple

PersonaGateView = namedtuple("PersonaGateView", [
  "name", "curr_tile", "chatting_with", "act_address",
  "act_description", "chatting_with_buffer",
])


class WorldSnapshot:
  def __init__(self, tick_id, curr_time, personas):
    self.tick_id = tick_id
    self.curr_time = curr_time
    self._views = {}
    for name, p in personas.items():
      s = p.scratch
      self._views[name] = PersonaGateView(
        name=name,
        curr_tile=tuple(s.curr_tile) if s.curr_tile else None,
        chatting_with=s.chatting_with,
        act_address=s.act_address,
        act_description=s.act_description,
        chatting_with_buffer=dict(s.chatting_with_buffer or {}),
      )

  def gate_view(self, persona_name):
    return self._views[persona_name]

  def curr_tile_of(self, persona_name):
    return self._views[persona_name].curr_tile
