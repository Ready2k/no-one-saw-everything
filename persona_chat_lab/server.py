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
from speech import render_owen_speech, speech_path

STATIC_DIR = Path(__file__).parent / "static"
MYSTERY_ART_DIR = Path(__file__).parent.parent / "mystery" / "frontend" / "public" / "art"

# These are authored stills from the game, selected by the same pressure
# bands as the chat engine.  Keeping the lookup here (rather than accepting
# a path from the browser) makes the asset endpoint deliberately narrow.
PORTRAITS = {
    "owen": {
        # The case_005 set is the HD, photoreal Owen (not the older
        # illustrated portrait set in art/portraits/).
        "composed": "case_005/portraits/owen_price_calm.avif",
        "guarded": "case_005/portraits/owen_price_defensive.avif",
        "cornered": "case_005/portraits/owen_price_defensive.avif",
        "breaking": "case_005/portraits/owen_price_cracking.avif",
    },
    "owen_twin": {
        "composed": "case_005/portraits/owen_price_calm.avif",
        "guarded": "case_005/portraits/owen_price_defensive.avif",
        "cornered": "case_005/portraits/owen_price_defensive.avif",
        "breaking": "case_005/portraits/owen_price_cracking.avif",
    },
    "priya": {
        "composed": "portraits/priya_calm.avif", "guarded": "portraits/priya_defensive.avif",
        "cornered": "portraits/priya_defensive.avif", "breaking": "portraits/priya_cracking.avif",
    },
}

ANIMATIONS = {
    # First locally-rendered LivePortrait proof: HD Owen driven by a natural
    # motion performance. This is intentionally separate from reply audio;
    # the audio-viseme stage is the next integration step.
    # `_concat` is LivePortrait's three-panel diagnostic video. Serve the
    # output-only render; otherwise the UI shows the static source panel.
    "owen_demo": Path(__file__).parent / ".face-runtime" / "animations" / "owen_source--d0.mp4",
    "guarded": Path(__file__).parent / ".face-runtime" / "animations" / "owen_guarded.mp4",
    "considering": Path(__file__).parent / ".face-runtime" / "animations" / "owen_considering.mp4",
    "answering": Path(__file__).parent / ".face-runtime" / "animations" / "owen_answering.mp4",
}

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
                    "portraits": {
                        band: f"/api/portrait/{key}/{band}"
                        for band in PORTRAITS[key]
                    },
                }
                for key, p in PERSONAS.items()
            })
            return
        elif self.path.startswith("/api/portrait/"):
            _, _, _, persona_key, band = self.path.split("/", 4)
            filename = PORTRAITS.get(persona_key, {}).get(band)
            path = MYSTERY_ART_DIR / filename if filename else None
            if not path or not path.is_file():
                self.send_response(404)
                self.end_headers()
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/avif")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(body)
            return
        elif self.path.startswith("/api/animation/"):
            animation = self.path.rsplit("/", 1)[-1]
            path = ANIMATIONS.get(animation)
            if not path or not path.is_file():
                self.send_response(404)
                self.end_headers()
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        elif self.path.startswith("/api/audio/"):
            audio_id = self.path.rsplit("/", 1)[-1].removesuffix(".wav")
            path = speech_path(audio_id)
            if not path:
                self.send_response(404)
                self.end_headers()
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
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
            if persona_key in {"owen", "owen_twin"}:
                result["speech_audio_id"] = render_owen_speech(result["answer"])
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
