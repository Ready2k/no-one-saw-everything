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

def default_small_talk_line(agent: Agent, intent: str) -> str:
    """A per-agent default for small talk when the case has not authored one
    (`Agent.small_talk` is empty for most cast members in most cases), built
    only from fields every agent already has — occupation, first trait, and
    the numeric temperament dials — never a fixed vocabulary of specific
    trait words, since traits are freeform text authored per case. Replaces
    one universal "I don't have much to say about that." shared by every
    character in every case regardless of who they are."""
    occupation = agent.occupation.strip()
    article = "an" if occupation[:1].lower() in "aeiou" else "a"
    trait = agent.traits[0] if agent.traits else None

    if intent == "occupation":
        return f"I'm {article} {occupation}."
    if intent == "favorite_thing":
        base = f"Can't say I've got much time for hobbies, between the {occupation.lower()} and everything else."
        if trait:
            return f"{base} Ask around and people would call me {trait} before anything else."
        return base
    if intent == "about_me":
        first_name = agent.full_name.split()[0]
        base = f"I'm {first_name}, {article} {occupation.lower()} here."
        if trait:
            return f"{base} {trait.capitalize()}, if you ask anyone who knows me."
        return base
    if intent == "general_relationships":
        if agent.conflict_avoidance > 0.65:
            return "I keep out of most people's business, truth be told."
        if agent.gossip_tendency > 0.65:
            return "You hear things, working where I do. I don't chase it, but it finds you."
        return "I get on well enough with most people around here."
    if intent == "emotions":
        if agent.conflict_avoidance > 0.65:
            return "I'd rather keep things calm than make a show of how I feel."
        return "I don't make a show of it, but today's been hard on everyone."
    return "I don't have much to say about that."


def humanize_response(text: str, agent: Agent, count: int) -> str:
    """Passes deterministic text through humanizing filters."""
    text = apply_repetition_frustration(text, count)
    text = apply_personality_fillers(text, agent)
    text = apply_body_language(text, agent)
    return text
