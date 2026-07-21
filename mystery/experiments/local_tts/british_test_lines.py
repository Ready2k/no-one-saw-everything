"""Standard British-English test corpus for voice evaluation.

Covers the categories from the investigation brief: place names, UK
surnames, dates/times, police terminology, £ amounts, punctuation-heavy
detective dialogue, abbreviations, contractions, hesitant speech, short
replies and a long monologue. Used by synthesize_corpus.py and benchmark.py.
"""

TEST_LINES = [
    # (id, category, text)
    ("place_names", "British place names",
     "I took the early train from Marylebone, changed at Bicester, and reached "
     "Chipping Norton a little before noon; Aldeburgh was quite out of the question."),
    ("surnames", "Common and difficult UK surnames",
     "The guests were Mr. Featherstonehaugh, Mrs. Cholmondeley, Miss Marjoribanks, "
     "and a quiet couple called Smith from Leominster."),
    ("dates_times", "Dates and times",
     "It happened at quarter past seven on Tuesday the 3rd of March; the church "
     "clock struck half past before anyone thought to call for help."),
    ("police_terms", "Police terminology",
     "DCI Marsh briefed the SOCOs at the cordon, then cautioned the suspect: you do "
     "not have to say anything, but it may harm your defence if you do not mention "
     "when questioned something which you later rely on in court."),
    ("pounds", "Amounts in pounds",
     "The till was short by £3.50 on Monday, £12.20 on Wednesday, and by the end of "
     "the month two hundred and forty pounds had simply vanished."),
    ("detective_punct", "Punctuation-heavy detective dialogue",
     "\"You saw him — didn't you? — by the lych-gate,\" said the detective; \"and "
     "yet, curiously, you told Sergeant Reed you'd been at home all evening.\""),
    ("abbreviations", "Abbreviations",
     "Dr. Hale lives at no. 4, St. Mary's Rd.; the surgery opens at approx. 8 a.m., "
     "e.g. earlier than the shop."),
    ("contractions", "Contractions",
     "I shouldn't've said anything — he can't have known, and they wouldn't've "
     "believed me anyway, would they?"),
    ("hesitant", "Emotionally hesitant speech",
     "I… I don't— I wasn't anywhere near the storage room. You have to believe me. "
     "I just… I heard the thud, and I froze."),
    ("whisper", "Whispered / frightened",
     "Keep your voice down. If he hears us talking to you, I don't know what he'll do."),
    ("angry", "Angry / defensive",
     "How dare you! Twenty years I've kept that pub, and you stand there and call me "
     "a liar in front of half the village!"),
    ("tired", "Tired / resigned",
     "Fine. Yes. I was there. I'm too old to keep lying about it, Detective."),
    ("short_reply_1", "Short reply", "No."),
    ("short_reply_2", "Short reply", "Ask Clara."),
    ("short_reply_3", "Short reply", "I'd rather not say."),
    ("monologue", "Long monologue",
     "You want the whole morning, do you? Very well. I was down by half past six, as "
     "always — the ovens don't light themselves. Ben brought the flour in from the "
     "yard, late again, and I told him so. At seven the first regulars came through: "
     "Mrs. Okafor for her loaf, old Tom for his tea, the girl from the post office "
     "who never buys anything. I heard nothing unusual, no shouting, no thud — "
     "nothing until Clara came running across the green, white as chalk, saying "
     "someone had better fetch the constable, and quickly."),
]

# Per-line emotion instructions for engines that support them (qwen3_tts).
INSTRUCTIONS = {
    "hesitant": "Nervous and hesitant, voice catching, speaking quietly",
    "whisper": "Whispering, frightened, urgent",
    "angry": "Angry and defensive, raised voice, wounded pride",
    "tired": "Exhausted and resigned, flat, slow",
    "detective_punct": "Dry, probing, lightly sarcastic",
    "monologue": "A composed but wary witness giving a statement",
}
