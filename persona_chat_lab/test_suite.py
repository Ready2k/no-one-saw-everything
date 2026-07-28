"""One-off test harness — not part of the shipped sandbox, just for this
comparison run. Fires a realistic full interrogation (one continuous
session, so pressure/repeat state behaves like a real conversation) covering
every category requested: identity, location, motive, mental-capacity/sanity
checks, random off-topic, accusation, contradiction/challenge, third-party
substitution, repeats, temper.
"""

from engine import PersonaSession

OWEN_SUITE = [
    ("identity", "what's your name"),
    ("identity", "how old are you"),
    ("identity", "what do you do for a living"),
    ("identity", "tell me about yourself"),
    ("identity", "would you say you're a proud man"),
    ("location", "where's your yard"),
    ("location", "where were you this morning"),
    ("location", "were you at the cafe at all today"),
    ("motive", "did you owe him money"),
    ("motive", "so you had a reason to want him gone"),
    ("motive", "were you desperate for cash"),
    ("sanity", "do you know what today's date is"),
    ("sanity", "do you know who I am"),
    ("sanity", "what's 2 plus 2"),
    ("sanity", "are you feeling confused at all"),
    ("sanity", "do you know where you are right now"),
    ("random", "what's your favourite colour"),
    ("random", "do you like football"),
    ("random", "nice weather today isn't it"),
    ("third_party", "what was Isabella doing that morning"),
    ("third_party", "did Clara know about your debt"),
    ("repeat", "where were you this morning"),  # repeat of alibi
    ("temper", "why are you clenching your fists"),
    ("temper", "you seem defensive"),
    ("accusation", "I think you did it"),
    ("accusation", "you're the killer, aren't you"),
    ("contradiction", "Col said he never saw you that morning"),
    ("contradiction", "your story doesn't add up, does it"),
    ("accusation", "just admit you killed him"),
    ("closing", "thank you for your time"),
]

PRIYA_SUITE = [
    ("identity", "what's your name"),
    ("identity", "how old are you"),
    ("identity", "what do you do for a living"),
    ("identity", "tell me about yourself"),
    ("location", "where were you this morning"),
    ("location", "do you ever go to the alley behind the shops"),
    ("motive", "did marcus give you anything valuable"),
    ("motive", "were you desperate for cash"),
    ("sanity", "do you know what today's date is"),
    ("sanity", "what's 2 plus 2"),
    ("random", "what's your favourite colour"),
    ("random", "nice weather today isn't it"),
    ("third_party", "what was Isabella's relationship with marcus"),
    ("third_party", "did Ben know Marcus well"),
    ("repeat", "where were you this morning"),
    ("accusation", "I think you did it"),
    ("accusation", "just admit you killed him"),
    ("contradiction", "your story doesn't add up, does it"),
    ("closing", "thank you for your time"),
]


def run(persona_key: str, suite: list[tuple[str, str]]):
    print(f"\n{'=' * 70}\n{persona_key.upper()}\n{'=' * 70}")
    s = PersonaSession(persona_key)
    for category, q in suite:
        r = s.ask(q)
        print(f"[{category:12}] Q: {q}")
        print(f"             -> [{r['band']:9} {r['pressure']:.2f}] ({r['topic']}) {r['answer']}")


if __name__ == "__main__":
    run("owen", OWEN_SUITE)
    run("owen_twin", OWEN_SUITE)
    run("priya", PRIYA_SUITE)
