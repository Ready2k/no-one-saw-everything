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


def normalize_base_url(base_url: str) -> str:
    """Users often paste a bare host:port (e.g. copied from Ollama docs)
    without a scheme, which urllib rejects outright. Default to http://."""
    base_url = base_url.strip()
    if base_url and not base_url.startswith(("http://", "https://")):
        return f"http://{base_url}"
    return base_url


def load_saved_settings() -> SavedLLMSettings | None:
    try:
        if SETTINGS_FILE.exists():
            return SavedLLMSettings(**json.loads(SETTINGS_FILE.read_text()))
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to read saved LLM settings, ignoring: {e}")
    return None


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
    )
