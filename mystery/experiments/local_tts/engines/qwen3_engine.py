"""Qwen3-TTS CustomVoice engine (Apache-2.0) — the emotional-delivery engine.

Install:  pip install -r requirements-qwen.txt   (torch + qwen-tts)
First use downloads the model from Hugging Face (0.6B ≈ 2.5 GB).

Presets are Qwen CustomVoice speakers ("Ryan", "Aiden", ...). `instruction`
is passed straight through to the model's `instruct` parameter — this is the
only engine in the PoC with real emotion control ("Nervous, defensive,
speaking quietly").

Device selection: CUDA if available, else MPS (unofficial — the upstream
package documents CUDA only; MPS may hit CPU fallbacks), else CPU (slow:
expect several times real time for the 0.6B model). Override with
QWEN_TTS_DEVICE=cuda|mps|cpu, model with QWEN_TTS_MODEL.
"""

from __future__ import annotations

import io
import os
import wave

from . import LoadTimer

DEFAULT_MODEL = os.environ.get("QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")


class Qwen3TTSEngine(LoadTimer):
    name = "qwen3_tts"

    def __init__(self) -> None:
        super().__init__()
        self._model = None
        self._device = "cpu"

    def load(self) -> None:
        if self._model is not None:
            return

        def _load() -> None:
            import torch
            from qwen_tts import Qwen3TTSModel

            device = os.environ.get("QWEN_TTS_DEVICE")
            if not device:
                if torch.cuda.is_available():
                    device = "cuda:0"
                elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                    device = "mps"
                else:
                    device = "cpu"
            self._device = device
            kwargs = {"device_map": device}
            if device.startswith("cuda"):
                kwargs["dtype"] = torch.bfloat16
                try:
                    import flash_attn  # noqa: F401

                    kwargs["attn_implementation"] = "flash_attention_2"
                except ImportError:
                    pass
            self._model = Qwen3TTSModel.from_pretrained(DEFAULT_MODEL, **kwargs)

        self.timed_load(_load)

    def synthesize(
        self, text: str, preset: str, instruction: str | None, speed: float
    ) -> tuple[bytes, int]:
        self.load()
        import numpy as np

        wavs, sample_rate = self._model.generate_custom_voice(
            text=text,
            language="English",
            speaker=preset,
            instruct=instruction or "",
        )
        samples = np.asarray(wavs[0], dtype="float32")
        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(int(sample_rate))
            w.writeframes(pcm.tobytes())
        return buf.getvalue(), int(sample_rate)

    def info(self) -> dict:
        return {
            "loaded": self._model is not None,
            "device": self._device,
            "model": DEFAULT_MODEL,
            "load_seconds": self.load_seconds,
            "supports_instruction": True,
        }
