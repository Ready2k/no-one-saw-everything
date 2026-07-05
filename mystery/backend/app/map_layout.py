"""Canonical visual layout for the map replay layer.

Positions are pixel coordinates on the 719x513 rendered overview of the
original Smallville map (``the_ville2.png``), derived from the sector
tile data in ``environment/frontend_server/static_dirs/assets/the_ville``.

This module is visual-only fallback data: authored ``map_position`` /
``map_bounds`` fields on a location always win. It exists so that
procedurally generated cases (which reuse the same location ids as the
hand-authored templates) render on the map without authored coordinates.
It must never influence case logic.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from .models import Agent, Location, MapBounds, MapPosition

MAP_ASSET = "the_ville"
MAP_IMAGE = "/map/the_ville.png"
MAP_WIDTH = 719
MAP_HEIGHT = 513

# location_id -> (center, bounds, layer). Centers/bounds sit on real ville
# sectors: Hobbs Cafe is the actual cafe; the bookshop borrows the Rose and
# Crown; the clinic borrows the Willows Market and Pharmacy; houses borrow
# the ville's residential row.
_LOCATION_LAYOUT: dict[str, tuple[MapPosition, MapBounds, str]] = {
    "loc_village_square": (
        MapPosition(x=370, y=180),
        MapBounds(x=300, y=140, width=150, height=80),
        "exterior",
    ),
    "loc_fountain": (
        # Matches the fountain + bench sprites stamped into the_ville.png
        # (see the mystery map render script / village-square overlay).
        MapPosition(x=370, y=184),
        MapBounds(x=357, y=168, width=26, height=28),
        "exterior",
    ),
    "loc_hobbs_cafe": (
        MapPosition(x=390, y=115),
        MapBounds(x=365, y=87, width=67, height=46),
        "exterior",
    ),
    "loc_cafe_kitchen": (
        MapPosition(x=377, y=98),
        MapBounds(x=366, y=88, width=24, height=20),
        "interior",
    ),
    "loc_cafe_storage": (
        MapPosition(x=418, y=94),
        MapBounds(x=406, y=88, width=24, height=18),
        "interior",
    ),
    "loc_rear_alley": (
        MapPosition(x=390, y=80),
        MapBounds(x=330, y=74, width=130, height=12),
        "exterior",
    ),
    "loc_bookshop": (
        MapPosition(x=295, y=114),
        MapBounds(x=267, y=92, width=56, height=41),
        "exterior",
    ),
    "loc_clinic": (
        MapPosition(x=432, y=244),
        MapBounds(x=380, y=215, width=103, height=56),
        "exterior",
    ),
    "loc_marcus_house": (
        MapPosition(x=383, y=372),
        MapBounds(x=349, y=328, width=67, height=92),
        "exterior",
    ),
    "loc_owen_house": (
        MapPosition(x=475, y=372),
        MapBounds(x=442, y=328, width=67, height=92),
        "exterior",
    ),
    "loc_clara_flat": (
        MapPosition(x=295, y=78),
        MapBounds(x=267, y=67, width=56, height=31),
        "exterior",
    ),
}

# Fallback ring for unknown location ids (generated cases with novel
# locations). Deterministic per id so replays are stable.
_FALLBACK_SLOTS: list[MapPosition] = [
    MapPosition(x=141, y=236),  # Johnson Park
    MapPosition(x=326, y=244),  # Harvey Oak Supply Store
    MapPosition(x=598, y=134),  # Oak Hill College
    MapPosition(x=146, y=129),  # artist's co-living space
    MapPosition(x=290, y=372),  # Taylor/Ortiz house
    MapPosition(x=113, y=329),  # Adam Smith's house
    MapPosition(x=617, y=257),  # Oak Hill dorm
    MapPosition(x=488, y=95),   # Carlos Gomez's apartment
]

# Character sprite sheets shipped with the original project and copied to
# the mystery frontend's /map/sprites directory. 96x128 PNG, 3x4 grid of
# 32x32 frames.
SPRITE_POOL: list[str] = [
    "Abigail_Chen.png",
    "Adam_Smith.png",
    "Arthur_Burton.png",
    "Ayesha_Khan.png",
    "Carlos_Gomez.png",
    "Carmen_Ortiz.png",
    "Eddy_Lin.png",
    "Francisco_Lopez.png",
    "Giorgio_Rossi.png",
    "Hailey_Johnson.png",
    "Isabella_Rodriguez.png",
    "Jane_Moreno.png",
    "John_Lin.png",
    "Klaus_Mueller.png",
    "Latoya_Williams.png",
    "Marcus_Chen.png",
    "Maria_Lopez.png",
    "Mei_Lin.png",
    "Priya_Kapoor.png",
    "Rajiv_Patel.png",
    "Ryan_Park.png",
    "Sam_Moore.png",
]


def _stable_index(key: str, size: int) -> int:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % size


def location_visuals(loc: Location) -> tuple[Optional[MapPosition], Optional[MapBounds], Optional[str]]:
    """Authored visual fields win; otherwise fall back to the canonical
    layout, then to a deterministic fallback slot."""
    if loc.map_position is not None:
        return loc.map_position, loc.map_bounds, loc.visual_layer
    layout = _LOCATION_LAYOUT.get(loc.location_id)
    if layout:
        return layout
    slot = _FALLBACK_SLOTS[_stable_index(loc.location_id, len(_FALLBACK_SLOTS))]
    return slot, None, loc.visual_layer or "exterior"


def agent_sprite(agent: Agent) -> tuple[str, str]:
    """Return (sprite_id, sprite_asset) for an agent, assigning a stable
    sprite from the pool when none is authored."""
    if agent.sprite_asset:
        sprite_id = agent.sprite_id or "sprite_" + agent.sprite_asset.rsplit(".", 1)[0].lower()
        return sprite_id, agent.sprite_asset
    asset = SPRITE_POOL[_stable_index(agent.agent_id, len(SPRITE_POOL))]
    return "sprite_" + asset.rsplit(".", 1)[0].lower(), asset
