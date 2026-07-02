import re
from typing import Optional
from app.models import CaseData
from app.session import Session

def normalize_text(text: str) -> str:
    """Normalize text by lowercasing and removing non-alphanumeric chars (except spaces)."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text.strip()

def resolve_references(question: str, case: CaseData, session: Session) -> dict[str, Optional[str]]:
    """
    Resolve words in the player's question to known/discovered entities.
    Must not expose hidden truth.
    Returns a dict with:
        referenced_agent_id
        referenced_location_id
        referenced_object_id
        referenced_clue_id
    """
    q_norm = normalize_text(question)
    
    agent_id = None
    # Prioritize longest names (e.g. "clara vane" before "clara")
    agents = sorted(case.agents, key=lambda a: len(a.full_name), reverse=True)
    for a in agents:
        name_norm = normalize_text(a.full_name)
        first_name = normalize_text(a.full_name.split()[0])
        # Visible agents only. Assuming all agents in case.agents are visible/public known for now.
        if name_norm in q_norm or (first_name and first_name in q_norm.split()):
            agent_id = a.agent_id
            break

    location_id = None
    locations = sorted(case.locations, key=lambda loc: len(loc.name), reverse=True)
    for loc in locations:
        if normalize_text(loc.name) in q_norm:
            location_id = loc.location_id
            break

    object_id = None
    objects = sorted(case.objects, key=lambda o: len(o.name), reverse=True)
    for obj in objects:
        # Check if the object is known. An object is known if it has been discovered.
        # Discovered objects could be those touched by discovered clues.
        is_known = False
        for clue_id in session.discovered_clue_ids:
            clue = next((c for c in case.clues if c.clue_id == clue_id), None)
            if clue and obj.object_id in clue.linked_object_ids:
                is_known = True
                break
        
        if is_known and normalize_text(obj.name) in q_norm:
            object_id = obj.object_id
            break

    clue_id = None
    clues = sorted(case.clues, key=lambda c: len(c.title), reverse=True)
    for clue in clues:
        if clue.clue_id in session.discovered_clue_ids:
            if normalize_text(clue.title) in q_norm:
                clue_id = clue.clue_id
                break

    return {
        "referenced_agent_id": agent_id,
        "referenced_location_id": location_id,
        "referenced_object_id": object_id,
        "referenced_clue_id": clue_id,
    }
