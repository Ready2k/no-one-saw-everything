"""The settings panel must not report a dead endpoint as healthy.

`get_llm_config()` computes `configured` from saved settings alone — it never
touches the network, because it runs on the interview/challenge/free-text hot
path and a probe there would put a timeout in front of every question the
player asks. The consequence was that a host which does not resolve still
produced `configured: true, fallback_reason: null`, and the panel rendered a
green "Active" badge while every rewrite in the game failed and fell back to
deterministic text with nothing on screen saying so.
"""

import threading
import time
import urllib.error

import pytest
from fastapi.testclient import TestClient

import app.llm.discovery as discovery
from app.llm.config import LLMConfig
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_probe_cache():
    discovery.reset_reachability_cache()
    yield
    discovery.reset_reachability_cache()


def _config(**overrides):
    base = dict(
        provider="openai_compatible", base_url="http://llm.invalid:11434/v1",
        api_key=None, model="test-model", timeout_seconds=60, configured=True,
        fallback_reason=None, dialogue_enabled=True,
    )
    base.update(overrides)
    return lambda: LLMConfig(**base)


# ---------------------------------------------------------------------------
# The probe itself
# ---------------------------------------------------------------------------

def test_unreachable_host_reports_a_usable_reason(monkeypatch):
    def boom(*a, **k):
        raise urllib.error.URLError("[Errno 8] nodename nor servname provided, or not known")

    monkeypatch.setattr(discovery, "urlopen_no_redirect", boom)
    reachable, detail = discovery.endpoint_reachable("http://llm.invalid:11434/v1")

    assert reachable is False
    assert "resolve" in (detail or "").lower(), detail


def test_an_http_error_still_counts_as_reachable(monkeypatch):
    """A 401 or 404 means something answered. That is a credentials or path
    problem, not the "this host does not exist" case that silently ruins a
    session — and conflating them is what this check exists to avoid."""
    def unauthorized(*a, **k):
        raise urllib.error.HTTPError("http://x/models", 401, "Unauthorized", {}, None)

    monkeypatch.setattr(discovery, "urlopen_no_redirect", unauthorized)
    reachable, _ = discovery.endpoint_reachable("http://llm.invalid:11434/v1")

    assert reachable is True


def test_result_is_cached_so_opening_the_panel_does_not_hammer_the_host(monkeypatch):
    calls = []

    def counted(*a, **k):
        calls.append(1)
        raise urllib.error.URLError("nope")

    monkeypatch.setattr(discovery, "urlopen_no_redirect", counted)
    for _ in range(5):
        discovery.endpoint_reachable("http://llm.invalid:11434/v1")

    assert len(calls) == 1, f"probed {len(calls)} times, expected 1 (cached)"


def test_a_slow_probe_does_not_block_the_caller(monkeypatch):
    """A socket timeout does not bound name resolution — an unresolvable mDNS
    host blocks in the resolver for ~5s. The caller must not wait that long;
    it reports "unknown" and the background thread fills the cache."""
    released = threading.Event()

    def slow(*a, **k):
        released.wait(10)
        raise urllib.error.URLError("eventually")

    monkeypatch.setattr(discovery, "urlopen_no_redirect", slow)
    monkeypatch.setattr(discovery, "_REACHABILITY_DEADLINE_SECONDS", 0.2)

    started = time.monotonic()
    reachable, detail = discovery.endpoint_reachable("http://slow.invalid:11434/v1")
    waited = time.monotonic() - started
    released.set()

    assert reachable is None, "an unfinished probe is unknown, not a guess either way"
    assert waited < 2.0, f"caller blocked for {waited:.2f}s"
    assert detail


def test_a_missing_endpoint_is_not_reachable():
    assert discovery.endpoint_reachable("") == (False, "No endpoint configured")


# ---------------------------------------------------------------------------
# What the settings endpoint reports
# ---------------------------------------------------------------------------

def test_settings_endpoint_admits_the_host_is_down(monkeypatch):
    monkeypatch.setattr("app.llm.config.get_llm_config", _config())
    monkeypatch.setattr(
        discovery, "urlopen_no_redirect",
        lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("nodename nor servname")),
    )

    effective = client.get("/api/llm-settings").json()["effective"]

    assert effective["configured"] is True, "settings are filled in — that part was never wrong"
    assert effective["reachable"] is False
    assert effective["fallback_reason"] == "host_unreachable"
    assert effective["health_detail"]


def test_settings_endpoint_reports_a_live_host_as_healthy(monkeypatch):
    class _Response:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr("app.llm.config.get_llm_config", _config())
    monkeypatch.setattr(discovery, "urlopen_no_redirect", lambda *a, **k: _Response())

    effective = client.get("/api/llm-settings").json()["effective"]

    assert effective["reachable"] is True
    assert effective["fallback_reason"] is None


def test_an_unfinished_probe_is_never_reported_as_unreachable(monkeypatch):
    """`reachable` is None while the probe is still running. Treating that as
    falsy would make the panel claim the host is down when we simply do not
    know yet — the same overclaiming this whole change exists to remove."""
    released = threading.Event()

    def slow(*a, **k):
        released.wait(10)
        raise urllib.error.URLError("eventually")

    monkeypatch.setattr("app.llm.config.get_llm_config", _config())
    monkeypatch.setattr(discovery, "urlopen_no_redirect", slow)
    monkeypatch.setattr(discovery, "_REACHABILITY_DEADLINE_SECONDS", 0.2)

    effective = client.get("/api/llm-settings").json()["effective"]
    released.set()

    assert effective["reachable"] is None
    assert effective["fallback_reason"] is None, "claimed a failure it had not observed"


def test_no_probe_runs_for_the_offline_default(monkeypatch):
    """The default build talks to nobody. A settings read must not start
    reaching out to the network just because the panel was opened."""
    def forbidden(*a, **k):
        raise AssertionError("probed the network with no endpoint configured")

    monkeypatch.setattr(discovery, "urlopen_no_redirect", forbidden)
    monkeypatch.setattr(
        "app.llm.config.get_llm_config",
        _config(provider="fake", base_url=None, configured=True, dialogue_enabled=False),
    )

    effective = client.get("/api/llm-settings").json()["effective"]

    assert effective["reachable"] is None, "nothing to check, so nothing is claimed"


def test_the_interview_hot_path_never_probes(monkeypatch):
    """The whole reason this lives on the settings read: a probe in
    get_llm_config() would sit in front of every question the player asks."""
    def forbidden(*a, **k):
        raise AssertionError("interview turn hit the network for a reachability probe")

    monkeypatch.setattr(discovery, "urlopen_no_redirect", forbidden)
    client.post("/api/session/reset")
    response = client.post(
        "/api/interview/ask", json={"agent_id": "agent_clara", "question_type": "alibi"}
    )

    assert response.status_code == 200
    assert response.json()["answer_text"]


def test_a_degraded_session_is_visible(monkeypatch):
    """`Session.llm_unavailable` latches on the first provider error and drops
    the rest of the session to the no-LLM path. Correct, but it was invisible."""
    from app.session import get_session
    import app.main as main_module

    monkeypatch.setattr("app.llm.config.get_llm_config", _config(provider="fake", base_url=None))

    assert client.get("/api/llm-settings").json()["effective"]["session_degraded"] is False
    get_session(main_module.ACTIVE_CASE_ID).llm_unavailable = True
    assert client.get("/api/llm-settings").json()["effective"]["session_degraded"] is True
