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

def get_llm_config() -> LLMConfig:
    provider = os.environ.get("MYSTERY_LLM_PROVIDER", "fake").lower()
    base_url = os.environ.get("MYSTERY_LLM_BASE_URL")
    api_key = os.environ.get("MYSTERY_LLM_API_KEY")
    model = os.environ.get("MYSTERY_LLM_MODEL")
    timeout = int(os.environ.get("MYSTERY_LLM_TIMEOUT_SECONDS", "60"))
    dialogue_enabled = os.environ.get("MYSTERY_LLM_DIALOGUE_ENABLED", "false").lower() == "true"

    if provider == "fake":
        return LLMConfig(
            provider="fake",
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout,
            configured=True,
            fallback_reason=None,
            dialogue_enabled=dialogue_enabled
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
                dialogue_enabled=dialogue_enabled
            )
        return LLMConfig(
            provider="openai_compatible",
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout,
            configured=True,
            fallback_reason=None,
            dialogue_enabled=dialogue_enabled
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
        dialogue_enabled=dialogue_enabled
    )
