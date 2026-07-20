"""Request correlation: every response carries an X-Request-Id, and the
access-log line for that request is stamped with the SAME id — not "-", which
is what a reset-before-log ordering bug produces (the id existed only for the
brief window between setting it and prematurely clearing it)."""

import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_response_carries_a_request_id():
    r = client.get("/api/config")
    assert r.status_code == 200
    assert r.headers["x-request-id"]


def test_an_inbound_request_id_is_reused_not_replaced():
    r = client.get("/api/config", headers={"X-Request-Id": "caller-supplied-id"})
    assert r.headers["x-request-id"] == "caller-supplied-id"


def test_access_log_line_carries_the_real_request_id_not_the_reset_default(caplog):
    with caplog.at_level(logging.INFO, logger="app.main"):
        r = client.get("/api/config", headers={"X-Request-Id": "trace-me-1234"})

    access_records = [
        rec for rec in caplog.records if "GET /api/config" in rec.getMessage()
    ]
    assert access_records, "no access-log line was emitted"
    assert getattr(access_records[-1], "request_id", None) == "trace-me-1234"
    assert r.headers["x-request-id"] == "trace-me-1234"
