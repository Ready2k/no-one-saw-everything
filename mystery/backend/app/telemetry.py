import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.session import Session

logger = logging.getLogger(__name__)

MYSTERY_DEV_TELEMETRY_ENABLED = os.getenv("MYSTERY_DEV_TELEMETRY_ENABLED", "true").lower() == "true"

# The in-session event_log (session.py) is reset-scoped by design — it is
# "this investigation attempt's" history, and analytics that want a fresh
# read after a restart rely on that. It used to be the ONLY copy: a reset or
# a crash before the next autosave lost the telemetry outright. This is a
# second, append-only sink per (player, case) that neither reset_session nor
# a restart ever truncates — the durable audit trail an operator actually
# wants when reviewing playtests across retries.
TELEMETRY_DIR = Path(__file__).parent / "data" / "telemetry"


def _persist_enabled() -> bool:
    if os.environ.get("MYSTERY_SESSION_PERSIST") == "0":
        return False
    return "PYTEST_CURRENT_TEST" not in os.environ


def _safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value).lstrip(".") or "_"


def _durable_log_path(player_id: str, case_id: str) -> Path:
    return TELEMETRY_DIR / _safe_component(player_id) / f"{_safe_component(case_id)}.jsonl"


def _append_durable(player_id: str, case_id: str, event: dict) -> None:
    if not _persist_enabled():
        return
    try:
        path = _durable_log_path(player_id, case_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        # Same rule as session autosave: losing a telemetry line is bad,
        # taking the player's game down over it is worse.
        logger.exception("Failed to append durable telemetry for %s/%s", player_id, case_id)


def read_durable_log(player_id: str, case_id: str) -> list[dict]:
    """The full history for this (player, case), across every reset and
    restart — parsed defensively so one bad line can't break the export."""
    path = _durable_log_path(player_id, case_id)
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def log_telemetry_event(session: Session, event_type: str, data: dict[str, Any] = None) -> None:
    """Logs a telemetry event to the session's in-memory log (reset-scoped)
    and to the durable per-(player, case) log (survives resets and restarts)."""
    if not MYSTERY_DEV_TELEMETRY_ENABLED:
        return

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "data": data or {},
    }
    session.event_log.append(event)
    _append_durable(getattr(session, "player_id", "local"), session.case_id, event)
