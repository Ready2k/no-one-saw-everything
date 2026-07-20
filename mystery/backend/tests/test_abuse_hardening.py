"""Basic abuse hardening: request size limits and rate limiting on the routes
that cost the server real work (LLM-backed calls, case generation) — none of
this existed before; anyone could hammer /api/cases/generate or the LLM
settings probes in a tight loop, and no route capped body size at all.
"""

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.rate_limit import RateLimiter

client = TestClient(app)


# ---------------------------------------------------------------------------
# RateLimiter unit behaviour
# ---------------------------------------------------------------------------

def test_rate_limiter_allows_up_to_the_cap_then_blocks():
    clock = {"t": 0.0}
    limiter = RateLimiter(max_requests=3, window_seconds=60, time_func=lambda: clock["t"])
    assert [limiter.allow("a") for _ in range(3)] == [True, True, True]
    assert limiter.allow("a") is False


def test_rate_limiter_is_per_key():
    clock = {"t": 0.0}
    limiter = RateLimiter(max_requests=1, window_seconds=60, time_func=lambda: clock["t"])
    assert limiter.allow("player-a") is True
    assert limiter.allow("player-b") is True
    assert limiter.allow("player-a") is False


def test_rate_limiter_window_slides():
    clock = {"t": 0.0}
    limiter = RateLimiter(max_requests=1, window_seconds=10, time_func=lambda: clock["t"])
    assert limiter.allow("a") is True
    assert limiter.allow("a") is False
    clock["t"] = 10.1
    assert limiter.allow("a") is True


# ---------------------------------------------------------------------------
# Endpoint-level enforcement
# ---------------------------------------------------------------------------

def test_case_generation_is_rate_limited_per_player(monkeypatch):
    monkeypatch.setattr(main, "_generate_rate_limiter", RateLimiter(max_requests=2, window_seconds=60))
    headers = {"X-Session-Id": "abuse_test_player_1"}
    body = {"case_type": "blackmail", "difficulty": "standard", "seed": 1, "mode": "deterministic"}

    assert client.post("/api/cases/generate", json=body, headers=headers).status_code == 200
    assert client.post("/api/cases/generate", json=body, headers=headers).status_code == 200
    r = client.post("/api/cases/generate", json=body, headers=headers)
    assert r.status_code == 429
    assert "Retry-After" in r.headers

    # A different player has their own quota.
    other = {"X-Session-Id": "abuse_test_player_2"}
    assert client.post("/api/cases/generate", json=body, headers=other).status_code == 200


def test_free_text_ask_is_rate_limited_per_player(monkeypatch):
    monkeypatch.setattr(main, "_llm_rate_limiter", RateLimiter(max_requests=1, window_seconds=60))
    headers = {"X-Session-Id": "abuse_test_player_3"}
    body = {"agent_id": "agent_clara", "question": "Where were you?"}

    assert client.post("/api/interview/free-text", json=body, headers=headers).status_code == 200
    r = client.post("/api/interview/free-text", json=body, headers=headers)
    assert r.status_code == 429


def test_llm_settings_probe_is_rate_limited(monkeypatch):
    monkeypatch.setattr(main, "_llm_rate_limiter", RateLimiter(max_requests=1, window_seconds=60))
    headers = {"X-Session-Id": "abuse_test_player_4"}
    assert client.post("/api/llm-settings/probe", headers=headers).status_code == 200
    assert client.post("/api/llm-settings/probe", headers=headers).status_code == 429


# ---------------------------------------------------------------------------
# Request body size limit
# ---------------------------------------------------------------------------

def test_oversized_declared_content_length_is_rejected(monkeypatch):
    monkeypatch.setattr(main, "_MAX_REQUEST_BYTES", 100)
    huge = {"title": "x" * 1000, "body": ""}
    r = client.post("/api/notes", json=huge)
    assert r.status_code == 413


def test_body_within_limit_is_accepted(monkeypatch):
    monkeypatch.setattr(main, "_MAX_REQUEST_BYTES", 100_000)
    r = client.post("/api/notes", json={"title": "fine", "body": "also fine"})
    assert r.status_code == 200


def test_dev_routes_get_a_higher_body_size_limit(monkeypatch):
    # A body well within the general cap but declared oversized should still
    # be rejected for a non-dev route, while the dev-prefixed route's own
    # (much higher) limit is unaffected by the general one.
    monkeypatch.setattr(main, "_MAX_REQUEST_BYTES", 10)
    monkeypatch.setattr(main, "_MAX_DEV_REQUEST_BYTES", 10_000_000)
    r = client.post("/api/notes", json={"title": "x", "body": "y"})
    assert r.status_code == 413
    # The dev route itself 403s (disabled by default) rather than 413 — proves
    # the request body was allowed through to the handler under the dev limit.
    r_dev = client.post("/api/dev/map-editor/layout", json={"small": "payload"})
    assert r_dev.status_code == 403
