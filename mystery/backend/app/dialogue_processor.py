import random
from typing import Optional
from .models import Agent

def apply_repetition_frustration(text: str, count: int) -> str:
    if count == 2:
        prefixes = [
            "I already told you. ",
            "We just went over this. ",
            "As I said before, "
        ]
        return random.choice(prefixes) + text
    elif count >= 3:
        prefixes = [
            "Are you even listening to me? ",
            "I don't know why you keep asking me that. ",
            "For the last time: "
        ]
        return random.choice(prefixes) + text
    return text

def apply_personality_fillers(text: str, agent: Agent) -> str:
    # If conflict avoidance is high, they are nervous/hesitant
    if agent.conflict_avoidance > 0.7:
        if random.random() < 0.5:
            text = "Um... " + text
        # Optionally replace some periods with ellipses for trailing off
        if random.random() < 0.3:
            text = text.replace(". ", "... ")
    
    # If honesty baseline is low, they might stall for time to think of a lie
    if agent.honesty_baseline < 0.5:
        if random.random() < 0.4:
            text = "Well... " + text
            
    return text

def apply_body_language(text: str, agent: Agent) -> str:
    # Add stage directions occasionally
    if random.random() > 0.4:
        return text
        
    actions = []
    if agent.honesty_baseline < 0.5:
        actions.extend(["*[Avoids your gaze]*", "*[Shifts uncomfortably]*", "*[Looks away]*"])
    
    if agent.conflict_avoidance < 0.3:
        actions.extend(["*[Crosses arms]*", "*[Glares]*", "*[Sighs impatiently]*"])
    elif agent.conflict_avoidance > 0.7:
        actions.extend(["*[Fidgets]*", "*[Looks down]*", "*[Wrings hands]*"])
        
    if not actions:
        # Default calm actions
        actions = ["*[Nods]*", "*[Pauses]*", "*[Takes a breath]*"]
        
    action = random.choice(actions)
    return f"{action} {text}"

def apply_deflection(agent: Agent) -> str:
    # Called when trust is too low, or it's a fallback intent that they refuse to answer
    if agent.conflict_avoidance < 0.3:
        return random.choice([
            "That's none of your business.",
            "I don't see how that's relevant to anything.",
            "Ask a sensible question, Detective."
        ])
    elif agent.conflict_avoidance > 0.7:
        return random.choice([
            "I... I don't really know anything about that.",
            "Maybe you should ask someone else.",
            "I'm sorry, I can't help you with that."
        ])
    else:
        return random.choice([
            "I'd prefer not to discuss that.",
            "I have nothing to say on the matter.",
            "Let's stay focused on the facts, please."
        ])

def humanize_response(text: str, agent: Agent, count: int) -> str:
    """Passes deterministic text through humanizing filters."""
    text = apply_repetition_frustration(text, count)
    text = apply_personality_fillers(text, agent)
    text = apply_body_language(text, agent)
    return text
