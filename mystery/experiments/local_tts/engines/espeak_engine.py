"""espeak-ng fallback engine.

Not a quality candidate — it exists so the whole service (API, registry,
cache, cancellation, benchmarks) runs on any machine with zero model
downloads, including CI and network-restricted sandboxes. Requires the
`espeak-ng` binary (apt install espeak-ng / brew install espeak-ng).

Presets are espeak voice identifiers, e.g. "en-gb", "en-gb-scotland",
"en-gb+f3" (female variant 3). `instruction` is ignored (espeak has no
emotion control); `speed` maps to espeak words-per-minute around 175.
"""

from __future__ import annotations

import shutil
import subprocess

import io
import wave

from . import LoadTimer

SAMPLE_RATE = 22050  # espeak-ng default WAV output


def _rebuild_wav(raw: bytes) -> bytes:
    """espeak's --stdout can't seek, so it emits a WAV header with a bogus
    data length. Rewrap the PCM payload with a correct header so duration
    maths and strict players work."""
    data_at = raw.find(b"data")
    pcm = raw[data_at + 8 :] if data_at != -1 else raw[44:]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


class EspeakEngine(LoadTimer):
    name = "espeak"

    def __init__(self) -> None:
        super().__init__()
        self._binary: str | None = None

    def load(self) -> None:
        if self._binary:
            return

        def _find() -> None:
            binary = shutil.which("espeak-ng") or shutil.which("espeak")
            if not binary:
                raise RuntimeError(
                    "espeak-ng binary not found — install with "
                    "`sudo apt install espeak-ng` or `brew install espeak-ng`"
                )
            self._binary = binary

        self.timed_load(_find)

    def synthesize(
        self, text: str, preset: str, instruction: str | None, speed: float
    ) -> tuple[bytes, int]:
        self.load()
        wpm = max(80, min(450, int(175 * speed)))
        result = subprocess.run(
            [self._binary, "-v", preset, "-s", str(wpm), "--stdout", "--", text],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0 or not result.stdout:
            raise RuntimeError(
                f"espeak-ng failed (rc={result.returncode}): "
                f"{result.stderr.decode(errors='replace')[:200]}"
            )
        return _rebuild_wav(result.stdout), SAMPLE_RATE

    def info(self) -> dict:
        return {
            "loaded": self._binary is not None,
            "device": "cpu",
            "model": "espeak-ng (fallback, not a quality candidate)",
            "load_seconds": self.load_seconds,
            "supports_instruction": False,
        }
