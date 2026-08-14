"""Visual-only location fallbacks for the map replay layer.

Authored ``map_position`` / ``map_bounds`` fields on a location always win.
This module fills the gap for cases that carry no authored coordinates —
chiefly procedurally generated ones, which reuse the canonical ``loc_*`` ids
and therefore resolve against the canonical town contract in ``town_map``.
It must never influence case logic.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from .models import Location, MapBounds, MapPosition


def _stable_index(key: str, size: int) -> int:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % size


def location_visuals(loc: Location) -> tuple[Optional[MapPosition], Optional[MapBounds], Optional[str]]:
    """Authored visual fields win; otherwise resolve against the canonical
    town, then against a deterministic canonical slot so an unknown location
    still lands somewhere stable on the map rather than nowhere."""
    if loc.map_position is not None:
        return loc.map_position, loc.map_bounds, loc.visual_layer

    from .town_map import CANONICAL_LOCATIONS, canonical_location_visuals

    position, bounds, layer = canonical_location_visuals(loc.location_id)
    if position is not None:
        return (
            MapPosition(**position),
            MapBounds(**bounds) if bounds else None,
            layer or loc.visual_layer or "exterior",
        )

    # Unknown id: borrow a canonical location's footprint, chosen stably by id
    # so replays of the same case never shift between requests.
    slots = sorted(CANONICAL_LOCATIONS)
    if not slots:
        return None, None, loc.visual_layer or "exterior"
    fallback = CANONICAL_LOCATIONS[slots[_stable_index(loc.location_id, len(slots))]]
    return (
        MapPosition(**fallback["position"]),
        MapBounds(**fallback["bounds"]) if fallback.get("bounds") else None,
        loc.visual_layer or "exterior",
    )
