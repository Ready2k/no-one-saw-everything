#!/usr/bin/env python3
"""Print searchable Places artwork coverage by case and lighting phase."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "backend/app/data/town/place_art_registry.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lighting", help="Only show a lighting phase containing this text")
    args = parser.parse_args()
    data = json.loads(REGISTRY.read_text())
    needle = (args.lighting or "").lower()
    for case_id, profile in data["case_profiles"].items():
        if needle and needle not in profile["lighting_phase"].lower():
            continue
        bindings = data["case_bindings"][case_id]
        print(
            f"{case_id}: {profile['lighting_phase']} {profile['clock_range']} "
            f"({profile['coverage']}, {len(bindings)} explicit scenes)"
        )
        for location_id, path in sorted(bindings.items()):
            print(f"  {location_id}: {path}")


if __name__ == "__main__":
    main()
