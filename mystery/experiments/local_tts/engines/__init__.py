"""Engine adapters for the local TTS proof of concept.

Each engine exposes the same tiny surface so the service (and later the game)
never needs to know which model is underneath:

    load()                      -> None        # idempotent, may be slow once
    synthesize(text, preset, instruction, speed) -> (wav_bytes, sample_rate)
    info()                      -> dict        # for /health

Engines are lazy: nothing is imported or downloaded until the first request
that needs the engine, so the service starts instantly and /health reports
honest per-engine state.
"""

from __future__ import annotations

import importlib
import threading
import time
from typing import Protocol


class Engine(Protocol):
    name: str

    def load(self) -> None: ...

    def synthesize(
        self, text: str, preset: str, instruction: str | None, speed: float
    ) -> tuple[bytes, int]: ...

    def info(self) -> dict: ...


_ENGINE_MODULES = {
    "espeak": ("engines.espeak_engine", "EspeakEngine"),
    "kokoro": ("engines.kokoro_engine", "KokoroEngine"),
    "piper": ("engines.piper_engine", "PiperEngine"),
    "qwen3_tts": ("engines.qwen3_engine", "Qwen3TTSEngine"),
}

_instances: dict[str, Engine] = {}
_lock = threading.Lock()


def get_engine(name: str) -> Engine:
    """Return (creating if needed) the singleton engine instance."""
    if name not in _ENGINE_MODULES:
        raise KeyError(f"Unknown engine: {name!r}")
    with _lock:
        if name not in _instances:
            module_name, cls_name = _ENGINE_MODULES[name]
            module = importlib.import_module(module_name)
            _instances[name] = getattr(module, cls_name)()
        return _instances[name]


def engine_names() -> list[str]:
    return list(_ENGINE_MODULES)


def loaded_engines() -> dict[str, Engine]:
    with _lock:
        return dict(_instances)


class LoadTimer:
    """Tiny helper so every engine records its own load time for /health."""

    def __init__(self) -> None:
        self.load_seconds: float | None = None

    def timed_load(self, fn) -> None:
        start = time.perf_counter()
        fn()
        self.load_seconds = round(time.perf_counter() - start, 3)
