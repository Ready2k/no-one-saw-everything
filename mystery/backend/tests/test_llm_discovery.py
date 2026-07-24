"""Tests for LLM auto-detection (app.llm.discovery) and the 'auto' provider."""

import pytest

from app.llm import discovery
from app.llm.discovery import AVAILABLE_HOSTS, DetectedLLM


@pytest.fixture(autouse=True)
def reset_discovery_cache():
    discovery.reset_cache()
    yield
    discovery.reset_cache()


def test_probes_hosts_in_order(monkeypatch):
    def fake_models(endpoint):
        # Only the second host in the list responds.
        if endpoint == AVAILABLE_HOSTS[1]["endpoint"]:
            return ["some-model:latest"]
        return []

    monkeypatch.setattr(discovery, "_models_for_host", fake_models)
    result = discovery.detect_llm()
    assert result is not None
    assert result.source == "auto_probe"
    assert result.host_id == AVAILABLE_HOSTS[1]["id"]
    assert result.model == "some-model:latest"


def test_returns_none_when_nothing_reachable(monkeypatch):
    monkeypatch.setattr(discovery, "_models_for_host", lambda endpoint: [])
    assert discovery.detect_llm() is None


def test_detection_is_cached(monkeypatch):
    calls = {"n": 0}

    def fake_models(endpoint):
        calls["n"] += 1
        return ["model:latest"] if endpoint == AVAILABLE_HOSTS[0]["endpoint"] else []

    monkeypatch.setattr(discovery, "_models_for_host", fake_models)
    discovery.detect_llm()
    discovery.detect_llm()
    discovery.detect_llm()
    assert calls["n"] == 1, "repeated calls within the TTL should not re-probe"

    discovery.detect_llm(force=True)
    assert calls["n"] == 2, "force=True should bypass the cache"


# ---------------------------------------------------------------------------
# get_llm_config() "auto" branch
# ---------------------------------------------------------------------------

def test_config_auto_provider_success(monkeypatch):
    from app.llm.config import get_llm_config
    import app.llm.discovery as discovery_module

    monkeypatch.setenv("MYSTERY_LLM_PROVIDER", "auto")
    monkeypatch.setattr(
        discovery_module, "detect_llm",
        lambda: DetectedLLM(
            host_id="ollama-remote",
            endpoint="http://Desktop-HomePC.local:11434",
            model="qwen2.5-coder:7b",
            source="auto_probe",
        ),
    )

    cfg = get_llm_config()
    assert cfg.provider == "openai_compatible"
    assert cfg.base_url == "http://Desktop-HomePC.local:11434/v1"
    assert cfg.model == "qwen2.5-coder:7b"
    assert cfg.configured is True
    assert cfg.dialogue_enabled is True  # auto-on when a live model is found
    assert cfg.detected_source == "auto_probe"


def test_config_auto_provider_respects_explicit_dialogue_override(monkeypatch):
    from app.llm.config import get_llm_config
    import app.llm.discovery as discovery_module

    monkeypatch.setenv("MYSTERY_LLM_PROVIDER", "auto")
    monkeypatch.setenv("MYSTERY_LLM_DIALOGUE_ENABLED", "false")
    monkeypatch.setattr(
        discovery_module, "detect_llm",
        lambda: DetectedLLM(
            host_id="ollama-remote",
            endpoint="http://Desktop-HomePC.local:11434",
            model="qwen2.5-coder:7b",
            source="auto_probe",
        ),
    )

    cfg = get_llm_config()
    assert cfg.dialogue_enabled is False


def test_config_auto_provider_falls_back_when_nothing_found(monkeypatch):
    from app.llm.config import get_llm_config
    import app.llm.discovery as discovery_module

    monkeypatch.setenv("MYSTERY_LLM_PROVIDER", "auto")
    monkeypatch.setattr(discovery_module, "detect_llm", lambda: None)

    cfg = get_llm_config()
    assert cfg.provider == "fake"
    assert cfg.configured is False
    assert cfg.fallback_reason == "no_llm_host_reachable"
    assert cfg.dialogue_enabled is False  # old default preserved on fallback


def test_config_default_unset_provider_never_probes_network(monkeypatch):
    """The bare default (no MYSTERY_LLM_PROVIDER set) must stay 'fake' and
    must not import/call discovery at all, so tests and the default game
    experience are never network-dependent."""
    from app.llm.config import get_llm_config
    import app.llm.discovery as discovery_module

    monkeypatch.delenv("MYSTERY_LLM_PROVIDER", raising=False)

    def boom():
        raise AssertionError("discovery.detect_llm should not be called for the default provider")

    monkeypatch.setattr(discovery_module, "detect_llm", boom)
    cfg = get_llm_config()
    assert cfg.provider == "fake"
