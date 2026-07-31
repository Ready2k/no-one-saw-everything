"""Memoises a rewrite on its exact inputs, so a turn can be paid for early.

The safety property that makes this worth having is that **the cache can only
change how long an answer takes, never what it says**. The key is the complete
input tuple to `rewrite_interview_answer` plus the identity of the model that
would answer it, so a hit is only possible when every input is byte-identical
and a miss simply falls through to the ordinary path. There is no staleness
window and no invalidation rule to get wrong: if anything about the turn
differs — pressure, ask count, what the player has discovered, the configured
model — the key differs and the cache is silent.

Only *successful* rewrites are stored. A fallback is usually a transient
provider failure or a sanitiser rejection worth re-attempting, and caching it
would freeze one bad moment into every future turn with the same inputs.

Cleared on session reset so a playtest never inherits the previous run's
dialogue.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from typing import Any, Optional

# Bounded because a long interrogation touches many distinct inputs and this
# lives for the life of the process. Oldest-first eviction; the useful entries
# are the recent ones, since prefetch warms exactly what is about to be asked.
MAX_ENTRIES = 512

_cache: "OrderedDict[str, Any]" = OrderedDict()
_lock = threading.Lock()
_stats = {"hits": 0, "misses": 0, "stores": 0}


def _stable(value: Any) -> Any:
    """JSON-ready form of an input, stable across runs (no id()/set ordering)."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_stable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _stable(v) for k, v in sorted(value.items())}
    if hasattr(value, "model_dump"):
        return _stable(value.model_dump())
    return repr(value)


def make_key(**inputs: Any) -> str:
    blob = json.dumps(_stable(inputs), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def get(key: str) -> Optional[Any]:
    with _lock:
        hit = _cache.get(key)
        if hit is None:
            _stats["misses"] += 1
            return None
        _cache.move_to_end(key)
        _stats["hits"] += 1
        return hit


def put(key: str, result: Any) -> None:
    with _lock:
        _cache[key] = result
        _cache.move_to_end(key)
        _stats["stores"] += 1
        while len(_cache) > MAX_ENTRIES:
            _cache.popitem(last=False)


def stats() -> dict[str, int]:
    with _lock:
        return dict(_stats, size=len(_cache))


def reset_rewrite_cache() -> None:
    with _lock:
        _cache.clear()
        for k in _stats:
            _stats[k] = 0
