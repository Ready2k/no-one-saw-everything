"""Synchronise editor location bounds with current_village_v2 artwork."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "backend/app/data/town/town_layout.json"

BOUNDS = {
    "loc_village_square": (88, 52, 22, 13, "exterior", "Current village square plaza"),
    "loc_fountain": (97, 54, 5, 5, "exterior", "Fountain in the village square"),
    "loc_marcus_house": (101, 36, 21, 14, "exterior", "North-centre house compound"),
    "loc_marcus_study": (108, 39, 8, 6, "interior", "Study nested inside Marcus's house"),
    "loc_hobbs_cafe": (99, 67, 17, 20, "exterior", "Large square-front building"),
    "loc_cafe_kitchen": (100, 72, 8, 7, "interior", "Kitchen nested inside Hobbs Cafe"),
    "loc_cafe_storage": (109, 72, 6, 7, "interior", "Storage nested inside Hobbs Cafe"),
    "loc_clinic": (111, 52, 15, 14, "exterior", "Public building east of the square"),
    "loc_clinic_dispensary": (118, 56, 6, 6, "interior", "Dispensary nested inside the clinic"),
    "loc_bookshop": (72, 54, 16, 16, "exterior", "West shop compound"),
    "loc_bookshop_back": (73, 62, 7, 7, "interior", "Back room nested inside the bookshop"),
    "loc_rear_alley": (86, 50, 40, 2, "exterior", "Service route behind the north buildings"),
    "loc_pub": (89, 37, 12, 10, "exterior", "Mallet & Crown beside St. Alder's Church"),
    "loc_owen_house": (118, 68, 21, 18, "exterior", "Eastern house and work yard"),
    "loc_elias_house": (99, 92, 17, 13, "exterior", "South-centre cottage"),
    "loc_clara_flat": (100, 68, 8, 3, "interior", "Flat nested above Hobbs Cafe"),
    "loc_ben_flat": (64, 72, 8, 12, "interior", "Western cottage group, west unit"),
    "loc_priya_flat": (73, 72, 8, 12, "interior", "Western cottage group, east unit"),
    "loc_nadia_flat": (128, 54, 12, 12, "interior", "East-square residence"),
    "loc_ruth_cottage": (126, 35, 18, 17, "exterior", "North-east house plot"),
    "loc_solicitors_office": (88, 65, 9, 10, "exterior", "Whittle & Cross on the south-west square plot"),
    "loc_elias_bench": (104, 62, 4, 2, "exterior", "Bench on the south-east edge of the square"),
    "loc_fishery": (145, 42, 39, 29, "exterior", "Eastern fishery and docks"),
    "loc_lake": (7, 44, 47, 42, "exterior", "Western lake and accessible shoreline"),
    "loc_woodland": (120, 101, 51, 38, "exterior", "South-eastern woodland"),
    "loc_meadow": (70, 106, 42, 28, "exterior", "Southern meadow"),
    "loc_back_lane": (110, 87, 31, 4, "exterior", "Lane behind Owen's yard"),
    "loc_st_alder_church": (67, 36, 18, 15, "exterior", "St. Alder's Church and churchyard"),
    "loc_willow_farmhouse": (46, 108, 22, 19, "exterior", "Willow Farmhouse and yard"),
}


def main() -> None:
    data = json.loads(LAYOUT.read_text())
    locations = data.setdefault("canonical_locations", {})
    for location_id, (x, y, w, h, mode, notes) in BOUNDS.items():
        locations[location_id] = {
            "bounds": {"x": x, "y": y, "w": w, "h": h},
            "mode": mode,
            "notes": notes,
        }
        if mode == "interior":
            locations[location_id]["bounds_internal"] = {"x": x, "y": y, "w": w, "h": h}

    # Map markers are visual-only. Re-centre the old-map evidence anchors
    # within their new parent location so validation and replay cannot retain
    # stale coordinates from the retired artwork.
    for override in data.get("case_overrides", {}).values():
        counters = {}
        for anchor_data in override.get("object_anchors", {}).values():
            location_id = anchor_data.get("location_id")
            spec = BOUNDS.get(location_id)
            if not spec:
                continue
            x, y, w, h, *_ = spec
            index = counters.get(location_id, 0)
            counters[location_id] = index + 1
            columns = 3
            col = index % columns
            row = index // columns
            anchor_data["anchor"] = {
                "x": round(x + w * (0.3 + 0.2 * col), 2),
                "y": round(y + h * (0.35 + 0.2 * min(row, 2)), 2),
            }

    data["version"] = "town_layout_editor_v2"
    LAYOUT.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Updated {len(BOUNDS)} boundaries in {LAYOUT}")


if __name__ == "__main__":
    main()
