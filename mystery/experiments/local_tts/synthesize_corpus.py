"""Render the British-English test corpus to WAV files for listening.

    python synthesize_corpus.py --server http://localhost:8020 \
        --voice-id clara_wells --out out/clara

Writes one WAV per corpus line (out/<voice>/<line_id>.wav) plus a summary
of per-line latency. Listen for: accent plausibility (British, not American
or ambiguous), abbreviation expansion, £ amounts, hesitation delivery.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

from british_test_lines import INSTRUCTIONS, TEST_LINES


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://localhost:8020")
    parser.add_argument("--voice-id", default="fallback_male")
    parser.add_argument("--out", default=None, help="output dir (default out/<voice-id>)")
    parser.add_argument("--with-instructions", action="store_true",
                        help="send per-line emotion instructions (qwen3_tts voices)")
    args = parser.parse_args()

    out_dir = Path(args.out or f"out/{args.voice_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    base = args.server.rstrip("/")

    total_chars = 0
    total_s = 0.0
    for line_id, category, text in TEST_LINES:
        payload = {"text": text, "voice_id": args.voice_id, "no_cache": True}
        if args.with_instructions and line_id in INSTRUCTIONS:
            payload["instruction"] = INSTRUCTIONS[line_id]
        req = urllib.request.Request(
            f"{base}/synthesize",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=300) as resp:
            wav = resp.read()
        elapsed = time.perf_counter() - start
        (out_dir / f"{line_id}.wav").write_bytes(wav)
        total_chars += len(text)
        total_s += elapsed
        print(f"{line_id:18s} {category:38s} {elapsed*1000:7.1f} ms  {len(wav)/1024:7.1f} KiB")

    print(f"\n{len(TEST_LINES)} lines, {total_chars} chars, {total_s:.2f}s total → {out_dir}/")


if __name__ == "__main__":
    main()
