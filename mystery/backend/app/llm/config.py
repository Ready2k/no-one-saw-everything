import os
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

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
    provider = os.environ.get("MYSTERY_LLM_PROVIDER", "fake").lower()
    base_url = os.environ.get("MYSTERY_LLM_BASE_URL")
    api_key = os.environ.get("MYSTERY_LLM_API_KEY")
    model = os.environ.get("MYSTERY_LLM_MODEL")
    timeout = int(os.environ.get("MYSTERY_LLM_TIMEOUT_SECONDS", "60"))
    dialogue_env = os.environ.get("MYSTERY_LLM_DIALOGUE_ENABLED")

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
