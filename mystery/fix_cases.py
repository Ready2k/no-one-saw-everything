import json
import glob
import os

body_terms = ["body", "pocket", "hand", "clothes", "coat", "jacket", "wound", "note"]

for clues_path in glob.glob("backend/app/data/*/clues.json"):
    case_dir = os.path.dirname(clues_path)
    case_json_path = os.path.join(case_dir, "case.json")
    if not os.path.exists(case_json_path):
        continue
        
    with open(case_json_path) as f:
        case_data = json.load(f)
    victim_id = case_data.get("victim_id")
    discovery_loc = case_data.get("discovery_location_id")
    
    if not victim_id or not discovery_loc:
        continue
    
    with open(clues_path) as f:
        clues_obj = json.load(f)
        
    modified = False
    for clue in clues_obj.get("clues", []):
        d = clue.get("discoverability", {})
        if d.get("method") != "inspect":
            continue
            
        reveal_on = d.get("reveal_on", [])
        if "examine_body" in reveal_on:
            continue
            
        text = (clue.get("title", "") + " " + clue.get("description", "")).lower()
        is_body = (
            d.get("location_id") == discovery_loc and
            (victim_id in clue.get("linked_agent_ids", []) or any(t in text for t in body_terms))
        )
        if is_body:
            print(f"Updating {clues_path} -> clue {clue['clue_id']} ({clue['title']})")
            if "reveal_on" not in d:
                d["reveal_on"] = []
            if isinstance(d["reveal_on"], list):
                d["reveal_on"].append("examine_body")
                modified = True
            
    if modified:
        with open(clues_path, "w") as f:
            json.dump(clues_obj, f, indent=4)
