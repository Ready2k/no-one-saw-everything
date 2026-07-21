"""Benchmark harness — run the same script on every target machine.

Direct (no server), measures the engine itself:
    python benchmark.py --engine espeak --voice en-gb
    python benchmark.py --engine kokoro --voice bf_isabella
    python benchmark.py --engine qwen3_tts --voice Ryan

Against a running server (adds HTTP + cache behaviour):
    python benchmark.py --server http://localhost:8020 --voice-id fallback_male

Records: engine load time, first-synthesis latency (includes any lazy work),
subsequent latency, real-time factor (synthesis seconds per second of audio),
process RSS, and GPU memory via nvidia-smi when present. Appends a markdown
row you can paste into BENCHMARKS.md.
"""

from __future__ import annotations

import argparse
import io
import json
import platform
import resource
import statistics
import subprocess
import time
import urllib.request
import wave

from british_test_lines import INSTRUCTIONS, TEST_LINES

WARM_LINES = [t for _, _, t in TEST_LINES if len(t) > 60][:5]
FIRST_LINE = "I never entered the pub that evening."


def wav_duration_seconds(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes)) as w:
        return w.getnframes() / w.getframerate()


def rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is KiB on Linux, bytes on macOS.
    return round(usage / (1024 * 1024) if platform.system() == "Darwin" else usage / 1024, 1)


def gpu_mb() -> float | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        return float(out.stdout.strip().splitlines()[0]) if out.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
        return None


def bench_direct(engine_name: str, preset: str) -> dict:
    from engines import get_engine

    engine = get_engine(engine_name)
    t0 = time.perf_counter()
    engine.load()
    load_s = time.perf_counter() - t0

    def synth(text: str, line_id: str | None = None) -> tuple[float, float]:
        instruction = INSTRUCTIONS.get(line_id) if line_id else None
        t = time.perf_counter()
        wav, _ = engine.synthesize(text, preset, instruction, 1.0)
        elapsed = time.perf_counter() - t
        return elapsed, wav_duration_seconds(wav)

    first_s, first_audio_s = synth(FIRST_LINE)
    laters = [synth(line) for line in WARM_LINES]
    return {
        "mode": f"direct/{engine_name}/{preset}",
        "load_s": round(load_s, 2),
        "first_synth_s": round(first_s, 3),
        "first_rtf": round(first_s / first_audio_s, 3),
        "later_synth_s": round(statistics.median(s for s, _ in laters), 3),
        "later_rtf": round(statistics.median(s / a for s, a in laters), 3),
    }


def bench_server(base_url: str, voice_id: str) -> dict:
    def post(path: str, payload: dict) -> tuple[float, bytes]:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{base_url}{path}", data=body, headers={"Content-Type": "application/json"}
        )
        t = time.perf_counter()
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = resp.read()
        return time.perf_counter() - t, data

    t0 = time.perf_counter()
    with urllib.request.urlopen(f"{base_url}/health", timeout=10) as resp:
        json.loads(resp.read())
    health_s = time.perf_counter() - t0

    payload = {"text": FIRST_LINE, "voice_id": voice_id, "no_cache": True}
    first_s, wav = post("/synthesize", payload)
    first_audio_s = wav_duration_seconds(wav)
    laters = []
    for line in WARM_LINES:
        s, wav = post("/synthesize", {"text": line, "voice_id": voice_id, "no_cache": True})
        laters.append((s, wav_duration_seconds(wav)))
    # Cached repeat: same line twice, second hit must come from disk.
    post("/synthesize", {"text": FIRST_LINE, "voice_id": voice_id})
    cached_s, _ = post("/synthesize", {"text": FIRST_LINE, "voice_id": voice_id})
    return {
        "mode": f"server/{voice_id}",
        "health_roundtrip_s": round(health_s, 4),
        "first_synth_s": round(first_s, 3),
        "first_rtf": round(first_s / first_audio_s, 3),
        "later_synth_s": round(statistics.median(s for s, _ in laters), 3),
        "later_rtf": round(statistics.median(s / a for s, a in laters), 3),
        "cached_repeat_s": round(cached_s, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", help="direct mode: engine name")
    parser.add_argument("--voice", help="direct mode: engine preset name")
    parser.add_argument("--server", help="server mode: base URL, e.g. http://localhost:8020")
    parser.add_argument("--voice-id", help="server mode: registry voice_id")
    args = parser.parse_args()

    if args.server:
        result = bench_server(args.server.rstrip("/"), args.voice_id or "fallback_male")
    elif args.engine:
        result = bench_direct(args.engine, args.voice or "en-gb")
    else:
        parser.error("need --engine (direct) or --server (HTTP)")

    if args.engine:
        # RSS only means anything in direct mode — in server mode this
        # process is just an HTTP client; read the server's RSS separately
        # (e.g. `ps -o rss= -p <uvicorn pid>`).
        result["rss_mb"] = rss_mb()
    vram = gpu_mb()
    if vram is not None:
        result["gpu_used_mb"] = vram
    result["machine"] = f"{platform.system()} {platform.machine()}"

    print(json.dumps(result, indent=2))
    cells = " | ".join(f"{k}={v}" for k, v in result.items())
    print(f"\nmarkdown: | {cells} |")


if __name__ == "__main__":
    main()
