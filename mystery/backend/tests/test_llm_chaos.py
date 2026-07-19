"""Chaos tests for the LLM layer: whatever the provider does, the game holds.

The pipeline contract is: Deterministic Result → optional LLM rewrite →
sanitiser → display text. These tests attack each failure mode a real provider
exhibits — dead hosts, hangs, garbage bodies, schema-shaped nonsense, and the
worst case, fluent text that leaks the truth — and assert the player always
receives the authored line, never an error and never a leak.
"""

import http.server
import json
import socket
import threading
import time

import pytest

import app.llm.dialogue_rewriter as rewriter_module
from app.case_store import get_case
from app.llm.client import FakeLLMClient, OpenAICompatibleLLMClient
from app.llm.dialogue_rewriter import rewrite_interview_answer


def _clara(case):
    return next(a for a in case.agents if a.agent_id == "agent_clara")


def _rewrite(case, agent, deterministic="I was at the fountain from about 07:45."):
    return rewrite_interview_answer(
        case=case,
        agent=agent,
        question_text="Where were you during the murder window?",
        deterministic_text=deterministic,
        allowed_facts=[deterministic],
        pressure_level=0.2,
    )


# ---------------------------------------------------------------------------
# Transport chaos against the real HTTP client
# ---------------------------------------------------------------------------

def _serve(handler_cls) -> tuple[http.server.HTTPServer, str]:
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_dead_host_is_an_error_not_a_hang():
    # A port nothing listens on: connection refused, promptly.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]
    client = OpenAICompatibleLLMClient(
        base_url=f"http://127.0.0.1:{free_port}", api_key=None, model="m"
    )
    started = time.monotonic()
    with pytest.raises(Exception):
        client.generate_chat(
            messages=[{"role": "user", "content": "hi"}], schema=None, timeout_seconds=2
        )
    assert time.monotonic() - started < 5


def test_hanging_provider_is_cut_off_by_the_timeout():
    class Hang(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            time.sleep(5)  # never answers within the 1s timeout

        def log_message(self, *a):
            pass

    server, url = _serve(Hang)
    try:
        client = OpenAICompatibleLLMClient(base_url=url, api_key=None, model="m")
        started = time.monotonic()
        with pytest.raises(Exception):
            client.generate_chat(
                messages=[{"role": "user", "content": "hi"}], schema=None, timeout_seconds=1
            )
        assert time.monotonic() - started < 5, "timeout did not fire"
    finally:
        server.shutdown()


@pytest.mark.parametrize(
    "body",
    [
        b"<html>502 Bad Gateway</html>",
        b"{ this is not json",
        json.dumps({"choices": []}).encode(),  # valid JSON, wrong shape
        json.dumps({"choices": [{"message": {"content": "not the json you wanted"}}]}).encode(),
    ],
    ids=["html-error-page", "broken-json", "empty-choices", "non-schema-content"],
)
def test_garbage_provider_bodies_fall_back_to_the_authored_line(monkeypatch, body):
    class Garbage(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server, url = _serve(Garbage)
    try:
        real_client = OpenAICompatibleLLMClient(base_url=url, api_key=None, model="m")
        monkeypatch.setattr(rewriter_module, "get_llm_client", lambda: real_client)
        case = get_case("case_001")
        result = _rewrite(case, _clara(case))
        assert result.fallback_used is True
        assert "I was at the fountain" in result.rewritten_text
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# Content chaos: fluent text that leaks
# ---------------------------------------------------------------------------

def test_invented_confession_is_rejected(monkeypatch):
    """The nightmare rewrite: no role label, no authored forbidden phrase, just
    the model confessing on the suspect's behalf. Must never reach the player."""
    confession = "All right. I killed him — I hit Marcus and left him in the storage room."
    monkeypatch.setattr(
        rewriter_module,
        "get_llm_client",
        lambda: FakeLLMClient(override_response={"rewritten_text": confession}),
    )
    case = get_case("case_001")
    result = _rewrite(case, _clara(case))
    assert result.fallback_used is True
    assert result.fallback_reason == "validation_failed"
    assert "killed" not in result.rewritten_text.lower()


def test_authored_confession_wording_may_be_paraphrased(monkeypatch):
    """The guard must not strangle the real confession beat: when the authored
    line itself says 'killed', a paraphrase reusing the word is legitimate."""
    authored = "Yes. I killed him. I hit him with the till weight and I left him."
    paraphrase = "I killed him with the till weight. There. Now you know."
    monkeypatch.setattr(
        rewriter_module,
        "get_llm_client",
        lambda: FakeLLMClient(override_response={"rewritten_text": paraphrase}),
    )
    case = get_case("case_001")
    result = _rewrite(case, _clara(case), deterministic=authored)
    assert result.fallback_used is False
    assert result.rewritten_text == paraphrase


def test_victim_blame_shift_is_rejected(monkeypatch):
    """Naming another villager the grounded answer never mentioned is a
    hallucinated sighting, even without violence words."""
    monkeypatch.setattr(
        rewriter_module,
        "get_llm_client",
        lambda: FakeLLMClient(
            override_response={"rewritten_text": "Ask Owen where he was — I saw him by the alley."}
        ),
    )
    case = get_case("case_001")
    result = _rewrite(case, _clara(case))
    assert result.fallback_used is True
    assert "Owen" not in result.rewritten_text
