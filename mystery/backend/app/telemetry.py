import os
from datetime import datetime, timezone
from typing import Any
from app.session import Session

MYSTERY_DEV_TELEMETRY_ENABLED = os.getenv("MYSTERY_DEV_TELEMETRY_ENABLED", "true").lower() == "true"

def log_telemetry_event(session: Session, event_type: str, data: dict[str, Any] = None) -> None:
    """Logs a telemetry event to the session log if enabled."""
    if not MYSTERY_DEV_TELEMETRY_ENABLED:
        return
        
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "data": data or {}
    }
    session.event_log.append(event)
