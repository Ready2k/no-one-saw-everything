import json
from pydantic import ValidationError
from app.models import CaseData
from app.session import Session
from app.models import QuestionIntent
from app.llm.client import get_llm_client
from app.reference_resolver import resolve_references

def classify_question_intent_llm(question: str, case: CaseData, session: Session, fallback_allowed: bool = True) -> QuestionIntent:
    client = get_llm_client()
    
    # We must only expose discovered/public things to the LLM
    refs = resolve_references(question, case, session)
    
    # Provide the LLM with context about what these IDs mean so it can map accurately
    # e.g., if referenced_agent_id is present, tell LLM their name.
    available_context = []
    
    if refs["referenced_agent_id"]:
        agent = next((a for a in case.agents if a.agent_id == refs["referenced_agent_id"]), None)
        if agent:
            available_context.append(f"Agent: {agent.full_name} ({agent.agent_id})")
            
    if refs["referenced_location_id"]:
        loc = next((l for l in case.locations if l.location_id == refs["referenced_location_id"]), None)
        if loc:
            available_context.append(f"Location: {loc.name} ({loc.location_id})")
            
    if refs["referenced_object_id"]:
        obj = next((o for o in case.objects if o.object_id == refs["referenced_object_id"]), None)
        if obj:
            available_context.append(f"Object: {obj.name} ({obj.object_id})")
            
    if refs["referenced_clue_id"]:
        clue = next((c for c in case.clues if c.clue_id == refs["referenced_clue_id"]), None)
        if clue:
            available_context.append(f"Clue: {clue.title} ({clue.clue_id})")
    
    context_str = "\n".join(available_context) if available_context else "None"
    
    schema_json = QuestionIntent.schema_json()
    
    prompt = f"""
You are a classification system for a detective game. The player has asked a suspect a question.
Your job is to map this free-text question into a structured QuestionIntent.

Question: "{question}"

Resolved references in the question (Use ONLY these IDs if applicable, do not invent IDs):
{context_str}

Intent rules:
- alibi: Asking where they were during the murder.
- timeline: Asking what they were doing at a specific time.
- last_seen_victim: Asking when they last saw the victim.
- relationship: Asking about their relationship with the victim or someone else.
- evidence: Asking about a specific clue.
- location: Asking about a specific location.
- motive: Asking why they might want the victim dead.
- object: Asking about a physical item or evidence.
- contradiction: Asking a vague question about a lie or contradictory statement ("Why did someone say X?").
- explicit_challenge: Explicitly demanding to confront or challenge the suspect with evidence ("Challenge Clara with Ben's sighting").
- fallback_unknown: If the question is nonsense, out of character, or asks about hidden things not resolved above.

Respond with valid JSON matching this schema:
{schema_json}
"""
    try:
        raw_json = client.generate_json(prompt, fallback_allowed=fallback_allowed)
        data = json.loads(raw_json)
        # Ensure we only use the safely resolved IDs
        data["referenced_agent_id"] = refs["referenced_agent_id"]
        data["referenced_location_id"] = refs["referenced_location_id"]
        data["referenced_object_id"] = refs["referenced_object_id"]
        data["referenced_clue_id"] = refs["referenced_clue_id"]
        
        return QuestionIntent(**data)
    except Exception as e:
        return QuestionIntent(
            intent="fallback_unknown",
            confidence=1.0,
            rewritten_structured_question="Unknown question",
            **refs
        )
