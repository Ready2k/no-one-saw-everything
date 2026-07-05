import json
import os

backstories = {
    "agent_priya": "I remember the day we met. I was just looking for a chance, and they took a leap of faith on me. I owe them so much for giving me a start when no one else would.",
    "agent_owen": "We first met over a job. The roof was leaking and I came to patch it. We shook hands on a fair price, and that was the start of a long working relationship. It's a shame how things turned out.",
    "agent_elias": "Oh, I've known them for decades. I remember them when they were younger, full of fire and vinegar. I've watched from my bench as they built their life here. You get to know a person well over thirty years.",
    "agent_nadia": "We met shortly after I moved to the village and started at the clinic. They brought over a tin of biscuits as a welcome gift. We've been neighbors and friends ever since, sharing quiet moments when the village got too loud.",
    "agent_ruth": "First time we met, it was pouring rain and I was soaked through on my round. They insisted I step inside for a cup of tea to warm up. You don't forget small kindnesses like that.",
    "agent_ben": "I met them on my very first delivery round. They showed me exactly where to leave the parcels so they wouldn't get wet. Always precise, but fair. We had a good rhythm going.",
    "agent_clara": "I answered a help-wanted card in the window years ago. I was nervous, but they took me on and taught me everything I know about running a business. I'll always be grateful for that.",
    "agent_dr_haig": "We met professionally, years ago. I was consulting on a complex case and they offered some surprisingly astute observations. We built a mutual respect from that day on.",
    "agent_fred": "We crossed paths at the pub one evening. Got talking about old cars, of all things. Realized we had a lot in common. Good memories, mostly.",
    "agent_col": "I was covering a mate's delivery route when we first bumped into each other. Got off on the wrong foot over a late package, but we sorted it out over a pint later. Been solid ever since.",
    "agent_isabella": "It was years ago, before I even owned the bookshop. They helped me carry some heavy boxes in from the rain. A small thing, but it showed character. We've been intertwined in village life ever since.",
    "agent_solicitor": "They came to my office for a standard consultation. Over the years, our professional relationship deepened. I respected their business acumen, even if their methods were sometimes... unorthodox."
}

def update_interviews(case_num):
    path = f"backend/app/data/case_00{case_num}/interviews.json"
    if not os.path.exists(path):
        return
        
    with open(path, 'r') as f:
        data = json.load(f)
        
    for agent_data in data:
        agent_id = agent_data.get("agent_id")
        rules = agent_data.get("rules", [])
        
        # Check if the min_ask_count rule already exists
        has_deep_backstory = any(r.get("question_type") == "relationship" and r.get("min_ask_count") == 1 for r in rules)
        if has_deep_backstory:
            continue
            
        # Find the regular relationship rule
        reg_rel_rule_idx = next((i for i, r in enumerate(rules) if r.get("question_type") == "relationship" and "min_ask_count" not in r), None)
        
        if reg_rel_rule_idx is not None:
            # Update the existing relationship rule
            reg_rule = rules[reg_rel_rule_idx]
            if "suggested_followups" not in reg_rule:
                reg_rule["suggested_followups"] = []
            if "How did you two first meet?" not in reg_rule["suggested_followups"]:
                reg_rule["suggested_followups"].append("How did you two first meet?")
                
            # Create deep backstory rule
            backstory_text = backstories.get(agent_id, "We met years ago. It's a long story, but we've known each other a long time.")
            deep_rule = {
                "question_type": "relationship",
                "min_ask_count": 1,
                "answer_text": backstory_text,
                "answer_type": "claim",
                "truthfulness": "true",
                "emotional_shift": "reflective",
                "claims": [],
                "reveals_clue_ids": [],
                "reveals_memory_ids": [],
                "suggested_followups": []
            }
            
            # Insert the new rule right before the existing relationship rule
            rules.insert(reg_rel_rule_idx, deep_rule)

    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        
    print(f"Updated {path}")

for i in range(2, 7):
    update_interviews(i)
