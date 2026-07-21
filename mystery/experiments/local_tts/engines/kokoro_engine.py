"""Kokoro-82M engine (Apache-2.0) — the recommended first real engine.

Install:  pip install -r requirements-kokoro.txt   (torch + kokoro)
          plus the system espeak-ng package (used by Kokoro's G2P fallback).
First use downloads ~330 MB of weights from Hugging Face.

Presets are Kokoro voice names. British English voices ('b' prefix):
  bf_alice, bf_emma, bf_isabella, bf_lily, bm_daniel, bm_fable,
  bm_george, bm_lewis

`instruction` is ignored — Kokoro has no emotion control (documented
limitation; the Qwen engine is the emotional-delivery path).
"""

from __future__ import annotations

import io
import wave

from . import LoadTimer

SAMPLE_RATE = 24000


class KokoroEngine(LoadTimer):
    name = "kokoro"

    def __init__(self) -> None:
        super().__init__()
        self._pipeline = None
        self._device = "cpu"

    def load(self) -> None:
        if self._pipeline is not None:
            return

        def _load() -> None:
            import torch
            from kokoro import KPipeline

            # lang_code 'b' selects British English G2P.
            if torch.cuda.is_available():
                self._device = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                self._device = "mps"
            self._pipeline = KPipeline(lang_code="b", device=self._device)

        self.timed_load(_load)

    def synthesize(
        self, text: str, preset: str, instruction: str | None, speed: float
    ) -> tuple[bytes, int]:
        self.load()
        import numpy as np

        chunks = []
        for _, _, audio in self._pipeline(text, voice=preset, speed=speed):
            chunks.append(audio.detach().cpu().numpy() if hasattr(audio, "detach") else audio)
        if not chunks:
            raise RuntimeError("Kokoro produced no audio")
        samples = np.concatenate(chunks)
        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(pcm.tobytes())
        return buf.getvalue(), SAMPLE_RATE

    def info(self) -> dict:
        return {
            "loaded": self._pipeline is not None,
            "device": self._device,
            "model": "hexgrad/Kokoro-82M",
            "load_seconds": self.load_seconds,
            "supports_instruction": False,
        }
