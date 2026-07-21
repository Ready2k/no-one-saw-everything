# Local TTS proof of concept

Companion code for `docs/local_tts_investigation.md`. A standalone FastAPI
service that turns text into WAV speech through interchangeable local
engines. **Nothing in the game is modified** — this directory is isolated on
purpose, and the game runs identically whether or not this service exists.

```
server.py               FastAPI service: /health /voices /synthesize /preview
voices.json             Voice registry (voice_id → engine + preset + defaults)
engines/                Adapters: espeak (zero-download), kokoro, piper, qwen3_tts
british_test_lines.py   Standard British-English evaluation corpus
synthesize_corpus.py    Render the corpus to WAVs for listening
benchmark.py            Load-time / latency / RTF / memory harness
sentences.py            Sentence splitter for future per-sentence synthesis
BENCHMARKS.md           Recorded results per machine
```

## Install and run (all platforms)

```bash
cd mystery/experiments/local_tts
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt          # fastapi + uvicorn only
# fallback engine needs the espeak-ng binary:
sudo apt install espeak-ng        # Linux
brew install espeak-ng            # macOS

.venv/bin/uvicorn server:app --port 8020
```

Smoke test (works immediately, no model downloads — uses the espeak
fallback engine, which is intentionally robotic; it proves the pipeline,
not the voice quality):

```bash
curl http://localhost:8020/health
curl http://localhost:8020/voices
curl -X POST http://localhost:8020/synthesize \
     -H 'Content-Type: application/json' \
     -d '{"text": "I never entered the pub that evening.", "voice_id": "fallback_male"}' \
     -o reply.wav
# fallback_female / fallback_scots for distinguishable second voices
```

## Real engines

### Kokoro-82M (recommended first engine — British voices, Apache-2.0)

```bash
.venv/bin/pip install -r requirements-kokoro.txt   # torch + kokoro
.venv/bin/uvicorn server:app --port 8020
# first synthesis downloads ~330 MB from Hugging Face, then fully offline
curl -X POST http://localhost:8020/synthesize \
     -H 'Content-Type: application/json' \
     -d '{"text": "It happened at quarter past seven.", "voice_id": "clara_wells"}' \
     -o clara.wav
```

Registry voices `narrator` (bm_george), `clara_wells` (bf_isabella),
`village_male_2` (bm_lewis), `village_female_2` (bf_emma) all use Kokoro's
British set.

### Qwen3-TTS 0.6B CustomVoice (emotion engine — CUDA recommended)

```bash
.venv/bin/pip install -r requirements-qwen.txt
# optional, CUDA only: .venv/bin/pip install flash-attn --no-build-isolation
QWEN_TTS_DEVICE=cuda .venv/bin/uvicorn server:app --port 8020
curl -X POST http://localhost:8020/synthesize \
     -H 'Content-Type: application/json' \
     -d '{"text": "I was not anywhere near the storage room.",
          "voice_id": "qwen_test_male",
          "instruction": "Nervous, defensive, speaking quietly"}' \
     -o nervous.wav
```

`QWEN_TTS_MODEL` overrides the default `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`.
On Apple Silicon set `QWEN_TTS_DEVICE=mps` (unofficial — upstream documents
CUDA only) or prefer the MLX route discussed in the investigation doc.

### Piper (lightweight fallback, GPL-3.0)

```bash
.venv/bin/pip install -r requirements-piper.txt
.venv/bin/python -m piper.download_voices en_GB-alan-medium --data-dir models/piper
```

## Evaluation

```bash
# British-English corpus → one WAV per line in out/<voice_id>/
.venv/bin/python synthesize_corpus.py --voice-id clara_wells
.venv/bin/python synthesize_corpus.py --voice-id qwen_test_male --with-instructions

# Benchmarks (paste results into BENCHMARKS.md)
.venv/bin/python benchmark.py --engine kokoro --voice bf_isabella
.venv/bin/python benchmark.py --server http://localhost:8020 --voice-id clara_wells

# Sentence-splitter self-check
.venv/bin/python sentences.py
```

## Serving over the LAN (RTX desktop → MacBook)

```bash
.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8020
# then from the game machine: http://<desktop-ip>:8020/synthesize
```

## Notes

- The cache (`cache/`) is deterministic: same engine+voice+instruction+text
  ⇒ same file. Delete the directory to clear it. Capped at 500 MB, LRU.
- `cache/`, `out/`, `models/` and all audio/weight files are gitignored —
  do not commit model weights or generated audio.
- Cancellation: abort the HTTP request (browser `AbortController`); the
  service checks for disconnects before starting expensive work.
- One synthesis runs at a time by design (predictable VRAM); queued
  requests wait on an internal lock, `/health` reports `queue_depth`.
