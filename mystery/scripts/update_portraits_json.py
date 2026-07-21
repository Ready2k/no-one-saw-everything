import json
import os

agents_file = 'backend/app/data/case_004/agents.json'

with open(agents_file, 'r') as f:
    agents = json.load(f)

for agent in agents:
    # Get the base name from the agent_id, e.g. agent_owen -> owen, agent_bg_cole -> cole
    agent_id = agent['agent_id']
    base_name = agent_id.replace('agent_bg_', '').replace('agent_', '')
    
    agent['portrait_art'] = {
        "calm": f"/art/case_004/portraits/{base_name}_calm.jpg",
        "defensive": None,
        "cracking": None
    }

with open(agents_file, 'w') as f:
    json.dump(agents, f, indent=2)

print("Updated agents.json successfully.")
