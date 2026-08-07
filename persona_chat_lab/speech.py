"""Local, private response-audio tracks for the talking-face renderer."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / ".face-runtime" / "response_audio"


def _spoken_text(text: str) -> str:
    """Remove visual stage direction before creating renderer audio."""
    return re.sub(r"\*\[[^\]]+\]\*\s*", "", text).strip()


def render_owen_speech(text: str) -> str | None:
    """Create a cached local WAV track and return its opaque ID.

    The browser does not play this automatically. It is the phoneme-timed
    input for the audio-driven lip-sync worker.
    """
    spoken = _spoken_text(text)
    if not spoken:
        return None
    audio_id = hashlib.sha256(spoken.encode("utf-8")).hexdigest()[:16]
    wav_path = OUTPUT_DIR / f"{audio_id}.wav"
    if wav_path.is_file():
        return audio_id

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    aiff_path = OUTPUT_DIR / f"{audio_id}.aiff"
    try:
        subprocess.run(["say", "-v", "Daniel", "-r", "155", "-o", str(aiff_path), spoken], check=True, capture_output=True, timeout=30)
        subprocess.run(["ffmpeg", "-y", "-i", str(aiff_path), "-ar", "24000", "-ac", "1", str(wav_path)], check=True, capture_output=True, timeout=30)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    finally:
        aiff_path.unlink(missing_ok=True)
    return audio_id if wav_path.is_file() else None


def speech_path(audio_id: str) -> Path | None:
    if not re.fullmatch(r"[0-9a-f]{16}", audio_id):
        return None
    path = OUTPUT_DIR / f"{audio_id}.wav"
    return path if path.is_file() else None
