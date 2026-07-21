import json
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent / "backend" / "app" / "data"
CASE_001 = BASE_DIR / "case_001"
TEMPLATES = BASE_DIR / "templates"
TEMPLATES.mkdir(exist_ok=True)

# Mappings for case_001
REPLACEMENTS = {
    "agent_marcus": "{VICTIM_ID}",
    "Marcus Bell": "{VICTIM_NAME}",
    "Marcus": "{VICTIM_NAME}",
    
    "agent_clara": "{KILLER_ID}",
    "Clara Wells": "{KILLER_NAME}",
    "Clara": "{KILLER_NAME}",
    
    "agent_owen": "{RH1_ID}",
    "Owen Price": "{RH1_NAME}",
    "Owen": "{RH1_NAME}",
    
    "agent_isabella": "{RH2_ID}",
    "Isabella Reed": "{RH2_NAME}",
    "Isabella": "{RH2_NAME}",
    
    "agent_ben": "{WITNESS1_ID}",
    "Ben Carter": "{WITNESS1_NAME}",
    "Ben": "{WITNESS1_NAME}",
    
    "agent_nadia": "{WITNESS2_ID}",
    "Nadia": "{WITNESS2_NAME}",
    
    "agent_elias": "{WITNESS3_ID}",
    "Elias": "{WITNESS3_NAME}",
    
    "agent_priya": "{WITNESS4_ID}",
    "Priya Shah": "{WITNESS4_NAME}",
    "Priya": "{WITNESS4_NAME}",

    "obj_till_weight": "{WEAPON_ID}",
    "brass till weight": "{WEAPON_NAME}",
    "till weight": "{WEAPON_NAME}",
}

def parameterize(text: str) -> str:
    for k, v in REPLACEMENTS.items():
        text = text.replace(k, v)
    return text

def process_file(filename: str):
    content = (CASE_001 / filename).read_text()
    return parameterize(content)

# We will just merge all case files into one big JSON template for each case type
def create_template(case_type: str, motive_text: str):
    data = {
        "case": json.loads(process_file("case.json")),
        "agents": json.loads(process_file("agents.json")),
        "locations": json.loads(process_file("locations.json")),
        "objects": json.loads(process_file("objects.json")),
        "memories": json.loads(process_file("memories.json")),
        "events": json.loads(process_file("events.json")),
        "clues": json.loads(process_file("clues.json"))["clues"],
        "conclusions": json.loads(process_file("clues.json"))["conclusions"],
        "interviews": json.loads(process_file("interviews.json")),
        "challenges": json.loads(process_file("challenges.json")),
        "solution": json.loads(process_file("solution.json")),
    }
    
    # Change case type
    data["case"]["case_type"] = case_type
    data["case"]["case_id"] = f"template_{case_type}"
    
    # Tweak motive summary to make them slightly distinct for the scaffold
    data["case"]["motive_summary"] = motive_text
    
    out = json.dumps(data, indent=2)
    (TEMPLATES / f"{case_type}.json").write_text(out)
    print(f"Created {case_type}.json")

if __name__ == "__main__":
    create_template("blackmail", "{KILLER_NAME} was being blackmailed by {VICTIM_NAME} over a secret ledger.")
    create_template("debt", "{KILLER_NAME} owed {VICTIM_NAME} a massive debt and could not pay before the deadline.")
    create_template("betrayal", "{VICTIM_NAME} betrayed {KILLER_NAME} regarding a vital partnership agreement.")

