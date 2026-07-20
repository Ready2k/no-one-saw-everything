"""LLM settings endpoints let a client make the SERVER issue arbitrary HTTP
requests and, until now, handed the saved API key back to any caller.

Two production-risk findings from the audit, guarded here:
  - GET /api/llm-settings must never return the plaintext api_key.
  - A client-supplied base_url pointing at a cloud metadata address
    (credential-theft SSRF) must be refused before any request is made.

PUT must also not silently erase a saved key just because a later save omits
it — the client is never given the real key back, so it cannot resend it.
"""

import pytest
from fastapi.testclient import TestClient

import app.llm.config as llm_config
from app.main import app

client = TestClient(app)


# Captured before any test runs, so it is immune to conftest's autouse stub
# (which replaces app.llm.config.load_saved_settings with `lambda: None` for
# every test in the suite — these tests need the real, disk-backed one).
_REAL_LOAD_SAVED_SETTINGS = llm_config.load_saved_settings


@pytest.fixture(autouse=True)
def isolated_settings_file(tmp_path, monkeypatch, mock_llm_saved_settings):
    """Undo conftest's global 'no saved settings' stub and point the real
    save/load functions at a throwaway file, so these tests can exercise the
    actual persistence path the endpoints use. Depending on
    `mock_llm_saved_settings` (conftest's autouse fixture) guarantees this
    fixture's override applies AFTER conftest's, not before."""
    settings_file = tmp_path / "llm_settings.json"
    monkeypatch.setattr(llm_config, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(llm_config, "load_saved_settings", _REAL_LOAD_SAVED_SETTINGS)
    yield settings_file


def test_get_llm_settings_never_returns_the_plaintext_key():
    client.put(
        "/api/llm-settings",
        json={
            "provider": "openai_compatible",
            "base_url": "http://localhost:11434/v1",
            "api_key": "sk-super-secret-token",
            "model": "llama3",
            "dialogue_enabled": False,
        },
    )
    r = client.get("/api/llm-settings")
    assert r.status_code == 200
    body = r.json()
    assert "sk-super-secret-token" not in str(body)
    assert body["saved"]["api_key_set"] is True
    assert body["saved"]["api_key_last4"] == "oken"
    assert "api_key" not in body["saved"]


def test_saving_without_a_key_keeps_the_previously_saved_key():
    client.put(
        "/api/llm-settings",
        json={
            "provider": "openai_compatible",
            "base_url": "http://localhost:11434/v1",
            "api_key": "sk-original-key",
            "model": "llama3",
            "dialogue_enabled": False,
        },
    )
    # A later save changes only the model, sending no api_key (the client was
    # never given the real one back, so it never sends it unless the operator
    # deliberately typed a new one).
    r = client.put(
        "/api/llm-settings",
        json={
            "provider": "openai_compatible",
            "base_url": "http://localhost:11434/v1",
            "model": "llama3.1",
            "dialogue_enabled": False,
        },
    )
    assert r.status_code == 200
    assert r.json()["saved"]["api_key_set"] is True

    saved_on_disk = llm_config.load_saved_settings()
    assert saved_on_disk.api_key == "sk-original-key"
    assert saved_on_disk.model == "llama3.1"


@pytest.mark.parametrize(
    "path,method,body",
    [
        ("/api/llm-settings", "PUT", {"provider": "openai_compatible", "base_url": "http://169.254.169.254/", "model": "m"}),
        ("/api/llm-settings/models", "POST", {"base_url": "http://169.254.169.254/latest/meta-data/"}),
        ("/api/llm-settings/test", "POST", {"base_url": "http://169.254.169.254/", "model": "m"}),
        ("/api/llm-settings/models", "POST", {"base_url": "http://metadata.google.internal/computeMetadata/v1/"}),
    ],
)
def test_cloud_metadata_targets_are_refused_before_any_request(path, method, body):
    r = client.request(method, path, json=body)
    assert r.status_code == 400
    assert "metadata" in r.json()["detail"].lower()


def test_saved_endpoints_use_the_stored_key_without_the_client_supplying_one(monkeypatch):
    client.put(
        "/api/llm-settings",
        json={
            "provider": "openai_compatible",
            "base_url": "http://localhost:11434/v1",
            "api_key": "sk-only-on-the-server",
            "model": "llama3",
            "dialogue_enabled": False,
        },
    )

    seen = {}

    def fake_list_models(base_url, api_key):
        seen["base_url"] = base_url
        seen["api_key"] = api_key
        return (["llama3"], None)

    monkeypatch.setattr("app.llm.discovery.list_models_for_base_url", fake_list_models)

    r = client.post("/api/llm-settings/models/saved")
    assert r.status_code == 200
    assert r.json()["models"] == ["llama3"]
    # The server used the real saved key server-side; the client's request
    # body carried no key at all (there was no request body).
    assert seen["api_key"] == "sk-only-on-the-server"


def test_saved_test_endpoint_404s_cleanly_with_no_saved_config():
    r = client.post("/api/llm-settings/test/saved")
    assert r.status_code == 400
    r2 = client.post("/api/llm-settings/models/saved")
    assert r2.status_code == 400
