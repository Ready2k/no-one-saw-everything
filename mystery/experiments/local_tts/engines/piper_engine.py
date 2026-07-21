"""Piper engine (GPL-3.0, OHF-Voice/piper1-gpl) — lightweight fallback.

Install:  pip install -r requirements-piper.txt
Voices:   python -m piper.download_voices en_GB-alan-medium en_GB-cori-high
          (downloads .onnx + .onnx.json into PIPER_VOICE_DIR, default ./models/piper)

Presets are Piper voice names, e.g. "en_GB-alan-medium",
"en_GB-southern_english_female-low", "en_GB-cori-high".
`instruction` is ignored (no emotion control). `speed` maps to Piper's
inverse length_scale.
"""

from __future__ import annotations

import io
import os
import threading
import wave
from pathlib import Path

from . import LoadTimer

VOICE_DIR = Path(os.environ.get("PIPER_VOICE_DIR", Path(__file__).parent.parent / "models" / "piper"))


class PiperEngine(LoadTimer):
    name = "piper"

    def __init__(self) -> None:
        super().__init__()
        self._voices: dict[str, object] = {}
        self._lock = threading.Lock()
        self._available = False

    def load(self) -> None:
        if self._available:
            return

        def _check() -> None:
            import piper  # noqa: F401  (validates the install)

            self._available = True

        self.timed_load(_check)

    def _get_voice(self, preset: str):
        with self._lock:
            if preset not in self._voices:
                from piper import PiperVoice

                model_path = VOICE_DIR / f"{preset}.onnx"
                if not model_path.exists():
                    raise RuntimeError(
                        f"Piper voice {preset!r} not found at {model_path}. Download it with: "
                        f"python -m piper.download_voices {preset} --data-dir {VOICE_DIR}"
                    )
                self._voices[preset] = PiperVoice.load(str(model_path))
            return self._voices[preset]

    def synthesize(
        self, text: str, preset: str, instruction: str | None, speed: float
    ) -> tuple[bytes, int]:
        self.load()
        voice = self._get_voice(preset)

        from piper import SynthesisConfig

        config = SynthesisConfig(length_scale=1.0 / max(0.25, speed))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            voice.synthesize_wav(text, w, syn_config=config)
        sample_rate = voice.config.sample_rate
        return buf.getvalue(), sample_rate

    def info(self) -> dict:
        return {
            "loaded": self._available,
            "device": "cpu",
            "model": f"piper1-gpl (voices in {VOICE_DIR})",
            "loaded_voices": list(self._voices),
            "load_seconds": self.load_seconds,
            "supports_instruction": False,
        }
