"""Local TTS proof-of-concept service for the Mystery game.

Run:  uvicorn server:app --port 8020            (from experiments/local_tts/)
Docs: README.md in this directory.

Design mirrors docs/local_tts_investigation.md §7: plain HTTP in, complete
WAV out, deterministic disk cache, lazy per-engine loading, client-disconnect
cancellation. Deliberately no WebSockets, no job queue — see the report.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from engines import get_engine, loaded_engines

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("tts")

ROOT = Path(__file__).parent
CACHE_DIR = ROOT / "cache"
CACHE_MAX_BYTES = 500 * 1024 * 1024
STARTED_AT = time.time()

app = FastAPI(title="Mystery local TTS (PoC)", version="0.1.0")

# One synthesis at a time per process: every candidate engine saturates its
# device with a single job, and serialising is what keeps VRAM predictable.
_synthesis_lock = threading.Lock()
_queue_depth = 0
_queue_lock = threading.Lock()


def _load_registry() -> dict[str, dict]:
    data = json.loads((ROOT / "voices.json").read_text())
    return {v["voice_id"]: v for v in data["voices"] if v.get("enabled", True)}


VOICES = _load_registry()


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice_id: str
    instruction: str | None = None
    format: str = "wav"  # v1: wav only
    sample_rate: int | None = None  # hint; engines return their native rate
    no_cache: bool = False


def _cache_key(voice: dict, req: SynthesizeRequest) -> str:
    payload = json.dumps(
        {
            "engine": voice["engine"],
            "model": voice.get("model"),
            "voice_id": voice["voice_id"],
            "preset": voice.get("preset_voice"),
            "speed": voice.get("speed", 1.0),
            "instruction": req.instruction or voice.get("default_instruction") or "",
            "text": " ".join(req.text.split()),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / key[:2] / f"{key}.wav"


def _evict_if_needed() -> None:
    files = sorted(CACHE_DIR.glob("*/*.wav"), key=lambda p: p.stat().st_atime)
    total = sum(p.stat().st_size for p in files)
    while total > CACHE_MAX_BYTES and files:
        victim = files.pop(0)
        total -= victim.stat().st_size
        victim.unlink(missing_ok=True)
        victim.with_suffix(".json").unlink(missing_ok=True)


def _synthesize_blocking(voice: dict, req: SynthesizeRequest) -> tuple[bytes, int, str]:
    """Returns (wav_bytes, sample_rate, source) where source is cache|engine."""
    key = _cache_key(voice, req)
    path = _cache_path(key)
    if not req.no_cache and path.exists():
        path.touch()  # keep LRU honest on filesystems with noatime
        return path.read_bytes(), 0, "cache"

    engine = get_engine(voice["engine"])
    instruction = req.instruction or voice.get("default_instruction")
    with _synthesis_lock:
        wav, sample_rate = engine.synthesize(
            text=req.text,
            preset=voice["preset_voice"],
            instruction=instruction,
            speed=float(voice.get("speed", 1.0)),
        )

    if not req.no_cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(wav)
        path.with_suffix(".json").write_text(
            json.dumps(
                {
                    "voice_id": voice["voice_id"],
                    "engine": voice["engine"],
                    "chars": len(req.text),
                    "created": time.time(),
                }
            )
        )
        _evict_if_needed()
    return wav, sample_rate, "engine"


@app.get("/health")
def health() -> dict:
    engines_info = {name: engine.info() for name, engine in loaded_engines().items()}
    return {
        "status": "ok",
        "uptime_s": round(time.time() - STARTED_AT, 1),
        "queue_depth": _queue_depth,
        "engines": engines_info or {"note": "no engine loaded yet (lazy)"},
        "voices": len(VOICES),
    }


@app.get("/voices")
def voices() -> list[dict]:
    safe_fields = ("voice_id", "engine", "model", "preset_voice", "default_instruction", "speed")
    return [{k: v.get(k) for k in safe_fields} for v in VOICES.values()]


async def _handle(req: SynthesizeRequest, request: Request, cacheable: bool) -> Response:
    global _queue_depth
    voice = VOICES.get(req.voice_id)
    if voice is None:
        raise HTTPException(404, f"Unknown voice_id: {req.voice_id!r}")
    if req.format != "wav":
        raise HTTPException(400, "Only format='wav' is supported in the PoC")
    if not cacheable:
        req.no_cache = True

    # Cancellation: if the player has already navigated away by the time this
    # job reaches the front, don't burn GPU time on it.
    if await request.is_disconnected():
        raise HTTPException(499, "client disconnected")

    with _queue_lock:
        _queue_depth += 1
    start = time.perf_counter()
    try:
        wav, _, source = await asyncio.to_thread(_synthesize_blocking, voice, req)
    except (RuntimeError, KeyError, ImportError, ModuleNotFoundError) as e:
        logger.warning("synthesis failed voice=%s: %s", req.voice_id, e)
        raise HTTPException(503, f"Engine unavailable: {e}")
    finally:
        with _queue_lock:
            _queue_depth -= 1

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "voice=%s chars=%d source=%s %sms", req.voice_id, len(req.text), source, elapsed_ms
    )
    return Response(
        content=wav,
        media_type="audio/wav",
        headers={
            "X-TTS-Source": source,
            "X-TTS-Elapsed-Ms": str(elapsed_ms),
            "Cache-Control": "no-store",
        },
    )


@app.post("/synthesize")
async def synthesize(req: SynthesizeRequest, request: Request) -> Response:
    return await _handle(req, request, cacheable=True)


@app.post("/preview")
async def preview(req: SynthesizeRequest, request: Request) -> Response:
    """Uncached, length-capped synthesis for the settings screen."""
    if len(req.text) > 300:
        raise HTTPException(400, "Preview text is capped at 300 characters")
    return await _handle(req, request, cacheable=False)


@app.delete("/jobs/{job_id}")
def cancel_job(job_id: str) -> dict:
    """PoC stub: cancellation is by client disconnect (AbortController); a
    job-id registry only becomes necessary with sentence-level pipelining."""
    return {"job_id": job_id, "cancelled": False, "note": "cancel by closing the request"}
