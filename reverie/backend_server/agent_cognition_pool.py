"""
File: agent_cognition_pool.py
Description: Runs every persona's cognition (perceive -> retrieve -> plan ->
reflect -> execute) for a tick concurrently via a bounded thread pool, since
the bottleneck is I/O-bound LLM calls, not CPU work. Each persona's cognition
only ever reads its own state plus the tick's WorldSnapshot, and only ever
writes its own scratch -- the one exception (starting a conversation) is
returned as a ChatProposal rather than applied, so nothing here needs to
lock persona state against itself. Movement/maze-event application and
ChatResolver still happen sequentially in the caller, after this returns.
"""
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError


class CognitionLog:
  """Minimal per-tick metrics: start/end time per agent, timeout/failure
  counts, and chat accept/reject events. Printed, not persisted -- enough to
  confirm the pool is actually parallelizing and to spot regressions."""

  def __init__(self):
    # Lifetime totals, for a running "how bad has this been overall" figure.
    self.total_timeout_count = 0
    self.total_failure_count = 0
    # Reset at the start of every tick so tick_summary reports what
    # happened *this* tick, not a stale cumulative count that makes a single
    # one-off timeout look like it's recurring on every subsequent tick.
    self.tick_timeout_count = 0
    self.tick_failure_count = 0
    self.durations = {}

  def tick_start(self):
    self.tick_timeout_count = 0
    self.tick_failure_count = 0
    self.durations = {}

  def task_start(self, persona_name):
    pass

  def task_end(self, persona_name, duration):
    self.durations[persona_name] = duration

  def task_timeout(self, persona_name):
    self.tick_timeout_count += 1
    self.total_timeout_count += 1
    print(f"[AgentCognitionPool] TIMEOUT: {persona_name}")

  def task_failed(self, persona_name, exc):
    self.tick_failure_count += 1
    self.total_failure_count += 1
    print(f"[AgentCognitionPool] FAILED: {persona_name}: {exc}")

  def chat_accepted(self, proposal):
    print(f"[ChatResolver] accepted: {proposal.initiator} <-> {proposal.target}")

  def chat_rejected(self, proposal):
    print(f"[ChatResolver] rejected: {proposal.initiator} -> {proposal.target}")

  def tick_summary(self, tick_id):
    if not self.durations and not self.tick_timeout_count and not self.tick_failure_count:
      return
    n = len(self.durations)
    avg = sum(self.durations.values()) / n if n else 0.0
    mx = max(self.durations.values()) if n else 0.0
    print(f"[AgentCognitionPool] tick {tick_id}: {n} agents processed, "
          f"avg cognition {avg:.2f}s, max {mx:.2f}s, "
          f"timeouts={self.tick_timeout_count} (total {self.total_timeout_count}), "
          f"failures={self.tick_failure_count} (total {self.total_failure_count})")


class AgentCognitionPool:
  def __init__(self, max_workers, llm_timeout_seconds, log=None):
    self.max_workers = max_workers
    self.llm_timeout_seconds = llm_timeout_seconds
    self.log = log or CognitionLog()

  def run_tick(self, personas, personas_tile, maze, curr_time, tick_id, snapshot):
    """Dispatches persona.move() for every persona concurrently.

    Returns dict[name] -> (next_tile, pronunciatio, description,
    chat_proposal). A persona whose cognition times out or raises gets a
    safe fallback instead (stay at current tile, keep current
    pronunciatio/description, no chat) -- one failed agent never blocks or
    drops the rest of the tick.

    Note: a timed-out task is abandoned, not killed (Python threads can't be
    force-cancelled) -- it may still complete in the background and mutate
    its own persona's scratch after this call returns. Acceptable for now
    since all cognition writes are self-only and calls share one local LLM
    server, but a genuinely hung call will leak a thread until it returns.
    """
    self.log.tick_start()
    results = {}
    # Deliberately not a `with` block: ThreadPoolExecutor.__exit__ calls
    # shutdown(wait=True), which would block here until every submitted
    # task finishes -- including ones we've already given up on below via
    # future.result(timeout=...). shutdown(wait=False) lets abandoned tasks
    # keep running in the background without the tick waiting on them.
    executor = ThreadPoolExecutor(max_workers=self.max_workers)
    try:
      futures = {}
      for name, persona in personas.items():
        self.log.task_start(name)
        start = time.time()
        future = executor.submit(persona.move, maze, personas,
                                 personas_tile[name], curr_time,
                                 tick_id, snapshot)
        futures[future] = (name, start)

      for future, (name, start) in futures.items():
        try:
          result = future.result(timeout=self.llm_timeout_seconds)
          self.log.task_end(name, time.time() - start)
          results[name] = result
        except FutureTimeoutError:
          self.log.task_timeout(name)
          results[name] = self._fallback(personas[name], personas_tile[name])
        except Exception as e:
          self.log.task_failed(name, e)
          results[name] = self._fallback(personas[name], personas_tile[name])
    finally:
      executor.shutdown(wait=False)

    self.log.tick_summary(tick_id)
    return results

  def _fallback(self, persona, curr_tile):
    s = persona.scratch
    description = f"{s.act_description} @ {s.act_address}"
    return curr_tile, s.act_pronunciatio, description, None
