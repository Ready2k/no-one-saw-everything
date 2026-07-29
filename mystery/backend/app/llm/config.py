import json
import os
from pathlib import Path
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Settings saved from the in-game LLM Settings panel (App.tsx gear icon ->
# LlmSettingsModal). These override environment variables so the game can be
# configured without restarting the backend process or editing shell env.
SETTINGS_FILE = Path(__file__).parent.parent / "data" / "llm_settings.json"


class SavedLLMSettings(BaseModel):
    provider: str = "fake"  # "fake" | "auto" | "openai_compatible"
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    dialogue_enabled: bool = False
    # Spec 15 Phase C: offline belief-state updates between player actions.
    # Off by default; only effective when dialogue rewriting is also on.
    beliefs_enabled: bool = False
    # Layer 7 (ENGINE_SPEC §9): hand the model the agent's own claim history
    # and require it to cite which claims it drew on. Off by default because
    # the layer is specified as optional — the deterministic floor and the
    # plain flavour rewrite must behave identically whether or not it is on,
    # and a model that ignores the citation field would otherwise have every
    # answer rejected. Only effective when dialogue rewriting is also on.
    claim_reasoning_enabled: bool = False


def normalize_base_url(base_url: str) -> str:
    """Users often paste a bare host:port (e.g. copied from Ollama docs)
    without a scheme, which urllib rejects outright. Default to http://.
    Also auto-appends '/v1' path suffix if it's missing for OpenAI compatibility."""
    base_url = base_url.strip()
    if not base_url:
        return base_url
    if not base_url.startswith(("http://", "https://")):
        base_url = f"http://{base_url}"
    
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(base_url)
    if not parsed.path or parsed.path == "/":
        parsed = parsed._replace(path="/v1")
        base_url = urlunparse(parsed)
    return base_url


def load_saved_settings() -> SavedLLMSettings | None:
    try:
        if SETTINGS_FILE.exists():
            return SavedLLMSettings(**json.loads(SETTINGS_FILE.read_text()))
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to read saved LLM settings, ignoring: {e}")
    return None


# SECURITY NOTE: API keys are stored in plaintext in llm_settings.json.
# Acceptable for local single-player use. If distributing or hosting,
# switch to environment-variable-only storage.
def save_settings(settings: SavedLLMSettings) -> None:
    if settings.base_url:
        settings.base_url = normalize_base_url(settings.base_url)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(settings.model_dump_json(indent=2))


class LLMConfig(BaseModel):
    provider: str
    base_url: str | None
    api_key: str | None
    model: str | None
    timeout_seconds: int
    configured: bool
    fallback_reason: str | None
    dialogue_enabled: bool
    beliefs_enabled: bool = False
    claim_reasoning_enabled: bool = False
    detected_source: str | None = None  # how "auto" found this config, if it did

def get_llm_config() -> LLMConfig:
    saved = load_saved_settings()

    provider = (saved.provider if saved else None) or os.environ.get("MYSTERY_LLM_PROVIDER", "fake")
    provider = provider.lower()
    base_url = (saved.base_url if saved else None) or os.environ.get("MYSTERY_LLM_BASE_URL")
    api_key = (saved.api_key if saved else None) or os.environ.get("MYSTERY_LLM_API_KEY")
    model = (saved.model if saved else None) or os.environ.get("MYSTERY_LLM_MODEL")
    timeout = int(os.environ.get("MYSTERY_LLM_TIMEOUT_SECONDS", "60"))
    dialogue_env = "true" if (saved and saved.dialogue_enabled) else os.environ.get("MYSTERY_LLM_DIALOGUE_ENABLED")
    beliefs_env = "true" if (saved and saved.beliefs_enabled) else os.environ.get("MYSTERY_LLM_BELIEFS_ENABLED")
    beliefs_enabled = (beliefs_env or "false").lower() == "true"
    reasoning_env = (
        "true" if (saved and saved.claim_reasoning_enabled)
        else os.environ.get("MYSTERY_LLM_CLAIM_REASONING_ENABLED")
    )
    claim_reasoning_enabled = (reasoning_env or "false").lower() == "true"

    if provider == "fake":
        return LLMConfig(
            provider="fake",
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout,
            configured=True,
            fallback_reason=None,
            dialogue_enabled=(dialogue_env or "false").lower() == "true",
            beliefs_enabled=beliefs_enabled,
            claim_reasoning_enabled=claim_reasoning_enabled,
        )

    if provider == "auto":
        # Auto-detect a live host/model the same way the main simulation's
        # Inference Settings page does: prefer the user's saved selection,
        # else probe known hosts for whatever is actually running.
        from .discovery import detect_llm

        detected = detect_llm()
        if detected is not None:
            # A live model was found — default dialogue rewriting ON so
            # "auto" actually links the game to it, unless overridden.
            dialogue_enabled = (dialogue_env or "true").lower() == "true"
            return LLMConfig(
                provider="openai_compatible",
                base_url=f"{detected.endpoint}/v1",
                api_key=api_key,
                model=detected.model,
                timeout_seconds=timeout,
                configured=True,
                fallback_reason=None,
                dialogue_enabled=dialogue_enabled,
                beliefs_enabled=beliefs_enabled,
                claim_reasoning_enabled=claim_reasoning_enabled,
                detected_source=detected.source,
            )

        logger.warning("MYSTERY_LLM_PROVIDER=auto but no reachable LLM host was found.")
        return LLMConfig(
            provider="fake",
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout,
            configured=False,
            fallback_reason="no_llm_host_reachable",
            dialogue_enabled=(dialogue_env or "false").lower() == "true",
            beliefs_enabled=beliefs_enabled,
            claim_reasoning_enabled=claim_reasoning_enabled,
        )

    if provider == "openai_compatible":
        if not base_url or not model:
            logger.warning("LLM config missing base_url or model for openai_compatible provider.")
            return LLMConfig(
                provider="fake",
                base_url=base_url,
                api_key=api_key,
                model=model,
                timeout_seconds=timeout,
                configured=False,
                fallback_reason="llm_not_configured",
                dialogue_enabled=(dialogue_env or "false").lower() == "true",
                beliefs_enabled=beliefs_enabled,
                claim_reasoning_enabled=claim_reasoning_enabled,
            )
        return LLMConfig(
            provider="openai_compatible",
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout,
            configured=True,
            fallback_reason=None,
            dialogue_enabled=(dialogue_env or "false").lower() == "true",
            beliefs_enabled=beliefs_enabled,
            claim_reasoning_enabled=claim_reasoning_enabled,
        )

    logger.warning(f"Unknown LLM provider: {provider}")
    return LLMConfig(
        provider="fake",
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout,
        configured=False,
        fallback_reason="llm_not_configured",
        dialogue_enabled=(dialogue_env or "false").lower() == "true",
        beliefs_enabled=beliefs_enabled,
    )
