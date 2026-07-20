"""Structured logging.

The default `logging` setup (whatever uvicorn's root handler happens to be)
has no request correlation and no machine-parseable format — every "Session
autosave failed" or "Rewrite rejected" line is just prose, impossible to
aggregate or alert on in a real deployment. This module is opt-in
(MYSTERY_LOG_JSON=true) so local development keeps its familiar plain-text
console output by default.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys

# Set by the request-id middleware (main.py) for the duration of one request,
# so every log line emitted while handling it — from any module, at any
# depth — can be correlated back to that request without threading an id
# through every function signature.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Call once at process startup (main.py module load)."""
    level_name = os.getenv("MYSTERY_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    use_json = os.getenv("MYSTERY_LOG_JSON", "false").lower() == "true"

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    if use_json:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
        )

    root = logging.getLogger()
    root.setLevel(level)
    # Idempotent: reconfiguring (tests import this module repeatedly) must not
    # pile up duplicate handlers and multiply every log line.
    root.handlers.clear()
    root.addHandler(handler)
