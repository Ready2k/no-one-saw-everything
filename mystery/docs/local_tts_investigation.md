# Local Text-to-Speech Investigation — *No One Saw Everything*

**Date:** 2026-07-21
**Status:** Investigation + proof of concept. No changes to the game itself.
**PoC location:** `experiments/local_tts/`

---

## 1. Executive summary and recommendation

| Question | Recommendation |
|---|---|
| Architecture | **Option B — a separate local TTS service** (FastAPI, port 8020), with a thin hybrid of Option C (deterministic disk cache means authored/repeated lines are effectively pre-generated after first play) |
| First engine | **Kokoro-82M** for the first release (genuine British voices, Apache-2.0, runs well on both target machines), with **Qwen3-TTS-12Hz-0.6B-CustomVoice** added as the *emotional-delivery* engine in phase 2 behind the same API |
| Which machine runs it | The **machine the game runs on** for Kokoro (it is light enough for the MacBook); the **RTX 2070 desktop over the LAN** when the Qwen engine is enabled |
| First release granularity | **Complete-response synthesis** (one WAV per reply). The game's interrogation flow is *not* streamed today — the full reply text arrives in one response — so sentence-level pipelining buys nothing yet. Sentence-level generation is phase 3, alongside any move to a streaming LLM flow |
| Deferred | Voice cloning (consent + storage policy first), true audio streaming, WebSockets, per-case bundled audio, ambient-voice mixing beyond simple ducking |
| Smallest safe sequence | 1) stand up the TTS service (PoC → hardened), 2) add a `SpeechManager` to the frontend that speaks the *last interrogation reply* with a toggle/stop/replay, 3) add narrator/autopsy speech, 4) add the Qwen engine + emotion instructions, 5) sentence-level pipelining |

The headline finding that shaped the recommendation: **Qwen3-TTS's preset voices contain no British English speaker** (its two English presets, Ryan and Aiden, are American-leaning). For a game set in an English village that matters more than raw model quality. Kokoro-82M ships eight dedicated British voices (`bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`, `bm_daniel`, `bm_fable`, `bm_george`, `bm_lewis`) at 1/8th the size. Qwen3-TTS still earns its place — it is the only candidate with **instruction-driven emotional delivery** ("nervous, defensive, speaking quietly"), which is exactly what interrogation replies want — but the honest path to British-sounding Qwen voices is the 1.7B VoiceDesign → Base-clone pipeline (design a synthetic British voice from a text description once, save the synthetic reference audio as a project-owned asset, then clone from it for consistency), which is heavier and should not gate the first release.

---

## 2. Existing application assessment

The Mystery game lives in `mystery/` on the `game` branch. FastAPI backend (`:8010`) + React 18/TypeScript/Vite frontend (`:5179`). No Docker; `./start.sh` bootstraps a venv and `npm install`, `./stop.sh` kills pids in `.pids/`.

### 2.1 What exists today (verified in code)

| Concern | Reality |
|---|---|
| Frontend framework | React 18 + TypeScript + Vite. `frontend/src/api.ts` is the single API client (plain `fetch`, JSON). `frontend/src/types.ts` mirrors backend schemas. |
| Audio playback | `frontend/src/audio.ts` — a Howler-based `AudioManager` singleton: ambient playlists, stingers with cooldowns, UI sounds, master mute/volume persisted in `localStorage`, and an **existing ducking pattern** (stingers fade ambient to 20 % and restore it — directly reusable for speech). `frontend/src/sfx.ts` synthesises diegetic UI sounds via WebAudio through Howler's master gain. Assets under `frontend/public/audio/` with a `manifest.json` (ambient / playlists / stingers / ui). |
| Backend framework | FastAPI, all routes in `backend/app/main.py` under `/api/*`. Pydantic v2 models in `models.py`. |
| LLM streaming | **There is none.** `backend/app/llm/client.py` uses blocking `urllib.request` calls returning complete JSON. The pipeline is: deterministic engine result → optional LLM rewrite → sanitiser (`dialogue_rewriter.py`) → full display text returned in one response. This is load-bearing for the TTS design: there is no token stream to piggyback on. |
| Interrogation flow | `POST /api/interview/ask` (structured) and `POST /api/interview/free-text` → `interview.answer_question` / `free_text_api.handle_free_text` → `public_ask_response()` returns `answer_text` (display text) in one JSON body. Frontend: `Suspects.tsx` `ask()` / `submitFreeText()` → `setLastResult(result)` renders the reply. **The natural TTS hook is the moment `setLastResult` fires.** |
| NPC identity / personality | `backend/app/data/case_00N/agents.json` per case; `models.py:Agent`. Agents already carry **`voice_card`** (a prose description of how they speak — e.g. Clara: *"Precise and clipped; clips her sentences even shorter when defensive"*), `pronoun`, `traits`, `age`, `occupation`, `baseline` (calm-manner spec), and `portrait_art` states (`calm`/`defensive`/`cracking`) that mirror the pressure bands. These map almost one-to-one onto a TTS instruction. |
| Emotional state | Session tracks per-agent `pressure`; frontend `demeanour.ts` derives calm/defensive/cracking. Stingers `pressure_defensive`/`pressure_cracking` already fire on band transitions in `Suspects.tsx`. The same signal can select the emotion instruction. |
| Case generation | `llm/mystery_architect.py` + `llm/schemas.py` + `case_assembler.py`; generated cases land in `data/gen_*/` as locked bundles. Character identities are generated in a best-effort phase — a voice-assignment phase can follow the same pattern. |
| Dialogue history | Yes — `session.py` keeps per-agent transcripts in memory (`sess.transcripts`, served by `GET /api/interview/{agent_id}`). Session is in-memory, one global session per case, reset via `/api/session/reset`. Nothing dialogue-related is persisted to disk. |
| Startup / env | `start.sh` / `stop.sh`; backend venv from `backend/requirements.txt` (fastapi, uvicorn, pydantic, pytest, httpx). LLM settings via env vars `MYSTERY_LLM_*` overridden by `data/llm_settings.json` (editable in-app via `LlmSettingsModal`). A TTS service should copy this exact config pattern (`MYSTERY_TTS_*` + saved settings). |
| Speech/microphone abstractions | None. No STT, no TTS, no microphone code anywhere. |
| Truth firewall | `projections.py` strips hidden fields at the API boundary; multiple no-leak tests guard it. **Constraint:** any text sent to a TTS service is player-visible display text only — never `deterministic_answer_text` internals, never truth fields. Voice config added to `Agent` must be classified player-safe or projected out. |

### 2.2 Integration file map (what would change, per phase)

Nothing below changes in this branch — this is the map for the implementation phases.

**New (phase 1):**
- `tts_service/` (promoted from `experiments/local_tts/`) — standalone FastAPI service: `server.py`, `engines/`, `voices.json`, cache dir.
- `frontend/src/speech.ts` — `SpeechManager`: fetch WAV from the service, queue, play through Howler, cancel, replay-last, speaking-state subscription.

**Modified (phase 1):**
- `frontend/src/audio.ts` — add a speech channel + duck/restore ambient while speech plays (copy the existing stinger-duck pattern at `audio.ts:242-250`).
- `frontend/src/views/Suspects.tsx` — call `speech.speak(...)` when `setLastResult`/`setLastChallenge` land; speaking indicator prop to `Portrait.tsx`; stop-speaking button; cancel on unmount/agent switch.
- `frontend/src/components/AudioControls.tsx` — "voice" toggle (auto-speak on/off) alongside mute.
- `frontend/src/settings.ts` — persisted speech prefs (`mystery_speech_enabled`, per-character overrides later).
- `frontend/src/api.ts` + `types.ts` — TTS client calls and types (or `speech.ts` talks to the service directly; see §7).
- `frontend/vite.config.ts` — dev proxy `/tts` → `http://localhost:8020` (mirrors the existing `/api` → `:8010` proxy).
- `start.sh` / `stop.sh` — optionally start/stop the TTS service (guarded by `MYSTERY_TTS_ENABLED`).

**Modified (phase 2 — voices per character, emotion):**
- `backend/app/models.py` — optional `voice: VoiceConfig | None` on `Agent` (player-safe).
- `backend/app/projections.py` — include `voice_id` (and only the safe fields) in `project_agent`.
- `backend/app/data/case_00N/agents.json` — voice assignments for hand-authored cases.
- `backend/app/llm/schemas.py` + `mystery_architect.py` + `case_assembler.py` — best-effort voice-assignment phase for generated cases (pick from the registry; never invent engine params).
- `frontend/src/views/Suspects.tsx` — pass pressure band → emotion instruction.
- `backend/app/main.py` — only if we choose the backend-proxy variant (`/api/tts/*` passthrough) or add TTS settings to the settings modal (`/api/tts-settings`, copying `llm_settings` handling in `main.py:114-253`).
- `frontend/src/views/LlmSettingsModal.tsx` (or a new `TtsSettingsModal`) — service URL, engine choice, voice previews.

**Modified (phase 3 — narrator/autopsy, sentence pipelining):**
- `frontend/src/views/Intro.tsx`, `Overview.tsx`, `AccusationCeremony.tsx` — narrator speech for scene descriptions and epilogues.
- `Suspects.tsx` autopsy panel (`~line 1244`) — forensic narration.
- `frontend/src/speech.ts` — sentence-buffered queue mode.

---

## 3. Engine research (official sources)

### 3.1 Qwen3-TTS (open-source, QwenLM) — [github.com/QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)

Open-sourced **22 January 2026**, Apache-2.0 (models + tokenizer). Built on the `Qwen3-TTS-Tokenizer-12Hz` codec (12 Hz frame rate; audio out is 24 kHz per the technical report). Installed via `pip install -U qwen-tts`. vLLM-Omni has day-0 support (offline inference only at time of writing).

| Model (Hugging Face) | What it does |
|---|---|
| `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` | 9 preset voices + **`instruct` parameter** for emotion/prosody control |
| `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | 3-second voice cloning (reference audio + transcript) |
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | Same as 0.6B CustomVoice, higher quality |
| `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | Free-form voice creation from a natural-language description |
| `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | Cloning + fine-tuning capable |

Key facts for our decision:

- **Instruction control is real and first-class**: `model.generate_custom_voice(text=…, language="English", speaker="Ryan", instruct="Speak nervously, quietly, hesitating")`. VoiceDesign takes full voice descriptions. This is the only candidate that can do "nervous, defensive, whispering, tired, frightened" on demand.
- **No British preset.** The 9 CustomVoice speakers are Chinese (Vivian, Serena, Uncle_Fu, Dylan, Eric), English–American (Ryan "dynamic", Aiden "sunny American male"), Japanese (Ono_Anna), Korean (Sohee). A British character voice requires VoiceDesign (1.7B only) or Base cloning from an authorised/synthetic British sample. An `instruct` like "speak with a British accent" is not a documented capability and must not be relied on (test it, but assume no).
- **Streaming**: the architecture is dual-track streaming-capable and the README quotes 97 ms first-packet latency, but the released `qwen-tts` package exposes **offline (complete-utterance) generation**; no public streaming inference API at the time of writing. vLLM-Omni: "only offline inference is supported. Online serving will be supported later." → *Do not design v1 around Qwen streaming.*
- **Hardware**: official examples are CUDA (`device_map="cuda:0"`, bf16, optional FlashAttention 2). No official MPS/CPU documentation. Community MLX ports exist for Apple Silicon (`mlx-audio` supports Qwen3-TTS, incl. 4/8-bit quantisation) but they are not official — treat as promising, verify locally.
- **Footprint** (community-reported, verify on target): 0.6B ≈ 2.5 GB weights, ~4–6 GB VRAM in practice; 1.7B ≈ 4.5 GB weights, ~4–8 GB VRAM; FlashAttention 2 reduces both. RTF ≈ 0.85–1.15 on mid-range GPUs (i.e. roughly real-time, not dramatically faster).

### 3.2 Qwen-Audio-3.0-TTS (announced ~20 July 2026) — **not a local option**

Distinct from Qwen3-TTS. Released by Tongyi Lab as **hosted models only** (`qwen-audio-3.0-tts-flash`, `-plus`) on Alibaba Cloud Model Studio: bidirectional WebSocket streaming API, 16 languages, up to 48 kHz output, first-packet ~300 ms (flash). **No model weights, no local inference code, no open licence** — DashScope SDK / raw WebSocket only. It therefore fails the hard constraint ("fully local, no required cloud dependency") and is excluded. Worth re-checking quarterly in case weights are released later, as happened with Qwen3-TTS.

### 3.3 Kokoro-82M — [huggingface.co/hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), [github.com/hexgrad/kokoro](https://github.com/hexgrad/kokoro)

82 M parameters, **Apache-2.0**, ~330 MB weights, 24 kHz output. `pip install kokoro` + system `espeak-ng` (G2P fallback). Actively maintained; topped TTS-Arena-style rankings for open small models in early 2026.

- **Eight British English voices** (`b` prefix): `bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`, `bm_daniel`, `bm_fable`, `bm_george`, `bm_lewis` — enough to cast a narrator + several villagers with distinct, consistent identities without any cloning.
- Runs **faster than real time on CPU**, trivially on any GPU, and on Apple Silicon (PyTorch MPS works for its non-autoregressive architecture; CPU alone is adequate).
- **No emotion/instruction control** — delivery is what the voice gives you (speed is adjustable; voice blending exists). Nervous/whispering/angry delivery is out of scope for Kokoro.
- No cloning (a feature, from a consent standpoint).

### 3.4 Piper — [github.com/OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl)

The original MIT `rhasspy/piper` was **archived October 2025**; development moved to the Open Home Foundation's `piper1-gpl` (latest v1.4.2, April 2026) — now **GPL-3.0**, and the foundation is actively seeking maintainers. VITS→ONNX, embedded espeak-ng phonemisation, tiny (voices ~20–120 MB), far faster than real time on CPU.

- Good en_GB voice set (e.g. `alan`, `alba`, `aru`, `cori`, `jenny_dioco`, `northern_english_male`, `semaine`, `southern_english_female`, `vctk`) — plausibly British, though flatter/more "assistant-like" prosody than Kokoro.
- No emotion control, no cloning.
- GPL-3.0 matters if the game is ever distributed as a combined closed-source product; as a separate local service invoked over HTTP it is comfortably isolated, but Kokoro's Apache-2.0 removes the question entirely. Maintenance risk is now the bigger flag.

### 3.5 Comparison and scoring

Scores 1–5 (5 best) against the stated decision criteria:

| Criterion | Qwen3 0.6B CustomVoice | Qwen3 1.7B CustomVoice | Qwen3 1.7B VoiceDesign(+Base clone) | Kokoro-82M | Piper (en_GB) |
|---|---|---|---|---|---|
| Voice quality | 4 | 5 | 5 | 4 | 3 |
| British English suitability | **2** (no UK preset) | **2** | 4 (designable) | **5** | 4 |
| Emotional control | 5 (instruct) | 5 | 5 | 1 | 1 |
| Voice consistency across a case | 4 (preset+instruct) | 4 | 3 (needs clone-ref discipline) | 5 (fixed voices) | 5 |
| Latency (target hw) | 3 (~RT on GPU) | 2–3 | 2 | 5 (≫RT even CPU) | 5 |
| Streaming readiness (today, official) | 2 | 2 | 2 | 2 (fast enough not to need it) | 3 |
| Apple Silicon support | 2 (official) / 4 (MLX community) | 2/3 | 2/3 | 5 | 5 |
| RTX 2070 8 GB support | 5 | 4 (fits, tight with FA2) | 4 | 5 | 5 |
| RAM/VRAM use | 3 | 2 | 2 | 5 | 5 |
| Installation difficulty | 3 (torch+FA2) | 3 | 3 | 4 (torch+espeak-ng) | 5 |
| Licence | 5 (Apache-2.0) | 5 | 5 | 5 (Apache-2.0) | 3 (GPL-3.0) |
| Maintenance activity | 5 (Qwen team) | 5 | 5 | 4 | 2 (seeking maintainers) |
| Integration complexity | 3 | 3 | 2 | 4 | 4 |
| Offline operation | 5 | 5 | 5 | 5 | 5 |
| **Total** | **51** | **49** | **49** | **59** | **55** |

Reading the table honestly: **Kokoro wins the first release** on British authenticity, footprint, licence and simplicity; **Qwen3-TTS is the only path to emotional delivery** and is worth adding as a second engine, on the GPU box, once the pipeline exists — starting with 0.6B CustomVoice (accepting Ryan/Aiden's accent for a test, or jumping straight to the VoiceDesign→Base British pipeline on the 1.7B if the accent is unacceptable, which it likely will be for this game). Piper remains the emergency fallback (or drops out entirely, since Kokoro already covers "light and reliable" with a better licence).

---

## 4. Hardware findings

### 4.1 Apple Silicon MacBook Pro (primary dev machine)

- **Kokoro**: runs on CPU faster than real time; PyTorch MPS also works. No unsupported-op issues expected (non-autoregressive). This is the recommended dev-machine engine.
- **Qwen3-TTS**: no official MPS/Metal support — official examples are CUDA-only. Three community paths, in order of promise: (1) **mlx-audio** (MLX-native port, 4/8-bit quantisation, reported 2–3 GB RAM for 1.7B quantised); (2) PyTorch MPS with `device_map="mps"` — plausible since it's a transformers stack, but expect possible CPU fallbacks in the codec decoder and slow autoregressive decoding; (3) plain CPU — expect well below real time. **Verdict: 0.6B is likely viable on the MacBook via MLX; treat as experimental until measured with `benchmark.py`.**
- **Piper**: trivial (CPU/ONNX).

### 4.2 RTX 2070 8 GB / 32 GB RAM desktop (optional inference server)

- **Qwen3-TTS 0.6B**: fits comfortably (community figures ~2.5 GB weights, ~4–6 GB VRAM working set in bf16; FA2 reduces further). *Recommended Qwen host.*
- **Qwen3-TTS 1.7B**: expected to fit in 8 GB in bf16 with FlashAttention 2 (~4.5 GB weights + KV/codec overhead) for single-stream synthesis; concurrency headroom is thin. Viable, verify; quantised vLLM-Omni later if needed.
- **Kokoro / Piper**: negligible load; could even share the box with an Ollama dialogue model — but note the dialogue LLM and TTS will contend for the same 8 GB if co-located; 0.6B TTS + a 7B-class LLM does not fit together comfortably. Prefer TTS-only on this GPU or accept sequential loading.
- Serving over LAN: fine — the service binds `0.0.0.0`, the game targets `MYSTERY_TTS_BASE_URL=http://<desktop>:8020`. Same trust model the game already uses for a LAN Ollama host in the LLM settings.

### 4.3 This investigation sandbox (what the PoC benchmarks actually cover)

This remote container is CPU-only (4 vcpu, 15 GB RAM) and its network policy **blocks huggingface.co and GitHub asset downloads** (PyPI is open). Model weights for Kokoro/Piper/Qwen could therefore not be fetched here. The PoC ships with a zero-download **espeak-ng fallback engine** (installed from apt) so the full service — API, voice registry, caching, cancellation, benchmark harness — runs and is measured end-to-end here, and the same `benchmark.py` reruns unchanged on the MacBook/RTX box once a real engine is installed. Sandbox numbers are in §11; they benchmark the *service pipeline*, not the recommended model, and are labelled as such.

---

## 5. Architecture options

### Option A — TTS inside the existing game backend

The FastAPI game process loads the model and serves audio from `/api/*`.

- **Startup**: adds model load (seconds for Kokoro; tens of seconds for Qwen + torch import) to a backend that currently starts instantly; `./start.sh` restarts (which the workspace rules require after every backend change) become painful.
- **Memory contention**: torch + weights permanently resident in the game process; the game backend is otherwise tiny.
- **Failure isolation**: none — a CUDA OOM or codec crash takes down the game API mid-interrogation.
- **Concurrency**: uvicorn workers each load their own copy, or synthesis blocks the event loop unless carefully threaded.
- **Model lifetime**: tied to the game process; can't restart TTS without restarting the game.
- **Only advantage**: no second process, no CORS/proxy question.

### Option B — separate local TTS service ✅ recommended

Independent FastAPI process (PoC in `experiments/local_tts/`), same shape as the game backend, speaking a small JSON+WAV API (§7), optionally an OpenAI-compatible `/v1/audio/speech` alias for tooling reuse.

- **Isolation**: model crashes/OOM never touch the game; game degrades to text (fallback is one failed `fetch` → banner + silent).
- **LAN**: bind `0.0.0.0` and the RTX box serves the MacBook — identical to the existing Ollama pattern the game already supports for dialogue.
- **Engine switching**: `voices.json` maps `voice_id → engine`; engines are lazy-loaded adapters; Kokoro→Qwen migration is config, not code.
- **Health/queueing/cancellation**: `GET /health` (model state, device, queue depth); single worker queue per engine (serialise GPU work); client-side cancellation via `AbortController` + server-side job cancel.
- **Startup/shutdown**: `start.sh`/`stop.sh` gain an optional third pid; the game runs fine when the service is absent.
- **Cost**: one more process to manage; ~50-line client in the frontend. Worth it.

### Option C — pre-generate stable dialogue at case creation

Runtime TTS only for dynamic interrogation replies; fixed narration/intros/authored dialogue rendered when a case is generated.

- **Latency**: zero for authored lines — but the deterministic cache in §8 already converges to this after first play, without a build step.
- **Disk**: a full case's authored lines ≈ tens of MB of WAV (or a few MB of Opus); per-case audio complicates the currently-clean locked case bundles.
- **Repeatability**: good (fits the "case truth is locked" philosophy) — voice config would be frozen into the bundle.
- **Export/portability**: case bundles are currently small JSON; bundling audio makes `gen_*` cases heavy and forces a "regenerate audio" migration whenever a voice changes.
- **Verdict**: don't build the batch step now. Adopt its *spirit* via the deterministic cache, and optionally add a "warm the cache for this case" endpoint later (one POST that synthesises all authored lines through the same runtime path).

**Recommendation: B, with C's benefit obtained for free through caching.** A is rejected on failure-isolation and restart ergonomics alone.

---

## 6. Voice system design

### 6.1 VoiceConfig (proposed)

```jsonc
{
  "voice_id": "clara_wells",            // stable key, referenced by agents
  "engine": "kokoro",                   // "kokoro" | "qwen3_tts" | "piper" | "espeak"
  "model": "kokoro-82m",                // engine-specific model tag
  "preset_voice": "bf_isabella",        // engine voice/speaker name
  "reference_audio": null,              // Base-clone only; path under tts_service/refs/
  "reference_transcript": null,
  "default_instruction": "Precise and clipped, guarded, never volunteers more than asked.",
  "speed": 1.0,
  "enabled": true
}
```

`default_instruction` is seeded from the agent's existing `voice_card` — the game already authors exactly this text. Engines that can't use it (Kokoro/Piper) ignore it; the Qwen engine appends the per-utterance emotion (from the pressure band) to it.

### 6.2 Where it lives — a three-layer combination

1. **Global voice registry** (`tts_service/voices.json`, service-owned): the full `VoiceConfig` objects, including engine details. The service is the only thing that knows engines exist. Includes `narrator` (default voice) and a small cast pool.
2. **Agent metadata** (`Agent.voice_id: str | None` in `models.py` + per-case `agents.json`, phase 2): each character references a registry voice by id only. Player-safe, so it can pass through `projections.py`. Generated cases get a best-effort voice-assignment phase in `mystery_architect.py` that *picks from the pool* (deterministic by agent seed, so regeneration doesn't reshuffle voices) — the LLM never invents engine parameters. **Assignments are frozen into the case bundle at generation, exactly like sprites and portraits, so a character's voice can't silently regenerate mid-case.**
3. **User settings** (frontend `localStorage` + optional service-side overrides): auto-speak toggle (global mute for speech, independent of the existing Howler master mute), per-character enable, narrator on/off, voice-preview picks. Cosmetic only, mirroring `settings.ts`'s cinematics pattern.

This satisfies: consistent voices per case (frozen `voice_id` in the bundle), default narrator voice (registry), per-character enablement + global mute (settings), replay (SpeechManager keeps the last utterance), cancellation on navigation (SpeechManager cancels on route/agent change), fallback when the service is down (speak() failures are silent + one status banner), previews in settings (POST `/preview`), and no accidental identity regeneration (bundle freeze + registry ids never reused for different presets).

**Consent guardrail:** no cloning in v1. When the Base-clone path arrives, `reference_audio` may only point at project-owned synthetic references (e.g. VoiceDesign output) or user-provided audio behind an explicit consent confirmation stored next to the reference. No bundled third-party samples.

---

## 7. Proposed local API

Implemented (except DELETE, which is stubbed as cancellation-by-disconnect) in the PoC.

```
GET  /health          → { status, engines: {kokoro: {loaded, device, model}}, queue_depth, uptime_s }
GET  /voices          → [ VoiceConfig… ] (safe fields only)
POST /synthesize      → audio/wav bytes (blocking; honours client disconnect)
POST /preview         → same as /synthesize but never cached and capped length
DELETE /jobs/{id}     → cancel a queued job (deferred; see below)
```

```jsonc
// POST /synthesize
{
  "text": "I never entered the pub that evening.",
  "voice_id": "clara_wells",
  "instruction": "Nervous, defensive, speaking quietly",   // optional
  "format": "wav",                                          // v1: wav only
  "sample_rate": 24000                                      // optional resample hint
}
```

**Transport choice:** plain **HTTP request → complete WAV response**. Rationale:
- The game's replies arrive as complete text (no LLM streaming), so there is nothing to stream *into* the synthesiser.
- Kokoro synthesises a two-sentence reply in a fraction of a second on the dev machine — chunked transfer would save tens of milliseconds.
- Browser cancellation is free: `AbortController` aborts the fetch; the service sees the disconnect and skips/aborts the job. This covers "player navigates away" without job ids.
- WebSocket/SSE/job-polling add state machines with no user-visible benefit until sentence-pipelining (phase 3), at which point *multiple small HTTP requests* (one per sentence, played sequentially) is still simpler than a socket and is the planned mechanism.

An OpenAI-compatible `POST /v1/audio/speech` alias is cheap to add later if other tools want the service; it is not needed by the game.

---

## 8. Caching design

Deterministic key: `sha256(engine | model_tag+version | voice_id | canonical(voice_params) | instruction | normalised_text | speed | sample_rate)` → `cache/<first2>/<hash>.wav` + sidecar `.json` (metadata: created, duration, hit count). Implemented in the PoC.

- Same line + same voice + same instruction ⇒ served from disk (measured ~1 ms service-side in the sandbox).
- **Layout**: two-level fan-out under `tts_service/cache/`; per-case subdirs are *not* used because the key already isolates content — but a `case_id` tag in the sidecar enables per-case deletion (`DELETE /cache?case_id=…`, phase 2).
- **Size/eviction**: default cap 500 MB, LRU by sidecar last-hit, checked lazily after writes. (A whole case's dialogue at 24 kHz/16-bit ≈ 3 MB/min of speech; 500 MB is weeks of play.)
- **Saved cases**: keep audio *out* of case bundles (repeatability comes from the deterministic key + frozen voice ids; bundles stay small and portable).
- **Privacy**: cached WAVs are spoken forms of player-visible dialogue only — no truth fields ever reach the service. Retention is still user data on disk; expose "clear speech cache" in settings, and never include the cache in exports. Free-text *player questions* are never synthesised, so player-authored text is not retained.

---

## 9. Streaming, latency, and sentence handling

Four modes considered:

1. **True speech streaming** (model emits audio frames continuously): not available in any candidate's official local package today (Qwen3-TTS architecture supports it; the released `qwen-tts` package and vLLM-Omni expose offline generation only). **Do not claim or build on this yet.**
2. **Chunked generation** (server chunks a finished WAV): pointless for our sizes.
3. **Sentence-by-sentence synthesis**: valuable once replies get long (monologues, narration). Requires the sentence splitter below. Phase 3.
4. **Complete WAV before playback**: matches the game's non-streaming dialogue flow exactly. **Chosen for v1.**

The task's suggested pipeline (stream LLM text → buffer to sentence boundary → TTS queue → sequential playback → cancel on interrupt) is the right *eventual* shape, but its first prerequisite is missing: the dialogue LLM is not streamed anywhere in this codebase, and adding streaming would touch the sanitiser (which validates the *complete* rewrite before display — a token stream cannot be sanitised until it ends). Sentence-level TTS therefore only becomes useful as: complete (sanitised) reply → split into sentences → synthesise sentence 1 while 2..n queue → sequential playback. That halves time-to-first-audio for long replies with no changes to the LLM layer, and is the planned phase 3.

**Will it sound natural?** Per-sentence synthesis loses cross-sentence prosody (each sentence gets fresh intonation). For Kokoro the effect is mild; for Qwen instruct-driven delivery it can reset emotional build-up. Mitigation: split only above a length threshold (e.g. >220 chars), and keep paragraph-sized chunks rather than strict sentences.

**Sentence boundary rules** (implemented in the PoC's `sentences.py`): split on `.!?…` followed by whitespace+capital/quote, with a protected-token list for UK-relevant abbreviations (`Mr. Mrs. Ms. Dr. Rev. Insp. Det. Sgt. PC St. no. approx. e.g. i.e. etc.`), decimals and amounts (`£3.50`, `7.45am`), initials (`J. Whitcombe`), and ellipses; closing quotes/brackets attach to the finished sentence (`"…he said."`). Hesitation markers (`—`, `…`) are kept inside the sentence so the voice carries the pause.

---

## 10. Frontend experience (recommended behaviour)

- **Auto-speak toggle** in `AudioControls` (default off on first run; persisted). Global speech mute independent of master mute.
- **Stop-speaking button** appears while audio plays (also Esc). Switching suspect/page always cancels (SpeechManager owns one active utterance + queue; `AbortController` for in-flight fetches).
- **Replay last response** button next to the transcript's latest entry (cache makes this instant).
- **Speaking indicator**: pulse ring on the suspect `Portrait` (reuse the demeanour frame); narrator lines get a subtle "🕮" indicator instead.
- **Ambient ducking**: copy the stinger duck (ambient → 20 %) for the duration of speech, restore on end/cancel.
- **No overlap**: SpeechManager is a strict queue of one; a new `speak()` cancels the current one (interrogation) or queues (narration reading multiple paragraphs).
- **Model loading state**: `/health` polled once when speech is first enabled; "Voice warming up…" toast until `loaded: true`; the first synthesis may take seconds on cold start.
- **Graceful fallback**: any failure → text-only, one non-blocking banner ("Voice unavailable — check the TTS service"), never a blocking error. TTS disabled ⇒ zero network calls.
- **Settings**: voice picker + `/preview` playback per character (phase 2), service URL field mirroring the LLM settings modal.
- All of this is additive; no existing behaviour changes when speech is off.

---

## 11. Proof of concept and benchmarks

**Location:** `experiments/local_tts/` — see its `README.md` for exact install/run commands per machine.
**What it does:** FastAPI service (`:8020`) with `GET /health`, `GET /voices`, `POST /synthesize`, `POST /preview`; engine adapters for **kokoro**, **piper**, **qwen3_tts** (CustomVoice + instruct, auto device cuda/mps/cpu) and a zero-download **espeak** fallback; deterministic WAV cache; British-English test corpus (`british_test_lines.py`); `benchmark.py` records model-load time, first/subsequent latency, RTF, and process RSS (+ VRAM via `nvidia-smi` when present).

### Sandbox results (this container: 4 vCPU, no GPU, HF blocked ⇒ espeak fallback engine)

Numbers measure the **service pipeline with the espeak-ng fallback**, not the recommended model — treat them as the overhead floor; rerun `benchmark.py` on the real machines:

| Metric | Value |
|---|---|
| Service cold start → healthy `/health` | 0.37 s |
| Engine "model load" (espeak) | < 0.01 s |
| First synthesis (uncached, 9-word line) | 13–16 ms |
| Subsequent synthesis (uncached, 60–200-char lines, median) | 19–20 ms (RTF 0.002–0.007) |
| Cached repeat of same line | ~2 ms |
| Full 16-line British corpus (2,039 chars) | 0.28 s total |
| Server process RSS after 40+ syntheses | 46 MB |

Expected orders of magnitude on the real targets (cited, to be verified with the same script): Kokoro ≈ 0.3–1 s per reply on the MacBook CPU (RTF ≪ 1), RSS ~1.5–2 GB with torch; Qwen3 0.6B on the RTX 2070 ≈ real-time generation (a 6-s reply ≈ 5–7 s uncached, ~4–6 GB VRAM), which is why caching + (later) sentence-splitting matter for the Qwen path, while Kokoro needs neither.

### British English test corpus

`british_test_lines.py` covers: place names (Chipping Norton, Bicester, Aldeburgh, Marylebone), UK surnames (Featherstonehaugh, Cholmondeley, Marjoribanks), dates/times ("quarter past seven on Tuesday the 3rd of March"), police terminology (DCI, SOCO, PACE caution phrasing), pounds ("£3.50", "two hundred and forty pounds"), punctuation-heavy detective dialogue, abbreviations (Mr./Dr./St./Insp.), contractions ("mustn't've"), hesitant speech ("I… I don't— I wasn't there"), a one-word reply and a long monologue. Listening assessment of accent plausibility must happen on the dev machine with real voices (espeak's en-GB is intelligible but robotic); the corpus + `synthesize_corpus.py` make that a five-minute job.

---

## 12. Risks and licensing notes

| Risk | Assessment / mitigation |
|---|---|
| Qwen3-TTS accent gap | The main open question. Mitigate: Kokoro first; evaluate Qwen VoiceDesign British voices on the RTX box before committing to Qwen for suspects. |
| Qwen on Apple Silicon unofficial | MLX port is community-maintained; pin versions, keep Kokoro as the Mac default. |
| Piper maintenance + GPL-3.0 | OHF is seeking maintainers; GPL is fine for a separate local service but Kokoro (Apache-2.0) makes Piper optional. Demote Piper to "only if Kokoro fails somewhere". |
| Licences | Qwen3-TTS: Apache-2.0 (models + code). Kokoro: Apache-2.0 (code + weights). Piper: GPL-3.0 (engine), voices carry per-voice dataset licences — check each voice's card before shipping. espeak-ng: GPL-3.0 (fallback/dev only). |
| Voice cloning ethics | Deferred entirely. When added: synthetic or consented references only, consent recorded alongside the reference file, no third-party samples in the repo. |
| Truth leaks | TTS receives display text only; the service never sees case truth. Add a no-leak test asserting the speech path uses `answer_text` and never `deterministic_answer_text`/solution fields. |
| Model weights in git | `.gitignore` in the PoC covers `cache/`, `out/`, `models/`, `*.wav`, `*.onnx`, `*.pt*`. CI-check later if the service is promoted. |
| GPU contention on the RTX box | The 2070 cannot comfortably co-host a 7B dialogue LLM and Qwen-TTS; plan device placement explicitly (TTS-only GPU, or 0.6B + small LLM). |
| Dialogue audio privacy | Cache holds spoken player-visible dialogue; add "clear speech cache", exclude from exports, never synthesise player-typed text. |

---

## 13. Phased implementation plan

**Phase 0 (this branch)** — investigation + PoC. ✔

**Phase 1 — dependable speech for interrogation replies (Kokoro, complete-response)**
1. Promote `experiments/local_tts/` → `tts_service/` (keep the espeak fallback for CI).
2. Install Kokoro on the dev machine; cast narrator + 8 villagers from the British voice set in `voices.json`; run `benchmark.py` + corpus listening pass.
3. Frontend `speech.ts` (queue/cancel/replay) + Howler duck; hook `Suspects.tsx` last-reply; toggle in `AudioControls`; graceful-fallback banner.
4. `vite.config.ts` proxy; optional `start.sh` integration. *(No backend/game-schema changes at all in this phase.)*

**Phase 2 — per-character voices as case data + settings**
5. `Agent.voice_id` in `models.py` + projections + hand-authored `agents.json` assignments; freeze-at-generation for `gen_*` cases (deterministic pick, best-effort phase in `mystery_architect.py`).
6. TTS settings UI (service URL, previews via `/preview`), per-character enable, cache clearing, per-case cache purge.

**Phase 3 — emotion + scale**
7. Qwen3-TTS engine on the RTX 2070 over LAN: 0.6B CustomVoice + `instruct` derived from `voice_card` + pressure band (calm/defensive/cracking). A/B against Kokoro; evaluate 1.7B VoiceDesign British voice creation (synthetic references, project-owned).
8. Sentence-level pipelining for long replies + narrator monologues (`sentences.py` already written).
9. Narrator/autopsy/epilogue speech (`Intro.tsx`, autopsy panel, `AccusationCeremony.tsx`).

**Deferred indefinitely until justified:** true audio streaming, WebSockets, voice cloning, bundling audio in case exports, LLM token streaming.

---

## 14. Conclusion

- **Engine first:** Kokoro-82M (British voices, Apache-2.0, runs everywhere) behind an engine-agnostic service; Qwen3-TTS-12Hz-0.6B-CustomVoice is the committed second engine for emotional interrogation delivery, with the 1.7B VoiceDesign→Base pipeline as the route to *British* Qwen voices.
- **Machine:** the game's own machine for Kokoro; the RTX 2070 desktop as an optional LAN TTS server when the Qwen engine lands. Qwen-Audio-3.0-TTS is hosted-only and excluded.
- **Separate service:** yes (Option B), with caching giving Option C's latency for repeated/authored lines for free.
- **Granularity:** complete-response synthesis first — it matches the game's non-streaming dialogue flow; sentence-level generation is phase 3.
- **Smallest safe sequence:** service → frontend SpeechManager on the last interrogation reply → per-character voices frozen into case bundles → Qwen emotion engine → sentence pipelining.
