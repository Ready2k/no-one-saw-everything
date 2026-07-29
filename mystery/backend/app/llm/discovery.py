"""Auto-detects a live LLM host + model for the mystery module.

Probes known Ollama-compatible hosts via their /api/tags endpoint and uses
whatever model is actually registered and running, so the player doesn't
have to hand-configure a host/model to link a real LLM.

This module performs no network calls at import time — only when
detect_llm() is actually invoked with MYSTERY_LLM_PROVIDER=auto — so it never
affects tests or the default (mocked) game experience.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

from pydantic import BaseModel

from .http_safety import urlopen_no_redirect

# Known Ollama-compatible hosts on the local network, probed in order.
AVAILABLE_HOSTS = [
    {"id": "ollama-remote", "endpoint": "http://Desktop-HomePC.local:11434"},
    {"id": "vmlx-local-quality", "endpoint": "http://Jamess-MacBook-Pro-2.local:8001"},
    {"id": "vmlx-local-fast", "endpoint": "http://Jamess-MacBook-Pro-2.local:8002"},
]

_PROBE_TIMEOUT_SECONDS = 2.0
_CACHE_TTL_SECONDS = 30.0


class DetectedLLM(BaseModel):
    host_id: str
    endpoint: str
    model: str
    source: str  # "auto_probe"


def _fetch_json(url: str) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=_PROBE_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _models_for_host(endpoint: str) -> list[str]:
    data = _fetch_json(f"{endpoint}/api/tags")
    if not data:
        return []
    names = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    return sorted(names)


# User-driven "Refresh" checks a single endpoint (unlike the multi-host
# background auto-probe), so it can afford a longer timeout — mDNS ".local"
# hostname resolution in particular can take several seconds.
_USER_PROBE_TIMEOUT_SECONDS = 6.0


def _describe_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code} from server"
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        text = str(reason)
        if "nodename nor servname" in text or "Name or service not known" in text:
            return "Could not resolve hostname — check for typos, or try the IP address instead"
        if isinstance(reason, TimeoutError) or "timed out" in text.lower():
            return "Connection timed out — host may be unreachable from this machine"
        if "Connection refused" in text:
            return "Connection refused — is the server running on that port?"
        return f"Connection failed: {text}"
    if isinstance(exc, TimeoutError):
        return "Connection timed out — host may be unreachable from this machine"
    if isinstance(exc, ValueError):
        return "Server did not return valid JSON"
    return f"Connection failed: {exc}"


# A configured-but-unreachable host is indistinguishable, in the settings
# panel, from a working one: `get_llm_config()` reports configured=True and
# fallback_reason=None because it only reads settings, never the network. The
# panel then renders a green "Active" badge while every rewrite in the game is
# failing and silently falling back to deterministic text.
#
# This is the cheap check that closes that gap. Deliberately *not* wired into
# `get_llm_config()`, which is called on the interview/challenge/free-text hot
# path — a network probe there would put a timeout in front of every question
# the player asks. It runs only on an explicit settings read, behind a short
# TTL so opening the panel repeatedly doesn't hammer the host.
_REACHABILITY_TTL_SECONDS = 15.0

# How long a settings read is willing to *wait* for the answer, as opposed to
# how long the probe itself may take. These are different numbers because a
# socket timeout does not bound name resolution: an unresolvable mDNS ".local"
# host blocks in the resolver for ~5s before the 2s socket timeout is ever
# consulted (measured). Blocking the panel that long would replace a wrong
# answer with a hang, so the probe runs on a daemon thread and the request
# waits only this long for it, reporting "unknown" if it is still going. The
# thread finishes into the cache regardless, so the next read has the answer.
_REACHABILITY_DEADLINE_SECONDS = 2.0

_reachability_cache: dict[str, tuple[float, bool, Optional[str]]] = {}
_reachability_inflight: dict[str, threading.Event] = {}
_reachability_lock = threading.Lock()


def _probe_endpoint_blocking(base_url: str, api_key: Optional[str]) -> tuple[bool, Optional[str]]:
    request = urllib.request.Request(f"{base_url.rstrip('/')}/models")
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urlopen_no_redirect(request, timeout=_PROBE_TIMEOUT_SECONDS):
            return True, None
    except urllib.error.HTTPError:
        # Something served us a response. A 401/404 is a credentials or path
        # problem, not the "this host does not exist" case that silently ruins
        # a session — and that distinction is the whole point of this check.
        return True, None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return False, _describe_error(e)


def endpoint_reachable(
    base_url: str, api_key: Optional[str] = None, *, force: bool = False
) -> tuple[Optional[bool], Optional[str]]:
    """Is this LLM host answering? Returns (reachable, detail).

    `reachable` is None when the probe has not come back within the deadline —
    genuinely unknown, which the panel must show as such rather than guessing
    either way.
    """
    from .config import normalize_base_url

    if not base_url:
        return False, "No endpoint configured"

    base_url = normalize_base_url(base_url)
    with _reachability_lock:
        cached = _reachability_cache.get(base_url)
        if cached and not force and (time.monotonic() - cached[0]) < _REACHABILITY_TTL_SECONDS:
            return cached[1], cached[2]

        done = _reachability_inflight.get(base_url)
        if done is None:
            done = threading.Event()
            _reachability_inflight[base_url] = done

            def run() -> None:
                result = _probe_endpoint_blocking(base_url, api_key)
                with _reachability_lock:
                    _reachability_cache[base_url] = (time.monotonic(), *result)
                    _reachability_inflight.pop(base_url, None)
                done.set()

            threading.Thread(target=run, daemon=True, name="llm-reachability").start()

    if done.wait(_REACHABILITY_DEADLINE_SECONDS):
        with _reachability_lock:
            fresh = _reachability_cache.get(base_url)
        if fresh:
            return fresh[1], fresh[2]

    if cached:  # stale, but a real observation beats a shrug
        return cached[1], cached[2]
    return None, "Still checking this endpoint…"


def reset_reachability_cache() -> None:
    with _reachability_lock:
        _reachability_cache.clear()
        _reachability_inflight.clear()


def list_models_for_base_url(base_url: str, api_key: Optional[str] = None) -> tuple[list[str], Optional[str]]:
    """Auto-discovers models available at a user-supplied base_url, for the
    Custom (OpenAI-compatible) LLM Settings option. Tries Ollama's /api/tags
    against the host root first (works whether the user entered the bare
    host or the /v1 suffix), then falls back to the OpenAI-compatible
    /models list endpoint.

    Returns (models, error). error is a human-readable reason set only when
    both attempts failed and no models were found.
    """
    from .config import normalize_base_url

    base_url = normalize_base_url(base_url)
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]

    last_error: Optional[str] = None

    try:
        with urlopen_no_redirect(f"{root}/api/tags", timeout=_USER_PROBE_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        names = sorted(m.get("name", "") for m in data.get("models", []) if m.get("name"))
        if names:
            return names, None
        last_error = "Endpoint responded but reported no models"
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        last_error = _describe_error(e)

    url = f"{base_url.rstrip('/')}/models"
    req = urllib.request.Request(url)
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urlopen_no_redirect(req, timeout=_USER_PROBE_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        names = sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))
        if names:
            return names, None
        last_error = "Endpoint responded but reported no models"
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        last_error = _describe_error(e)

    return [], last_error


def _detect_uncached() -> Optional[DetectedLLM]:
    # Probe every known host in order and use the first one that's actually
    # up with models registered.
    for host in AVAILABLE_HOSTS:
        available = _models_for_host(host["endpoint"])
        if available:
            return DetectedLLM(
                host_id=host["id"], endpoint=host["endpoint"],
                model=available[0], source="auto_probe",
            )

    return None


_cache: Optional[tuple[float, Optional[DetectedLLM]]] = None


def detect_llm(force: bool = False) -> Optional[DetectedLLM]:
    """Finds a live LLM host+model, or None if nothing is reachable.

    Cached for a short TTL so repeated calls within a game session (roughly
    one per interview question / challenge) don't re-probe hosts on the
    network every time.
    """
    global _cache
    now = time.monotonic()
    if not force and _cache is not None and (now - _cache[0]) < _CACHE_TTL_SECONDS:
        return _cache[1]

    result = _detect_uncached()
    _cache = (now, result)
    return result


def reset_cache() -> None:
    """Clears the detection cache. Used by tests and to force re-probing."""
    global _cache
    _cache = None
