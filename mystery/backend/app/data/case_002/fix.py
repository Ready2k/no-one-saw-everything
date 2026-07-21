import json
import os
import re

dir_path = 'backend/app/data/case_002'

def load_json(name):
    with open(os.path.join(dir_path, name), 'r') as f:
        return json.load(f)

def save_json(name, data):
    with open(os.path.join(dir_path, name), 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

def replace_strings(obj):
    if isinstance(obj, dict):
        return {k: replace_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_strings(v) for v in obj]
    elif isinstance(obj, str):
        s = obj
        # Event IDs
        s = re.sub(r'ev_06(\d\d)', r'ev_10\1', s)
        s = re.sub(r'ev_07(\d\d)', r'ev_11\1', s)
        s = re.sub(r'ev_08(\d\d)', r'ev_12\1', s)
        s = re.sub(r'ev_09(\d\d)', r'ev_13\1', s)
        
        # Times HH:MM
        time_replacements = {
            '06:30': '10:30', '06:40': '10:40', '06:50': '10:50',
            '07:00': '11:00', '07:10': '11:10', '07:30': '11:30',
            '08:00': '12:00', '08:05': '12:05', '08:10': '12:10',
            '08:25': '12:25', '08:32': '12:32', '08:35': '12:35',
            '08:40': '12:40', '08:43': '12:43', '08:45': '12:45',
            '08:48': '12:48', '08:50': '12:50',
            '09:00': '13:00', '09:15': '13:15', '09:30': '13:30'
        }
        for k, v in time_replacements.items():
            s = s.replace(k, v)
            
        # Dialog times
        s = s.replace("six-forty", "ten-forty")
        s = s.replace("seven-ten", "eleven-ten")
        s = s.replace("from seven", "from eleven")
        s = s.replace("at seven", "at eleven")
        s = s.replace("half eight", "half twelve")
        s = s.replace("twenty-five past eight", "twenty-five past twelve")
        s = s.replace("nine-ten", "one-ten")
        s = s.replace("just after nine", "just after one")
        
        # Morning -> lunchtime
        s = s.replace("morning papers", "lunchtime papers")
        s = s.replace("morning busk", "lunchtime busk")
        s = s.replace("all morning", "all lunchtime") # Might be weird but let's check
        s = s.replace("this morning", "this afternoon")
        s = s.replace("That whole stretch I was in the stockroom.", "That whole stretch I was in the stockroom.") # noop

        # Specific clue fixes
        s = s.replace("Five minutes are unaccounted for — and those five minutes are inside the murder window.", "Five minutes are unaccounted for — exactly when she claims to have been shelving books, proving she was elsewhere and breaking her alibi.")
        
        # Routine
        s = s.replace("Midday post round starts at 11:30, takes her past the bookshop around 12:45.", "Midday post round starts at 10:30, takes her past the bookshop around 11:10.")

        return s
    return obj

# Process all json files
files = ['agents.json', 'case.json', 'challenges.json', 'clues.json', 'events.json', 'interviews.json', 'locations.json', 'memories.json', 'objects.json', 'solution.json']

for file in files:
    data = load_json(file)
    data = replace_strings(data)
    save_json(file, data)

print("Done.")
