# PoC benchmark results

Run `python benchmark.py` (see its docstring) on each target machine and add
a section here. RTF = synthesis seconds per second of audio (lower is
better; < 1.0 means faster than real time).

## 2026-07-21 — investigation sandbox (Linux x86_64, 4 vCPU, no GPU)

**Engine: espeak-ng fallback** — the sandbox's network policy blocks
huggingface.co, so no candidate model weights could be downloaded here.
These numbers benchmark the *service pipeline* (HTTP, registry, cache,
WAV handling), not the recommended models. Rerun on the MacBook / RTX box
with kokoro / qwen3_tts for engine-representative numbers.

| Metric | fallback_male (en-gb) | fallback_female (en+f3) |
|---|---|---|
| Service cold start → healthy `/health` | 0.37 s | — |
| `/health` round-trip | 5–28 ms | 5 ms |
| Engine load ("model load") | < 0.01 s | — |
| First synthesis (9-word line, uncached) | 16 ms | 13 ms |
| Subsequent synthesis (60–200-char lines, median) | 20 ms | 19 ms |
| RTF | 0.002–0.007 | 0.002–0.006 |
| Cached repeat of same line | 1.9 ms | 1.8 ms |
| Full 16-line British corpus (2,039 chars) | 0.28 s total | — |
| Server process RSS after 40+ syntheses | 46 MB | — |
| Direct-mode client RSS (engine in-process) | 22 MB | — |
| GPU | n/a (no GPU present) | — |

Voice distinctness verified (different audio checksums for the same line
across `fallback_male` / `fallback_female` / `fallback_scots`).

## Template — MacBook Pro (Apple Silicon), engine: kokoro

```
python benchmark.py --engine kokoro --voice bf_isabella
python benchmark.py --server http://localhost:8020 --voice-id clara_wells
python synthesize_corpus.py --voice-id clara_wells   # then listen
```

| Metric | Value |
|---|---|
| Model load | _measure_ |
| First synthesis | _measure_ |
| Subsequent synthesis / RTF | _measure_ |
| RSS | _measure_ |

## Template — RTX 2070 desktop, engine: qwen3_tts

```
python benchmark.py --engine qwen3_tts --voice Ryan
python synthesize_corpus.py --voice-id qwen_test_male --with-instructions
nvidia-smi --query-gpu=memory.used --format=csv   # during synthesis
```

| Metric | Value |
|---|---|
| Model load (first run includes ~2.5 GB download) | _measure_ |
| First synthesis | _measure_ |
| Subsequent synthesis / RTF | _measure_ |
| VRAM used | _measure_ |
