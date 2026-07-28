"""Grounding packs for the persona chat lab.

Facts are lifted from mystery/backend/app/data/case_001 (Owen Price and
Priya Shah's authored interview packs, agent sheets, and relationships) so
this is a fair test of *delivery*, not a test of whether we can invent a
better-written case. The underlying content is identical to what the shipped
engine has available; only the rendering engine (engine.py) differs.

Case context (case_001, "The Storage Room Murder"): Marcus Bell, cafe owner,
found dead in the storage room at 08:12. Murder window 07:45-08:00. Neither
Owen nor Priya is the killer (that's Clara, kept out of this sandbox — not
needed to judge conversational realism).

Each fact carries two variant pools, addressing two different kinds of
repetition:

- `opening`: one or more *equally complete* phrasings of the first answer to
  this topic, same underlying facts (same times, same claims — a replay must
  never show different case truth), different wording. Selected by the
  session's playthrough seed, not by repeat count, so a fresh session can
  open on a different line than last time.
- `repeat`: a genuinely shorter, terser restatement used once the player has
  already asked this topic in the *current* session — not the identical
  paragraph replayed with a prefix bolted on.

Most facts only have one `opening` variant — writing a second, equally
complete, differently-worded line for every minor fact (opinions, work
quality, last-seen-victim) is real content-writing cost that wasn't invested
everywhere; the emotionally load-bearing facts (alibi, relationship,
accusation, debt/secrets) got the second pass first. Those still repeat
verbatim across playthroughs — a known, current gap, not a bug.
"""

VICTIM_NAME = "Marcus Bell"
MURDER_WINDOW = ("07:45", "08:00")
DISCOVERY_TIME = "08:12"

FACT = dict  # readability alias


OWEN = {
    "agent_id": "agent_owen",
    "full_name": "Owen Price",
    "pronoun": "he",
    "age": 47,
    "occupation": "Builder",
    "traits": ["blunt", "hot-tempered", "proud"],
    "voice_card": "Blunt, short sentences, no hedging; gets louder rather than more careful when pressed.",
    "conflict_avoidance": 0.2,
    "honesty_baseline": 0.55,
    "baseline_habit": "he leaves a workman's pause before each answer, measuring twice before he commits",
    "baseline_deviation": "The pauses have doubled. He is testing every question for load before he puts any weight on it.",
    "small_talk": {
        "greeting": ["What now?", "Still here. What is it now?"],
        "name": ["Owen Price. Everyone round here knows that already.", "Owen Price."],
        "how_are_you": ["I'm busy, that's how I am. Got a yard to run.", "Still busy. Yard doesn't run itself."],
        "occupation": ["I'm a builder. I run the timber yard and do most of the heavy lifting in this town.", "Builder. Timber yard."],
        "favorite_thing": ["A job done right and getting paid on time.", "A job done right."],
        "about_me": ["I work with my hands. I don't have time for gossip or games.", "I work. That's the whole of it."],
        "feelings": ["An honest day's pay makes me happy. People messing me about makes me furious.", "Good work pleases me. Wasted time doesn't."],
        "age": ["Forty-seven. Not that it's got anything to do with anything."],
        "self_assessment": ["Blunt, and proud of it. Ask anyone round here, they'd say the same."],
        "closing": ["About time.", "Right then."],
    },
    "facts": [
        FACT(
            topic="accusation",
            accusation=True,
            sensitive=True,
            keywords=[
                "you killed him", "did you kill him", "you murdered him", "think you killed",
                "you did it", "killed marcus", "murdered marcus", "kill marcus", "murder marcus",
                "you're the killer", "youre the killer", "you're guilty", "youre guilty",
                "why did you kill", "why did you do it", "why did you murder",
            ],
            opening=[
                "I didn't touch him. I was in my yard the whole window — ask Col Hartley if you don't believe me. Careful what you say next, Detective.",
                "Watch your mouth. I never laid a hand on him — I was in my yard the whole window, and Col Hartley can tell you the same. Think hard before you say that again.",
            ],
            repeat=["I was in my yard. That's not changing no matter how many times you ask."],
            truthfulness="true",
            emotion="fighting_hard",
        ),
        FACT(
            topic="alibi",
            keywords=["where were you", "where you were", "alibi", "murder window", "that morning", "07:45", "7:45", "8am", "quarter to eight"],
            exclude_keywords=["isabella", "clara", "col"],
            time_reference=435,  # 07:15
            location_name="his yard",
            opening=[
                "From a quarter past seven I was in my yard. The timber didn't finish going in until five past eight. And no, I'll not stand here and beg you to check up on me.",
                "Quarter past seven to five past eight, I was in my yard getting the timber stacked. I'm not going to plead with you to take my word for it.",
            ],
            repeat=["My yard. Quarter past seven to five past eight."],
            truthfulness="true",
            emotion="bristling",
        ),
        FACT(
            topic="alibi_corroboration",
            keywords=[
                "witness", "prove it", "anyone see you", "vouch",
                "corroborate", "corroborated", "corroboration", "corroborating",
                "alone", "by yourself", "delivery driver", "col hartley", "col",
            ],
            exclude_keywords=["isabella", "clara"],
            opening=[
                "You've been to see Col, then. Aye. He was there. Quarter past seven till five past eight, stacking the order with me. Both our names are on the docket and it's timed. I didn't lead with it because I've been a builder in this village thirty years and I'll not have it said Owen Price needed a delivery driver to vouch for him.",
                "Right, you've spoken to Col. He was with me the whole stretch — quarter past seven to five past eight, both our names on the timed docket. I kept that back because thirty years building in this village should count for something without needing a driver to swear for me.",
            ],
            repeat=["Col Hartley. Quarter past seven to five past eight. Go ask him yourself."],
            truthfulness="true",
            emotion="defensive",
            gate_topic="alibi",
            gate_min_ask=1,  # only lands once he's been pressed on the alibi already
        ),
        FACT(
            # A bare "col" keyword on alibi_corroboration used to fire on
            # ANY question mentioning him, including "how do you know Col,
            # is he family?" — a question about who Col *is*, not a repeat
            # of "did he corroborate you". These full phrases are longer
            # than alibi_corroboration's bare "col"/"col hartley", so
            # length-weighted scoring correctly prefers this fact instead.
            topic="col_relationship",
            keywords=[
                "how do you know col", "how you know col", "is he family",
                "is col family", "family member", "who is col", "relationship with col",
            ],
            opening=["Col's my regular delivery driver — timber, mostly. Known him years through the yard. No family, no fancy connection, just business. Good man to have vouching for you, as it happens."],
            repeat=["Delivery driver. Nothing more to it than that."],
            truthfulness="true",
            emotion="neutral",
        ),
        FACT(
            topic="last_seen_victim",
            keywords=["last see", "last time you saw", "see marcus", "see him"],
            exclude_keywords=["isabella", "clara", "col"],
            time_reference=425,  # 07:05
            location_name="outside the cafe",
            opening=["Five past seven, outside his cafe, both of us shouting. Half the square heard, so you'll hear about it anyway. Then I went back to my yard and got on with my work."],
            repeat=["Five past seven. Outside the cafe. Shouting."],
            truthfulness="true",
            emotion="grim",
        ),
        FACT(
            topic="relationship",
            keywords=[
                "relationship with marcus", "knew marcus", "know him", "his cafe", "how did you know",
                "were you friends", "friends with", "victim", "deceased", "get along", "good terms",
                "close to him", "close with him", "marcus", "relationship",
            ],
            exclude_keywords=["isabella", "clara", "col"],
            opening=[
                "He hired me to fix the cafe roof the winter it came down. Paid fair, shook my hand. That's how it started.",
                "Started with the roof job — the winter it caved in. He paid me fair and shook on it, and that was that.",
            ],
            repeat=["Roof job, years back. Nothing more to it."],
            truthfulness="true",
            emotion="regretful",
        ),
        FACT(
            topic="work_quality",
            keywords=["good job", "happy with your work", "satisfied", "complain", "quality of your work", "pleased with", "did a good job", "pay you", "paid you"],
            exclude_keywords=["isabella", "clara", "col"],
            opening=["Never had a complaint. He wasn't precious with compliments, but he never once mentioned the roof again after I finished it. That was Marcus's way of saying it was done right."],
            repeat=["Good enough he never brought it up again."],
            truthfulness="true",
            emotion="proud",
        ),
        FACT(
            topic="temper",
            keywords=[
                "aggressive", "aggresive", "fighter", "fists", "violent", "temper", "defensive",
                "hot-tempered", "hot tempered", "calm down", "why don't you sit",
                "why dont you sit", "sit down", "stand down", "pacing",
            ],
            exclude_keywords=["isabella", "clara", "col"],
            opening=[
                "I've got a temper, always have — ask anyone in this village, they'll say the same. Doesn't mean I put my hands on people. I stand because sitting doesn't suit how I think. That's all it is.",
                "Ask around, everyone knows I've a temper on me. Never once turned it into my fists though. Standing just helps me think — nothing more sinister than that.",
            ],
            repeat=["I shout. I don't swing. There's a difference."],
            truthfulness="true",
            emotion="defensive",
        ),
        FACT(
            topic="business_status",
            keywords=[
                "are you busy", "how's business", "hows business", "how's work", "hows work",
                "work is quiet", "work quiet", "business is quiet", "business quiet",
                "business is slow", "business slow", "work is slow", "work slow",
                "quiet today", "slow today", "busy today",
            ],
            exclude_keywords=["isabella", "clara", "col"],
            opening=[
                "Busy enough. Building work doesn't dry up round here — good thing, given what's owed against it.",
                "Work's steady. Has to be — I can't afford for it not to be, not with what I owe.",
            ],
            repeat=["Same as I said. Busy enough."],
            truthfulness="true",
            emotion="guarded",
        ),
        FACT(
            topic="relationship_debt",
            sensitive=True,
            keywords=["owe him", "debt", "money", "loan", "the argument", "were you shouting", "you were shouting", "heard you arguing", "committee"],
            exclude_keywords=["isabella", "clara", "col"],
            opening=[
                "I owed him. A lot. And no, I couldn't pay, and yes, he was going to make it public today. If that makes me a suspect, fine. But I settle things with my mouth, not whatever happened in that room.",
                "Fine — I was in debt to him, deep in it, and no I hadn't the money, and yes he meant to announce it today. Call me a suspect if you like. I fight with words, not with whatever happened in that storeroom.",
            ],
            repeat=["I owed him money. Doesn't make me a killer."],
            truthfulness="true",
            emotion="defensive",
        ),
        FACT(
            topic="loan_amount",
            sensitive=True,
            keywords=["how much", "amount", "eight thousand", "sum"],
            exclude_keywords=["isabella", "clara", "col"],
            opening=["Eight thousand. There, I've said the number. He'd have ruined me by lunchtime and called it principle."],
            repeat=["Eight thousand."],
            truthfulness="true",
            emotion="weary",
        ),
        FACT(
            topic="reaction_to_murder",
            sensitive=True,
            keywords=["how did you feel", "when you heard", "reaction", "found out he was dead", "murder happened"],
            exclude_keywords=["isabella", "clara", "col"],
            opening=["Sick. Then angry at myself for being glad the argument was over, which isn't the same as being glad he's dead. Don't twist that."],
            repeat=["Sick to my stomach. That's all there is to it."],
            truthfulness="true",
            emotion="raw",
        ),
        FACT(
            topic="opinion_clara",
            keywords=["clara", "cafe girl", "counter"],
            opening=["Clara runs that counter better than Marcus ever gave her credit for. Never had a problem with her."],
            repeat=["Nothing bad to say about Clara."],
            truthfulness="true",
            emotion="neutral",
        ),
        FACT(
            topic="opinion_isabella",
            keywords=["isabella"],
            opening=["Sharp woman. Found the body, poor cow. That's not a job I'd wish on anyone."],
            repeat=["Isabella's alright. Had a rough morning of it."],
            truthfulness="true",
            emotion="neutral",
        ),
    ],
    "deflect_mild": [
        "Couldn't tell you.",
        "Wouldn't know.",
        "Not something I keep track of.",
    ],
    "deflect_confrontational": [
        "Watch it.",
        "Say that again and see what happens.",
        "I've told you what I know.",
    ],
    "deflect_unmatched": [
        "That's got nothing to do with anything.",
        "Ask me something that matters.",
        "I don't see the point of that question.",
    ],
    # Layer 6 tension detector (ENGINE_SPEC.md §8): rendered when the player
    # references two already-revealed claims' times together. {gap} is the
    # computed minute delta — this is arithmetic on facts already told to
    # the player, not new content, so it never leaks ahead of what was
    # earned.
    "tension_response": [
        "Ten minutes is ten minutes. I walked it, same as any morning. Nothing convenient about it, whatever you're getting at.",
        "{gap} minutes, and I've got a yard five minutes from that cafe. Walk it yourself if you don't believe me.",
    ],
}


def _owen_fact(topic: str) -> dict:
    """Look up an OWEN fact by topic name, not list position — a positional
    index (`OWEN["facts"][3]`) silently breaks every reference after it the
    moment a fact is inserted earlier in the list, which is exactly what
    happened when col_relationship was added. Topic lookup is immune to
    reordering."""
    return next(f for f in OWEN["facts"] if f["topic"] == topic)


# Same character, same voice, same answer content, same dials — the ONLY
# difference from OWEN is that every `keywords` list is replaced with
# `concept_groups` (see concepts.py). Keeping everything else byte-identical
# is what makes this a fair, isolated A/B test of the matching layer, not a
# comparison muddied by two personas that also happen to answer differently.
OWEN_TWIN = {
    "agent_id": "agent_owen_twin",
    "full_name": "Owen Price (Concept Engine)",
    "pronoun": "he",
    "age": 47,
    "occupation": "Builder",
    "traits": ["blunt", "hot-tempered", "proud"],
    "voice_card": "Blunt, short sentences, no hedging; gets louder rather than more careful when pressed.",
    "conflict_avoidance": 0.2,
    "honesty_baseline": 0.55,
    "baseline_habit": "he leaves a workman's pause before each answer, measuring twice before he commits",
    "baseline_deviation": "The pauses have doubled. He is testing every question for load before he puts any weight on it.",
    "matcher": "concepts",
    "small_talk": OWEN["small_talk"],
    "facts": [
        FACT(
            topic="accusation",
            accusation=True,
            sensitive=True,
            concept_groups=[frozenset({"ACCUSATION"})],
            opening=_owen_fact("accusation")["opening"],
            repeat=_owen_fact("accusation")["repeat"],
            truthfulness="true",
            emotion="fighting_hard",
        ),
        FACT(
            topic="alibi",
            concept_groups=[frozenset({"WHERE", "TIME_WINDOW"}), frozenset({"TIME_WINDOW"}), frozenset({"ALIBI_PHRASE"})],
            exclude_concepts=frozenset({"COL", "ISABELLA", "CLARA"}),
            time_reference=435,
            location_name="his yard",
            opening=_owen_fact("alibi")["opening"],
            repeat=_owen_fact("alibi")["repeat"],
            truthfulness="true",
            emotion="bristling",
        ),
        FACT(
            topic="alibi_corroboration",
            concept_groups=[frozenset({"WITNESS"})],
            exclude_concepts=frozenset({"ISABELLA", "CLARA"}),
            opening=_owen_fact("alibi_corroboration")["opening"],
            repeat=_owen_fact("alibi_corroboration")["repeat"],
            truthfulness="true",
            emotion="defensive",
            gate_topic="alibi",
            gate_min_ask=1,
        ),
        FACT(
            topic="col_relationship",
            concept_groups=[frozenset({"COL_RELATIONSHIP"})],
            opening=_owen_fact("col_relationship")["opening"],
            repeat=_owen_fact("col_relationship")["repeat"],
            truthfulness="true",
            emotion="neutral",
        ),
        FACT(
            topic="last_seen_victim",
            concept_groups=[frozenset({"LAST_SEEN", "VICTIM_NAME"}), frozenset({"LAST_SEEN"})],
            exclude_concepts=frozenset({"COL", "ISABELLA", "CLARA"}),
            time_reference=425,
            location_name="outside the cafe",
            opening=_owen_fact("last_seen_victim")["opening"],
            repeat=_owen_fact("last_seen_victim")["repeat"],
            truthfulness="true",
            emotion="grim",
        ),
        FACT(
            topic="relationship",
            concept_groups=[frozenset({"KNOW", "VICTIM_NAME"}), frozenset({"RELATIONSHIP"}), frozenset({"VICTIM_NAME"}), frozenset({"KNOW_HIM"})],
            exclude_concepts=frozenset({"COL", "ISABELLA", "CLARA"}),
            opening=_owen_fact("relationship")["opening"],
            repeat=_owen_fact("relationship")["repeat"],
            truthfulness="true",
            emotion="regretful",
        ),
        FACT(
            topic="work_quality",
            concept_groups=[frozenset({"QUALITY"}), frozenset({"PAYMENT"})],
            exclude_concepts=frozenset({"COL", "ISABELLA", "CLARA"}),
            opening=_owen_fact("work_quality")["opening"],
            repeat=_owen_fact("work_quality")["repeat"],
            truthfulness="true",
            emotion="proud",
        ),
        FACT(
            topic="temper",
            concept_groups=[frozenset({"VIOLENCE"}), frozenset({"SIT"})],
            exclude_concepts=frozenset({"COL", "ISABELLA", "CLARA"}),
            opening=_owen_fact("temper")["opening"],
            repeat=_owen_fact("temper")["repeat"],
            truthfulness="true",
            emotion="defensive",
        ),
        FACT(
            topic="business_status",
            concept_groups=[frozenset({"BUSY", "WORK"}), frozenset({"BUSY"})],
            exclude_concepts=frozenset({"COL", "ISABELLA", "CLARA"}),
            opening=_owen_fact("business_status")["opening"],
            repeat=_owen_fact("business_status")["repeat"],
            truthfulness="true",
            emotion="guarded",
        ),
        FACT(
            topic="relationship_debt",
            sensitive=True,
            concept_groups=[frozenset({"MONEY"})],
            exclude_concepts=frozenset({"COL", "ISABELLA", "CLARA"}),
            opening=_owen_fact("relationship_debt")["opening"],
            repeat=_owen_fact("relationship_debt")["repeat"],
            truthfulness="true",
            emotion="defensive",
        ),
        FACT(
            topic="loan_amount",
            sensitive=True,
            concept_groups=[frozenset({"MONEY", "QUANTITY"})],
            exclude_concepts=frozenset({"COL", "ISABELLA", "CLARA"}),
            opening=_owen_fact("loan_amount")["opening"],
            repeat=_owen_fact("loan_amount")["repeat"],
            truthfulness="true",
            emotion="weary",
        ),
        FACT(
            topic="reaction_to_murder",
            sensitive=True,
            concept_groups=[frozenset({"FEELING", "DEATH"}), frozenset({"FEELING"})],
            exclude_concepts=frozenset({"COL", "ISABELLA", "CLARA"}),
            opening=_owen_fact("reaction_to_murder")["opening"],
            repeat=_owen_fact("reaction_to_murder")["repeat"],
            truthfulness="true",
            emotion="raw",
        ),
        FACT(
            topic="opinion_clara",
            concept_groups=[frozenset({"CLARA"})],
            opening=_owen_fact("opinion_clara")["opening"],
            repeat=_owen_fact("opinion_clara")["repeat"],
            truthfulness="true",
            emotion="neutral",
        ),
        FACT(
            topic="opinion_isabella",
            concept_groups=[frozenset({"ISABELLA"})],
            opening=_owen_fact("opinion_isabella")["opening"],
            repeat=_owen_fact("opinion_isabella")["repeat"],
            truthfulness="true",
            emotion="neutral",
        ),
    ],
    "deflect_mild": OWEN["deflect_mild"],
    "deflect_confrontational": OWEN["deflect_confrontational"],
    "deflect_unmatched": OWEN["deflect_unmatched"],
    "tension_response": OWEN["tension_response"],
}


PRIYA = {
    "agent_id": "agent_priya",
    "full_name": "Priya Shah",
    "pronoun": "she",
    "age": 33,
    "occupation": "Bookshop assistant",
    "traits": ["careful", "kind", "conflict-averse"],
    "voice_card": "Soft-spoken and apologetic; qualifies everything ('I think', 'maybe') and trails off under pressure.",
    "conflict_avoidance": 0.85,
    "honesty_baseline": 0.65,
    "baseline_habit": "she watches your face while she answers, checking that the words are landing right",
    "baseline_deviation": "She has stopped checking your face. Her answers go to the table now, and stay there.",
    "small_talk": {
        "greeting": ["Oh, um... hello, Detective.", "Hello again, Detective."],
        "name": ["Oh — Priya. Priya Shah, sorry, I should have said straight away.", "Priya Shah."],
        "how_are_you": ["I'm... okay, I think. It's just all a bit frightening.", "Still a bit shaken, if I'm honest."],
        "occupation": ["I assist Isabella at the bookshop. Unpacking, shelving... that sort of thing.", "The bookshop. Unpacking, shelving."],
        "favorite_thing": ["I love the smell of the new paperbacks when we open the boxes.", "The new paperbacks."],
        "about_me": ["I'm nobody important, really. Just trying to keep out of everyone's way.", "Just trying to help, really."],
        "feelings": ["A quiet afternoon with a good book makes me happy. Shouting... I really don't like shouting.", "Quiet things make me happy."],
        "age": ["Thirty-three."],
        "self_assessment": ["Careful, I suppose. Kind, I hope. I try not to cause anyone any trouble."],
        "closing": ["Oh — okay. Thank you.", "Right, okay."],
    },
    "facts": [
        FACT(
            topic="accusation",
            accusation=True,
            sensitive=True,
            keywords=[
                "you killed him", "did you kill him", "you murdered him", "think you killed",
                "you did it", "killed marcus", "murdered marcus", "kill marcus", "murder marcus",
                "you're the killer", "youre the killer", "you're guilty", "youre guilty",
                "why did you kill", "why did you do it", "why did you murder",
            ],
            opening=[
                "No — no, please, I could never do something like that. He was so good to me, why would I ever— please, you have to believe me.",
                "Please, no. I would never hurt him, not ever. He was so kind to me — why would you even think that? Please, please believe me.",
            ],
            repeat=["I didn't do it. Please."],
            truthfulness="true",
            emotion="distressed",
        ),
        FACT(
            topic="alibi",
            keywords=["where were you", "where you were", "alibi", "murder window", "that morning", "07:45", "7:45", "8am", "quarter to eight"],
            exclude_keywords=["isabella", "clara", "col", "ben"],
            opening=[
                "I was in the stockroom from seven. Alone, sorting the delivery. I know that's not much of an answer but it's the truth.",
                "From seven I was in the stockroom, on my own, going through the delivery. I know it isn't a great deal to go on, but it's what happened.",
            ],
            repeat=["The stockroom."],
            truthfulness="false",
            emotion="quiet",
        ),
        FACT(
            topic="location_alley",
            sensitive=True,
            keywords=["alley", "rear door", "back door", "really alone", "sure you were alone", "alone", "anyone with you", "with anyone", "ben"],
            opening=[
                "Alright. Please don't take this the wrong way. I was in the alley, for a few minutes, around a quarter to eight. With Ben. We've been seeing each other, and my apprenticeship is Isabella's to sign off, so we keep it quiet. We heard a sort of thud from the cafe side and then a door, and we got nervous someone would see us, so we left.",
                "Okay — please don't judge me for this. I slipped into the alley for a few minutes, about a quarter to eight, to meet Ben. We've been keeping it from Isabella because she signs off my apprenticeship. We heard something like a thud from the cafe, then a door, and got scared and left.",
            ],
            repeat=["The alley, with Ben, a quarter to eight. I heard the thud, then a door."],
            truthfulness="true",
            emotion="ashamed",
        ),
        FACT(
            topic="last_seen_victim",
            keywords=["last see", "last time you saw", "see marcus", "see him"],
            exclude_keywords=["isabella", "clara", "col", "ben"],
            opening=["Yesterday afternoon. He came by the shop."],
            repeat=["Yesterday. The shop."],
            truthfulness="true",
            emotion="neutral",
        ),
        FACT(
            topic="relationship",
            keywords=["relationship with marcus", "knew marcus", "know him", "how did you know"],
            exclude_keywords=["isabella", "clara", "col", "ben"],
            opening=[
                "I was sixteen, shelving books for pocket money, and he came in arguing about an invoice. He heard me correct the arithmetic and told Isabella to keep me on. I owed him the start of everything, really.",
                "I met him when I was sixteen, stacking shelves for pocket money — he was in arguing over an invoice, heard me correct the sum, and told Isabella to keep me on after that. He's the reason I have any of this.",
            ],
            repeat=["He gave me my start here, when I was sixteen. I owe him a lot."],
            truthfulness="true",
            emotion="fond",
        ),
        FACT(
            topic="relationship_secret",
            sensitive=True,
            keywords=["business", "secret", "hiding something", "not telling me", "partnership", "isabella find out"],
            # "isabella" itself is NOT excluded — "isabella find out" is a
            # legitimate positive trigger for this fact (Priya's secret is
            # specifically about hiding something *from* Isabella).
            exclude_keywords=["clara", "col", "ben"],
            opening=[
                "Marcus sponsored my apprenticeship. He believed in me when it wasn't fashionable. There are things I can't talk about yet — business things, not mine to tell. Please don't ask Isabella about them either. Not today.",
                "Marcus paid for my apprenticeship — believed in me before anyone else did. There's a business matter I still can't get into, it isn't mine alone to tell. Please, not Isabella either. Not today.",
            ],
            repeat=["There are things I still can't talk about. Business things."],
            truthfulness="true",
            emotion="anxious",
        ),
        FACT(
            topic="partnership_letter",
            sensitive=True,
            keywords=["partnership letter", "expansion", "the letter", "letter", "what did he give you"],
            exclude_keywords=["isabella", "clara", "col", "ben"],
            opening=[
                "He told me two weeks ago. The expansion, the partnership — me, not Isabella. I never asked for it! I told him it would break something between them and he said business isn't sentiment. I've been dreading Isabella finding out.",
                "Two weeks ago he told me — the expansion, the partnership, given to me and not Isabella. I never went looking for it! I warned him it would break something between the two of them, and he just said business doesn't run on sentiment. I've been dreading her finding out ever since.",
            ],
            repeat=["The partnership was mine, not Isabella's. I never asked for it."],
            truthfulness="true",
            emotion="distressed",
            gate_topic="relationship_secret",
            gate_min_ask=1,
        ),
        FACT(
            topic="reaction_to_murder",
            sensitive=True,
            keywords=["how did you feel", "when you heard", "reaction", "found out he was dead", "murder happened"],
            exclude_keywords=["isabella", "clara", "col", "ben"],
            opening=["I couldn't breathe for a moment. He was the reason I have anything at all. I keep thinking if I'd stayed at the counter instead of— never mind."],
            repeat=["It knocked the breath out of me."],
            truthfulness="true",
            emotion="distressed",
        ),
        FACT(
            topic="business_status",
            keywords=[
                "are you busy", "how's business", "hows business", "how's the shop", "hows the shop",
                "shop is quiet", "shop quiet", "business is quiet", "business quiet",
                "business is slow", "business slow", "shop is slow", "shop slow",
                "quiet today", "slow today", "busy today",
            ],
            exclude_keywords=["isabella", "clara", "col", "ben"],
            opening=["Busier than usual, actually. Everyone wants to come in and talk about it, whether they buy anything or not."],
            repeat=["Busier than normal, same as I said."],
            truthfulness="true",
            emotion="neutral",
        ),
        FACT(
            topic="opinion_isabella",
            keywords=["isabella"],
            opening=["She's been good to me. Strict, but fair. I don't want her to think badly of me."],
            repeat=["Isabella's been good to me."],
            truthfulness="true",
            emotion="anxious",
        ),
        FACT(
            topic="opinion_clara",
            keywords=["clara"],
            opening=["We're friendly enough. She always has time for a chat when I bring the post over."],
            repeat=["Clara's friendly. Nothing more to say."],
            truthfulness="true",
            emotion="neutral",
        ),
    ],
    "deflect_mild": [
        "I'm not sure, sorry.",
        "I wouldn't really know.",
        "I couldn't say, sorry.",
    ],
    "deflect_confrontational": [
        "Please, I'm not lying to you.",
        "I— I really am telling you the truth, I promise.",
        "I don't like this. Please don't shout.",
    ],
    "deflect_unmatched": [
        "I'm sorry, I don't understand what you mean.",
        "I don't know anything about that, I'm afraid.",
        "Could you ask that a different way? I don't want to get it wrong.",
    ],
}

PERSONAS = {"owen": OWEN, "priya": PRIYA, "owen_twin": OWEN_TWIN}
