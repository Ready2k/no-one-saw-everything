"""Utilities for fetching and managing LLM hosts, models, and inference settings."""
import json
import os
import time
import requests
from datetime import datetime

# Unified inference settings file
SETTINGS_FILE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "temp_storage",
    "inference_settings.json"
)

# Available LLM hosts
AVAILABLE_HOSTS = [
    {
        "id": "ollama-remote",
        "label": "Ollama (Remote)",
        "endpoint": "http://Desktop-HomePC.local:11434",
        "description": "Ollama server on Desktop-HomePC (RTX 2070)"
    },
    {
        "id": "vmlx-local-quality",
        "label": "vMLX Quality (Local)",
        "endpoint": "http://Jamess-MacBook-Pro-2.local:8001",
        "description": "MLX on MacBook Pro M4 - Quality (Qwen 27B)"
    },
    {
        "id": "vmlx-local-fast",
        "label": "vMLX Fast (Local)",
        "endpoint": "http://Jamess-MacBook-Pro-2.local:8002",
        "description": "MLX on MacBook Pro M4 - Fast (Gemma 12B)"
    },
]

# Default values
DEFAULT_HOST_ID = "ollama-remote"
DEFAULT_MODEL = "qwen2.5-coder-14b"
DEFAULT_PROFILE = "chat-large"

# Available prompt profiles (must match LAUNCHER_PROFILES in views.py)
AVAILABLE_PROFILES = [
    {"value": "chat-small", "label": "chat-small", "hint": "local small model (Gemma 4B)"},
    {"value": "chat-large", "label": "chat-large", "hint": "local large model (Qwen 14B)"},
    {"value": "gpt",        "label": "gpt",        "hint": "OpenAI GPT-3.5/4"},
    {"value": "cloud",      "label": "cloud",      "hint": "cloud API"},
]


def get_host_by_id(host_id):
    """Get host config by ID."""
    for host in AVAILABLE_HOSTS:
        if host["id"] == host_id:
            return host
    return None


def get_endpoint_url(host_id):
    """Get the full /v1 endpoint URL for a host."""
    host = get_host_by_id(host_id)
    if host:
        return f"{host['endpoint']}/v1"
    return None


def _ensure_settings_file():
    """Ensure the settings file exists."""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w") as f:
            json.dump({
                "host_id": DEFAULT_HOST_ID,
                "model": DEFAULT_MODEL,
                "profile": DEFAULT_PROFILE,
            }, f, indent=2)


def get_models_for_host(host_id):
    """Fetch available models from a specific LLM host.

    Args:
        host_id: Host ID (e.g., "ollama-remote", "vmlx-local-quality")

    Returns:
        list: [{"name": "model-name", "size": "7B", ...}, ...]
        or empty list if the server is unreachable
    """
    host = get_host_by_id(host_id)
    if not host:
        return []

    try:
        resp = requests.get(
            f"{host['endpoint']}/api/tags",
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            models = []
            for model in data.get("models", []):
                name = model.get("name", "")
                # Extract model name without tag (e.g., "qwen2.5-coder:14b" -> "qwen2.5-coder")
                display_name = name.split(":")[0] if ":" in name else name
                models.append({
                    "name": name,
                    "display_name": display_name,
                    "size": model.get("size", 0),
                    "modified": model.get("modified_at", ""),
                })
            return sorted(models, key=lambda m: m["display_name"])
    except Exception as e:
        print(f"[ollama_utils] Error fetching models from {host['label']}: {e}")
    return []


def get_settings():
    """Get all inference settings (host + model + profile)."""
    _ensure_settings_file()
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
        return {
            "host_id": settings.get("host_id", DEFAULT_HOST_ID),
            "model": settings.get("model", DEFAULT_MODEL),
            "profile": settings.get("profile", DEFAULT_PROFILE),
        }
    except Exception:
        return {
            "host_id": DEFAULT_HOST_ID,
            "model": DEFAULT_MODEL,
            "profile": DEFAULT_PROFILE,
        }


def get_selected_host_id():
    """Get the currently selected LLM host ID."""
    return get_settings()["host_id"]


def get_selected_model():
    """Get the currently selected model, with fallback to default."""
    return get_settings()["model"]


def get_selected_profile():
    """Get the currently selected prompt profile, with fallback to default."""
    return get_settings()["profile"]


def set_settings(host_id, model_name, profile_name):
    """Set host, model, and profile in the settings file."""
    _ensure_settings_file()
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
    except Exception:
        settings = {}

    settings["host_id"] = host_id
    settings["model"] = model_name
    settings["profile"] = profile_name
    settings["updated_at"] = datetime.now().isoformat()

    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

    return True


def get_api_base():
    """Get the /v1 endpoint URL for the selected host."""
    host_id = get_selected_host_id()
    return get_endpoint_url(host_id) or get_endpoint_url(DEFAULT_HOST_ID)


TEST_PROMPT = "Reply with one short sentence confirming you're working."


def test_llm(host_id, model, timeout=60):
    """Send a small chat-completion request to a host/model and time it.

    Returns a dict with ok, response_text, elapsed_seconds, completion_tokens
    (if the server reports usage), and tokens_per_second (derived from those).
    """
    host = get_host_by_id(host_id)
    if not host:
        return {"ok": False, "error": f"Unknown host: {host_id}"}

    url = f"{host['endpoint']}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": 100,
        "temperature": 0,
    }

    start = time.monotonic()
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        elapsed = time.monotonic() - start
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}
    except ValueError:
        return {"ok": False, "error": "Server returned a non-JSON response"}

    try:
        response_text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return {"ok": False, "error": f"Unexpected response format: {data}"}

    usage = data.get("usage") or {}
    completion_tokens = usage.get("completion_tokens")
    tokens_per_second = (
        completion_tokens / elapsed if completion_tokens and elapsed > 0 else None
    )

    return {
        "ok": True,
        "response_text": response_text,
        "elapsed_seconds": elapsed,
        "completion_tokens": completion_tokens,
        "tokens_per_second": tokens_per_second,
    }
