"""Auto-detects a live LLM host + model for the mystery module.

Ports the discovery approach from environment/frontend_server/translator/
ollama_utils.py (main branch): probe known Ollama-compatible hosts via their
/api/tags endpoint and use whatever model is actually registered and
running, so the player doesn't have to hand-configure a host/model to link a
real LLM. Also respects whatever host/model the user has already selected on
the main simulation's Inference Settings page, if that file is reachable
from this checkout.

This module performs no network calls at import time — only when
detect_llm() is actually invoked with MYSTERY_LLM_PROVIDER=auto — so it never
affects tests or the default (mocked) game experience.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from .http_safety import urlopen_no_redirect

# Same hosts as environment/frontend_server/translator/ollama_utils.py on
# main. Duplicated rather than imported: the mystery module is a standalone
# FastAPI service with its own venv and does not depend on the Django app.
AVAILABLE_HOSTS = [
    {"id": "ollama-remote", "endpoint": "http://Desktop-HomePC.local:11434"},
    {"id": "vmlx-local-quality", "endpoint": "http://Jamess-MacBook-Pro-2.local:8001"},
    {"id": "vmlx-local-fast", "endpoint": "http://Jamess-MacBook-Pro-2.local:8002"},
]

# The main simulation's shared inference selection, if this checkout has it
# (mystery/backend/app/llm/discovery.py -> repo root is 4 parents up).
_SHARED_SETTINGS_FILE = (
    Path(__file__).resolve().parents[4]
    / "environment" / "frontend_server" / "temp_storage" / "inference_settings.json"
)

_PROBE_TIMEOUT_SECONDS = 2.0
_CACHE_TTL_SECONDS = 30.0


class DetectedLLM(BaseModel):
    host_id: str
    endpoint: str
    model: str
    source: str  # "shared_settings" | "shared_settings_model_unavailable" | "auto_probe"


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


def _read_shared_settings() -> Optional[dict]:
    try:
        if _SHARED_SETTINGS_FILE.exists():
            return json.loads(_SHARED_SETTINGS_FILE.read_text())
    except (OSError, ValueError):
        pass
    return None


def _host_endpoint(host_id: str) -> Optional[str]:
    return next((h["endpoint"] for h in AVAILABLE_HOSTS if h["id"] == host_id), None)


def _detect_uncached() -> Optional[DetectedLLM]:
    # 1. Prefer whatever the user already selected on the main sim's
    #    Inference Settings page, if that host is actually reachable.
    shared = _read_shared_settings()
    if shared and shared.get("host_id") and shared.get("model"):
        endpoint = _host_endpoint(shared["host_id"])
        if endpoint:
            available = _models_for_host(endpoint)
            if available:
                wanted = shared["model"]
                if wanted in available:
                    return DetectedLLM(
                        host_id=shared["host_id"], endpoint=endpoint,
                        model=wanted, source="shared_settings",
                    )
                # Saved model isn't currently registered on this host (e.g.
                # it was removed) — use whatever IS running rather than
                # failing outright.
                match = next(
                    (m for m in available if wanted in m or m in wanted), None
                )
                return DetectedLLM(
                    host_id=shared["host_id"], endpoint=endpoint,
                    model=match or available[0],
                    source="shared_settings_model_unavailable",
                )

    # 2. Nothing usable from shared settings — probe every known host in
    #    order and use the first one that's actually up with models
    #    registered.
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
