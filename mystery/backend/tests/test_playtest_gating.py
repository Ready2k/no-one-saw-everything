"""Playtest/telemetry surfaces must be operator-only, enforced by the server.

MYSTERY_PLAYTEST_MODE previously only toggled a flag the FRONTEND read from
/api/config to decide whether to show the playtest panel — the endpoints
themselves (/api/session/log, /api/session/playtest-summary,
/api/session/playtest-export) had no server-side gate, so anyone could call
them directly regardless of the flag. There is deliberately no client request
that can flip this on; it is an environment variable only an operator sets.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PLAYTEST_ENDPOINTS = [
    "/api/session/log",
    "/api/session/playtest-summary",
    "/api/session/playtest-export",
    "/api/session/telemetry/durable",
]


@pytest.mark.parametrize("path", PLAYTEST_ENDPOINTS)
def test_playtest_endpoints_are_403_by_default(monkeypatch, path):
    monkeypatch.delenv("MYSTERY_PLAYTEST_MODE", raising=False)
    r = client.get(path)
    assert r.status_code == 403
    assert "MYSTERY_PLAYTEST_MODE" in r.json()["detail"]


@pytest.mark.parametrize("path", PLAYTEST_ENDPOINTS)
def test_playtest_endpoints_open_when_operator_enables_them(monkeypatch, path):
    monkeypatch.setenv("MYSTERY_PLAYTEST_MODE", "true")
    r = client.get(path)
    assert r.status_code == 200


def test_config_reports_the_live_flag_not_a_stale_import_time_value(monkeypatch):
    monkeypatch.delenv("MYSTERY_PLAYTEST_MODE", raising=False)
    assert client.get("/api/config").json()["playtest_mode"] is False
    monkeypatch.setenv("MYSTERY_PLAYTEST_MODE", "true")
    assert client.get("/api/config").json()["playtest_mode"] is True
