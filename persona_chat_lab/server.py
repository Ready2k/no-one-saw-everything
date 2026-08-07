"""Stdlib-only local server for the persona chat lab. No pip installs needed.

Run:  python3 server.py
Open: http://localhost:8765

Layer 7 (LLM claim reasoning, see layer7.py) is off by default. To try it
against a local Ollama:
  PERSONA_LAB_CLAIM_REASONING_ENABLED=true python3 server.py
Optional: PERSONA_LAB_LLM_BASE_URL, PERSONA_LAB_LLM_MODEL (defaults match
mystery/backend's current llm_settings.json — a local llama3.1:8b).
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import layer7
from engine import PersonaSession
from personas import PERSONAS

STATIC_DIR = Path(__file__).parent / "static"

SESSIONS: dict[str, PersonaSession] = {key: PersonaSession(key) for key in PERSONAS}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep the console quiet

    def _send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            path = STATIC_DIR / "index.html"
        elif self.path == "/api/personas":
            self._send_json({
                key: {
                    "full_name": p["full_name"],
                    "occupation": p["occupation"],
                    "voice_card": p["voice_card"],
                    "traits": p["traits"],
                }
                for key, p in PERSONAS.items()
            })
            return
        else:
            self.send_response(404)
            self.end_headers()
            return

        if not path.exists():
            self.send_response(404)
            self.end_headers()
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/api/chat":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw)
                persona_key = data["persona"]
                question = data["question"]
            except (KeyError, json.JSONDecodeError):
                self._send_json({"error": "bad request"}, status=400)
                return
            if persona_key not in SESSIONS:
                self._send_json({"error": "unknown persona"}, status=404)
                return
            session = SESSIONS[persona_key]
            result = session.ask(question)
            # Layer 7 (ENGINE_SPEC.md §9, generative half only — see
            # layer7.py docstring): only worth a shot when Layer 4 found
            # nothing to say (topic is None) and there's more than one
            # already-revealed claim to actually connect. try_claim_reasoning
            # is a no-op (returns None) when disabled, so this costs nothing
            # when PERSONA_LAB_CLAIM_REASONING_ENABLED isn't set.
            if result["topic"] is None:
                persona = PERSONAS[persona_key]
                llm_answer = layer7.try_claim_reasoning(
                    full_name=persona["full_name"],
                    occupation=persona["occupation"],
                    voice_card=persona["voice_card"],
                    claims=session.claim_store.claims,
                    question=question,
                )
                if llm_answer:
                    result["answer"] = llm_answer
                    result["topic"] = "layer7"
                    result["source"] = "layer7"
                    session.history[-1] = (persona_key, llm_answer)
            self._send_json(result)
            return

        if self.path == "/api/reset":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {}
            persona_key = data.get("persona")
            if persona_key and persona_key in PERSONAS:
                SESSIONS[persona_key] = PersonaSession(persona_key)
            else:
                for key in PERSONAS:
                    SESSIONS[key] = PersonaSession(key)
            self._send_json({"ok": True})
            return

        self.send_response(404)
        self.end_headers()


def main():
    port = 8765
    httpd = ThreadingHTTPServer(("localhost", port), Handler)
    print(f"Persona chat lab running at http://localhost:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
