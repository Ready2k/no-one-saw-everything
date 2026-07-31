"""A thinking model must not spend the player's turn thinking.

Measured on `gemma4:latest` rewriting one line of dialogue: ~1,800 characters
of hidden reasoning for ~220 characters of speech, median 12.5s per turn.
With `reasoning_effort: "none"` the same prompt returns in 1.6s and the
sanitiser accepts it at exactly the same rate — so the reasoning bought
latency and nothing else.

The parameter is an OpenAI-API one, not universal, so it cannot simply be sent
to every configured endpoint. These tests pin the probe-and-remember behaviour
that makes it safe to try.
"""

import json
import urllib.error

import pytest
from pydantic import BaseModel

import app.llm.client as clientmod
from app.llm.client import OpenAICompatibleLLMClient, reset_reasoning_probe


class Reply(BaseModel):
    rewritten_text: str


@pytest.fixture(autouse=True)
def _clear_probe():
    reset_reasoning_probe()
    yield
    reset_reasoning_probe()


class _Response:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


OK = {"choices": [{"message": {"content": '{"rewritten_text": "I was in early."}'}}]}


def _spy(monkeypatch, responder):
    """Capture every outgoing payload; `responder(payload)` returns or raises."""
    sent = []

    def fake_urlopen(req, timeout=None):
        payload = json.loads(req.data.decode())
        sent.append(payload)
        return responder(payload)

    monkeypatch.setattr(clientmod, "urlopen_no_redirect", fake_urlopen)
    return sent


def _client():
    return OpenAICompatibleLLMClient(
        base_url="http://host.invalid/v1", api_key=None, model="gemma4:latest"
    )


def test_reasoning_is_suppressed_by_default(monkeypatch):
    sent = _spy(monkeypatch, lambda _p: _Response(OK))

    _client().generate_json(system_prompt="s", user_prompt="u", schema=Reply)

    assert sent[0]["reasoning_effort"] == "none", (
        "a thinking model would spend the turn reasoning instead of answering"
    )


def test_an_endpoint_that_rejects_the_field_still_works(monkeypatch):
    """A server that 400s on the unknown parameter must not take the whole
    feature down with it — the turn has to complete."""
    def responder(payload):
        if "reasoning_effort" in payload:
            raise urllib.error.HTTPError("u", 400, "Unrecognized argument", {}, None)
        return _Response(OK)

    sent = _spy(monkeypatch, responder)
    result = _client().generate_json(system_prompt="s", user_prompt="u", schema=Reply)

    assert result.rewritten_text == "I was in early."
    assert len(sent) == 2, "expected one rejected attempt then a clean retry"
    assert "reasoning_effort" not in sent[1]


def test_the_rejection_is_remembered_not_re_probed_every_turn(monkeypatch):
    """One extra request per configuration is acceptable. One per interview
    question is not."""
    def responder(payload):
        if "reasoning_effort" in payload:
            raise urllib.error.HTTPError("u", 400, "Unrecognized argument", {}, None)
        return _Response(OK)

    sent = _spy(monkeypatch, responder)
    client = _client()
    for _ in range(4):
        client.generate_json(system_prompt="s", user_prompt="u", schema=Reply)

    with_field = [p for p in sent if "reasoning_effort" in p]
    assert len(with_field) == 1, f"probed {len(with_field)} times, expected 1"
    assert len(sent) == 5, "1 failed probe + 4 real calls"


def test_a_supporting_endpoint_keeps_getting_the_field(monkeypatch):
    sent = _spy(monkeypatch, lambda _p: _Response(OK))
    client = _client()
    for _ in range(3):
        client.generate_json(system_prompt="s", user_prompt="u", schema=Reply)

    assert all("reasoning_effort" in p for p in sent)


def test_a_real_error_is_not_swallowed_as_a_probe_failure(monkeypatch):
    """If the endpoint is simply broken, both attempts fail and the caller must
    hear about it rather than getting a silent empty turn."""
    def responder(_payload):
        raise urllib.error.HTTPError("u", 500, "Server Error", {}, None)

    _spy(monkeypatch, responder)

    with pytest.raises(RuntimeError):
        _client().generate_json(system_prompt="s", user_prompt="u", schema=Reply)


def test_the_probe_is_tracked_per_model(monkeypatch):
    """Two models behind one host can differ; a rejection by one must not
    disable the field for the other."""
    def responder(payload):
        if payload["model"] == "picky" and "reasoning_effort" in payload:
            raise urllib.error.HTTPError("u", 400, "nope", {}, None)
        return _Response(OK)

    sent = _spy(monkeypatch, responder)
    OpenAICompatibleLLMClient("http://host.invalid/v1", None, "picky").generate_json(
        system_prompt="s", user_prompt="u", schema=Reply)
    sent.clear()
    OpenAICompatibleLLMClient("http://host.invalid/v1", None, "gemma4:latest").generate_json(
        system_prompt="s", user_prompt="u", schema=Reply)

    assert "reasoning_effort" in sent[0]


def test_generate_chat_suppresses_reasoning_too(monkeypatch):
    """Both request paths matter — challenges and open-ended replies go through
    generate_chat, and a ten-second pause is no better there."""
    sent = _spy(monkeypatch, lambda _p: _Response(OK))

    _client().generate_chat(messages=[{"role": "user", "content": "hi"}], schema=Reply)

    assert sent[0]["reasoning_effort"] == "none"
