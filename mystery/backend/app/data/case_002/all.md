
--- agents.json ---
[
  {
    "agent_id": "agent_isabella",
    "full_name": "Isabella Reed",
    "age": 41,
    "occupation": "Bookshop owner",
    "traits": [
      "ambitious",
      "wounded",
      "composed"
    ],
    "portrait": "\ud83d\udcda",
    "home_location_id": "loc_bookshop",
    "work_location_id": "loc_bookshop",
    "routine_summary": "Opens the bookshop at nine; lunchtime is for paperwork and coffee at Hobbs.",
    "voice_card": "Measured, almost rehearsed; pauses before answering and chooses polite words with visible care.",
    "relationships": [
      {
        "target_agent_id": "agent_priya",
        "relationship_type": "employer",
        "affinity": 0.3,
        "trust": 0.5,
        "tension": 0.6
      },
      {
        "target_agent_id": "agent_owen",
        "relationship_type": "acquaintance",
        "affinity": -0.2,
        "trust": 0.2,
        "tension": 0.5
      },
      {
        "target_agent_id": "agent_nadia",
        "relationship_type": "neighbour",
        "affinity": 0.4,
        "trust": 0.6,
        "tension": 0.1
      }
    ],
    "observation_skill": 0.75,
    "memory_reliability": 0.85,
    "honesty_baseline": 0.6,
    "is_victim": true,
    "sprite_asset": "Isabella_Rodriguez.png"
  },
  {
    "agent_id": "agent_priya",
    "full_name": "Priya Shah",
    "age": 33,
    "occupation": "Bookshop assistant",
    "traits": [
      "careful",
      "quietly ruthless",
      "conflict-averse surface"
    ],
    "portrait": "\ud83c\udf38",
    "home_location_id": "loc_priya_flat",
    "work_location_id": "loc_bookshop",
    "routine_summary": "Sorts lunchtime deliveries in the stockroom, then waits for Isabella.",
    "voice_card": "Soft-spoken and apologetic; qualifies everything ('I think', 'maybe') and trails off under pressure.",
    "relationships": [
      {
        "target_agent_id": "agent_isabella",
        "relationship_type": "employee",
        "affinity": -0.4,
        "trust": 0.2,
        "tension": 0.9
      },
      {
        "target_agent_id": "agent_ben",
        "relationship_type": "secret_relationship",
        "affinity": 0.9,
        "trust": 0.8,
        "tension": 0.3
      },
      {
        "target_agent_id": "agent_nadia",
        "relationship_type": "acquaintance",
        "affinity": 0.3,
        "trust": 0.5,
        "tension": 0.1
      }
    ],
    "observation_skill": 0.7,
    "memory_reliability": 0.8,
    "honesty_baseline": 0.4,
    "conflict_avoidance": 0.85,
    "sprite_asset": "Priya_Kapoor.png"
  },
  {
    "agent_id": "agent_ben",
    "full_name": "Ben Carter",
    "age": 29,
    "occupation": "Delivery driver",
    "traits": [
      "easygoing",
      "chatty",
      "bad at secrets"
    ],
    "portrait": "\ud83d\udce6",
    "home_location_id": "loc_village_square",
    "work_location_id": "loc_village_square",
    "routine_summary": "Lunchtime delivery round through the square and rear alley.",
    "voice_card": "Rambles cheerfully, over-explains when nervous, and tends to answer a question you didn't ask.",
    "relationships": [
      {
        "target_agent_id": "agent_priya",
        "relationship_type": "secret_relationship",
        "affinity": 0.9,
        "trust": 0.8,
        "tension": 0.3
      },
      {
        "target_agent_id": "agent_isabella",
        "relationship_type": "acquaintance",
        "affinity": 0.1,
        "trust": 0.3,
        "tension": 0.2
      }
    ],
    "observation_skill": 0.6,
    "memory_reliability": 0.65,
    "honesty_baseline": 0.7,
    "gossip_tendency": 0.8,
    "sprite_asset": "Ryan_Park.png"
  },
  {
    "agent_id": "agent_owen",
    "full_name": "Owen Price",
    "age": 47,
    "occupation": "Builder",
    "traits": [
      "blunt",
      "hot-tempered",
      "proud"
    ],
    "portrait": "\ud83d\udd28",
    "home_location_id": "loc_owen_house",
    "work_location_id": "loc_owen_house",
    "routine_summary": "In the timber yard; takes deliveries around eleven-thirty.",
    "voice_card": "Blunt, short sentences, no hedging; gets louder rather than more careful when pressed.",
    "relationships": [
      {
        "target_agent_id": "agent_isabella",
        "relationship_type": "debtor",
        "affinity": -0.4,
        "trust": 0.2,
        "tension": 0.8
      },
      {
        "target_agent_id": "agent_priya",
        "relationship_type": "acquaintance",
        "affinity": 0.1,
        "trust": 0.3,
        "tension": 0.1
      }
    ],
    "observation_skill": 0.5,
    "memory_reliability": 0.7,
    "honesty_baseline": 0.55,
    "conflict_avoidance": 0.2,
    "sprite_asset": "Carlos_Gomez.png"
  },
  {
    "agent_id": "agent_nadia",
    "full_name": "Nadia Cole",
    "age": 38,
    "occupation": "Clinic nurse",
    "traits": [
      "observant",
      "practical",
      "discreet"
    ],
    "portrait": "\ud83e\ude7a",
    "home_location_id": "loc_village_square",
    "work_location_id": "loc_clinic",
    "routine_summary": "Lunch shift at the clinic; crosses the square a few times.",
    "voice_card": "Calm, clinical phrasing; states observations like chart notes and avoids speculation.",
    "relationships": [
      {
        "target_agent_id": "agent_isabella",
        "relationship_type": "neighbour",
        "affinity": 0.4,
        "trust": 0.6,
        "tension": 0.1
      },
      {
        "target_agent_id": "agent_priya",
        "relationship_type": "acquaintance",
        "affinity": 0.3,
        "trust": 0.5,
        "tension": 0.1
      }
    ],
    "observation_skill": 0.85,
    "memory_reliability": 0.85,
    "honesty_baseline": 0.85,
    "gossip_tendency": 0.2,
    "sprite_asset": "Ayesha_Khan.png"
  },
  {
    "agent_id": "agent_elias",
    "full_name": "Elias Grant",
    "age": 68,
    "occupation": "Retired schoolteacher",
    "traits": [
      "nosy",
      "certain of himself",
      "harmless"
    ],
    "portrait": "\ud83c\udfa9",
    "home_location_id": "loc_village_square",
    "work_location_id": "loc_village_square",
    "routine_summary": "On the square bench every day around midday with a flask and opinions.",
    "voice_card": "Talks like he's lecturing a classroom; fond of rhetorical questions and certain of every detail.",
    "relationships": [
      {
        "target_agent_id": "agent_isabella",
        "relationship_type": "acquaintance",
        "affinity": 0.3,
        "trust": 0.5,
        "tension": 0.2
      },
      {
        "target_agent_id": "agent_owen",
        "relationship_type": "acquaintance",
        "affinity": -0.2,
        "trust": 0.3,
        "tension": 0.3
      }
    ],
    "observation_skill": 0.55,
    "memory_reliability": 0.5,
    "honesty_baseline": 0.9,
    "gossip_tendency": 0.9,
    "sprite_asset": "Adam_Smith.png"
  },
  {
    "agent_id": "agent_ruth",
    "full_name": "Ruth Calder",
    "age": 52,
    "occupation": "Postwoman",
    "traits": [
      "methodical",
      "quiet",
      "reliable"
    ],
    "portrait": "\u2709\ufe0f",
    "home_location_id": "loc_village_square",
    "work_location_id": "loc_village_square",
    "routine_summary": "Midday post round starts at 10:30, takes her past the bookshop around 11:10.",
    "voice_card": "Speaks sparingly and precisely; answers exactly the question asked, then stops.",
    "relationships": [
      {
        "target_agent_id": "agent_isabella",
        "relationship_type": "acquaintance",
        "affinity": 0.2,
        "trust": 0.5,
        "tension": 0.1
      },
      {
        "target_agent_id": "agent_priya",
        "relationship_type": "acquaintance",
        "affinity": 0.3,
        "trust": 0.5,
        "tension": 0.1
      }
    ],
    "observation_skill": 0.75,
    "memory_reliability": 0.8,
    "honesty_baseline": 0.9,
    "gossip_tendency": 0.3,
    "sprite_asset": "Sarah_Whitmore.png"
  },
  {
    "agent_id": "agent_bg_sal",
    "full_name": "Sal Ibori",
    "age": 24,
    "occupation": "Milkman",
    "portrait": "\ud83e\udd5b",
    "home_location_id": "loc_village_square",
    "work_location_id": "loc_hobbs_cafe",
    "routine_summary": "Sal keeps to a quiet milkman routine around the village.",
    "is_background": true,
    "pronoun": "he"
  },
  {
    "agent_id": "agent_bg_wren",
    "full_name": "Wren Ashby",
    "age": 27,
    "occupation": "Busker",
    "portrait": "\ud83c\udfbb",
    "home_location_id": "loc_hobbs_cafe",
    "work_location_id": "loc_clinic",
    "routine_summary": "Wren keeps to a quiet busker routine around the village.",
    "is_background": true,
    "pronoun": "she"
  },
  {
    "agent_id": "agent_bg_min",
    "full_name": "Min Okafor",
    "age": 33,
    "occupation": "Baker's assistant",
    "portrait": "\ud83e\udd56",
    "home_location_id": "loc_clinic",
    "work_location_id": "loc_owen_house",
    "routine_summary": "Min keeps to a quiet baker's assistant routine around the village.",
    "is_background": true,
    "pronoun": "she"
  },
  {
    "agent_id": "agent_bg_cole",
    "full_name": "Cole Byrne",
    "age": 61,
    "occupation": "Window cleaner",
    "portrait": "\ud83e\ude9f",
    "home_location_id": "loc_owen_house",
    "work_location_id": "loc_fountain",
    "routine_summary": "Cole keeps to a quiet window cleaner routine around the village.",
    "is_background": true,
    "pronoun": "he"
  },
  {
    "agent_id": "agent_bg_birdie",
    "full_name": "Birdie Voss",
    "age": 29,
    "occupation": "Street sweeper",
    "portrait": "\ud83e\uddf9",
    "home_location_id": "loc_fountain",
    "work_location_id": "loc_village_square",
    "routine_summary": "Birdie keeps to a quiet street sweeper routine around the village.",
    "is_background": true,
    "pronoun": "she"
  },
  {
    "agent_id": "agent_bg_rosa",
    "full_name": "Rosa Fenn",
    "age": 31,
    "occupation": "Groundskeeper",
    "portrait": "\ud83c\udf3f",
    "home_location_id": "loc_village_square",
    "work_location_id": "loc_hobbs_cafe",
    "routine_summary": "Rosa keeps to a quiet groundskeeper routine around the village.",
    "is_background": true,
    "pronoun": "she"
  },
  {
    "agent_id": "agent_bg_gus",
    "full_name": "Gus Farrow",
    "age": 37,
    "occupation": "Newspaper seller",
    "portrait": "\ud83d\udcf0",
    "home_location_id": "loc_hobbs_cafe",
    "work_location_id": "loc_clinic",
    "routine_summary": "Gus keeps to a quiet newspaper seller routine around the village.",
    "is_background": true,
    "pronoun": "he"
  },
  {
    "agent_id": "agent_bg_effie",
    "full_name": "Effie Marsh",
    "age": 49,
    "occupation": "Dog walker",
    "portrait": "\ud83d\udc15",
    "home_location_id": "loc_clinic",
    "work_location_id": "loc_owen_house",
    "routine_summary": "Effie keeps to a quiet dog walker routine around the village.",
    "is_background": true,
    "pronoun": "she"
  },
  {
    "agent_id": "agent_bg_tam",
    "full_name": "Tam Doyle",
    "age": 59,
    "occupation": "Postal carrier",
    "portrait": "\ud83d\udce8",
    "home_location_id": "loc_owen_house",
    "work_location_id": "loc_fountain",
    "routine_summary": "Tam keeps to a quiet postal carrier routine around the village.",
    "is_background": true,
    "pronoun": "he"
  },
  {
    "agent_id": "agent_bg_dez",
    "full_name": "Dez Holt",
    "age": 34,
    "occupation": "Market stallholder",
    "portrait": "\ud83e\uddfa",
    "home_location_id": "loc_fountain",
    "work_location_id": "loc_village_square",
    "routine_summary": "Dez keeps to a quiet market stallholder routine around the village.",
    "is_background": true,
    "pronoun": "he"
  }
]

--- case.json ---
{
  "case_id": "case_002",
  "case_type": "jealousy",
  "title": "The Locked Bookshop",
  "status": "locked",
  "victim_id": "agent_isabella",
  "killer_id": "agent_priya",
  "motive_summary": "Priya killed Isabella after Isabella discovered that Priya had forged her signature on the bookshop expansion documents to accelerate her inheritance of the partnership after Marcus's death.",
  "method": "blunt_force",
  "weapon_id": "obj_letter_opener",
  "murder_location_id": "loc_bookshop_back",
  "time_of_death": "12:43",
  "discovery_time": "13:15",
  "discovered_by": "agent_nadia",
  "discovery_location_id": "loc_bookshop",
  "sim_start_time": "11:30",
  "murder_window": [
    "12:35",
    "12:50"
  ],
  "overview_text": "13:15 \u2014 Isabella Reed, owner of Reed & Bell Bookshop, found dead in the bookshop back room by Nadia Cole. The back door was ajar and a window pane was broken \u2014 staged to suggest a break-in. Several villagers passed the bookshop between 12:30 and 13:00. The lunchtime hour can be rewound from 11:30."
}

--- challenges.json ---
[
  {
    "target_agent_id": "agent_priya",
    "challenged_claim_id": "claim_priya_stockroom_all_morning",
    "evidence_clue_ids": [
      "clue_invoice_discrepancy"
    ],
    "outcome": "deflect",
    "response_text": "The driver logged the time wrong on his copy \u2014 happens constantly. I signed at twelve-ten when he came back to the door. The gap you're seeing isn't a gap, it's a clerical error.",
    "emotional_shift": "tense",
    "pressure_delta": 0.15,
    "sets_claim_status": "disputed"
  },
  {
    "target_agent_id": "agent_priya",
    "challenged_claim_id": "claim_priya_not_in_back",
    "evidence_clue_ids": [
      "clue_scarf_thread"
    ],
    "outcome": "deflect",
    "response_text": "A thread. On a door I use for deliveries. My scarf catches on everything in that building \u2014 the shelf edges, the stock trolley. You can't put me in a room based on a single fibre.",
    "emotional_shift": "sharp",
    "pressure_delta": 0.2,
    "sets_claim_status": "disputed"
  },
  {
    "target_agent_id": "agent_priya",
    "challenged_claim_id": "claim_priya_not_in_back",
    "evidence_clue_ids": [
      "clue_scarf_thread",
      "clue_priya_scarf_missing_thread"
    ],
    "outcome": "partial_admission",
    "response_text": "...Fine. I was near the back door. I went to check whether an order had arrived from outside \u2014 I thought I heard something. I looked out, saw nothing, came back. That's all. I didn't go in.",
    "emotional_shift": "rattled",
    "pressure_delta": 0.3,
    "sets_claim_status": "reframed",
    "new_claims": [
      {
        "claim_id": "claim_priya_checked_back_door",
        "summary": "Priya now admits she went to the rear door but claims she only looked out, not in.",
        "claim_type": "alibi",
        "time_reference": "12:42",
        "location_reference_id": "loc_bookshop_back",
        "truthfulness": "false"
      }
    ]
  },
  {
    "target_agent_id": "agent_priya",
    "challenged_claim_id": "claim_priya_signature_genuine",
    "evidence_clue_ids": [
      "clue_forged_document",
      "clue_solicitor_letter"
    ],
    "outcome": "deflect",
    "response_text": "The signature is hers. I witnessed it. Whatever a solicitor says about letter-loops, I know what I saw. Isabella could have shaky handwriting on a bad day \u2014 she wasn't well.",
    "emotional_shift": "brittle",
    "pressure_delta": 0.25,
    "sets_claim_status": "disputed"
  },
  {
    "target_agent_id": "agent_priya",
    "challenged_claim_id": "claim_priya_stockroom_all_morning",
    "evidence_clue_ids": [
      "clue_crash_sound",
      "clue_invoice_discrepancy"
    ],
    "outcome": "partial_admission",
    "response_text": "I... I want a moment. Please. I need to think about what I'm saying. I didn't do anything to Isabella. You have to believe that. Whatever else you think you've found, I didn't \u2014 I wouldn't \u2014",
    "emotional_shift": "close_to_breaking",
    "pressure_delta": 0.4,
    "sets_claim_status": "disputed"
  },
  {
    "target_agent_id": "agent_priya",
    "challenged_claim_id": "claim_priya_not_in_back",
    "evidence_clue_ids": [
      "clue_ben_argument_glimpse"
    ],
    "outcome": "partial_admission",
    "response_text": "He saw me from the doorway for a second, that's all. Isabella had called me through to accuse me of things she didn't understand. We argued. I left. That doesn't make me a murderer.",
    "emotional_shift": "rattled",
    "pressure_delta": 0.25,
    "sets_claim_status": "reframed",
    "new_claims": [
      {
        "claim_id": "claim_priya_argument_only",
        "summary": "Priya now admits she argued with Isabella in the back room but claims she left before anything violent happened.",
        "claim_type": "alibi",
        "time_reference": "12:38",
        "location_reference_id": "loc_bookshop_back",
        "truthfulness": "false"
      }
    ]
  },
  {
    "target_agent_id": "agent_owen",
    "challenged_claim_id": "claim_owen_yard",
    "evidence_clue_ids": [
      "clue_owen_bookshop_pass"
    ],
    "outcome": "reframe",
    "response_text": "I walked past the bookshop on my way to the builders' merchants at twelve-twenty. I stopped for half a second to see if Isabella was in \u2014 I wanted a word before I got her solicitor's next letter. She wasn't at the window. I kept walking. I was back in my yard by half past at the latest.",
    "emotional_shift": "steady",
    "pressure_delta": 0.1,
    "sets_claim_status": "confirmed",
    "reveals_clue_ids": [
      "clue_owen_yard_alibi"
    ]
  }
]

--- clues.json ---
{
  "clues": [
    {
      "clue_id": "clue_solicitor_letter",
      "title": "Letter from Whittle & Cross",
      "clue_type": "document",
      "description": "A letter from the firm Whittle & Cross, delivered this afternoon and found already opened on Isabella's desk: 'Confirming our appointment at 13:30 today to review irregularities in the bookshop partnership transfer documents.' Isabella had found something wrong \u2014 and had booked a solicitor.",
      "strength": "strong",
      "reliability": 0.95,
      "ambiguity": "low",
      "discoverability": {
        "method": "inspect",
        "location_id": "loc_bookshop_back"
      },
      "supports_conclusion_ids": [
        "conc_priya_motive"
      ],
      "linked_agent_ids": [
        "agent_isabella"
      ],
      "linked_object_ids": [
        "obj_solicitor_letter"
      ],
      "linked_event_ids": [
        "ev_1110_solicitor_letter_delivered"
      ]
    },
    {
      "clue_id": "clue_forged_document",
      "title": "Forged partnership transfer document",
      "clue_type": "physical_evidence",
      "description": "In the safe behind the loose back panel: a signed transfer document putting the bookshop expansion in Priya's name. The signature reads 'I. Reed' but the loop on the capital R is reversed \u2014 inconsistent with every other sample of Isabella's handwriting in the room.",
      "strength": "strong",
      "reliability": 0.95,
      "ambiguity": "low",
      "discoverability": {
        "method": "inspect",
        "location_id": "loc_bookshop_back",
        "required_prior_clue_ids": [
          "clue_solicitor_letter"
        ]
      },
      "supports_conclusion_ids": [
        "conc_priya_motive"
      ],
      "linked_agent_ids": [
        "agent_priya",
        "agent_isabella"
      ],
      "linked_object_ids": [
        "obj_forged_document"
      ]
    },
    {
      "clue_id": "clue_scarf_thread",
      "title": "Green thread on the rear door latch",
      "clue_type": "physical_evidence",
      "description": "A single thread of emerald-green wool caught on the sharp edge of the bookshop's rear door latch. The same shade as Priya's scarf \u2014 and the scarf, still hanging on the stockroom hook, has a small pulled loop on one end.",
      "strength": "strong",
      "reliability": 0.9,
      "ambiguity": "low",
      "discoverability": {
        "method": "inspect",
        "location_id": "loc_bookshop_back"
      },
      "supports_conclusion_ids": [
        "conc_priya_opportunity"
      ],
      "linked_agent_ids": [
        "agent_priya"
      ],
      "linked_object_ids": [
        "obj_priya_scarf"
      ],
      "linked_event_ids": [
        "ev_1245_priya_stages"
      ]
    },
    {
      "clue_id": "clue_staged_breakin",
      "title": "Glass broke from inside",
      "clue_type": "physical_evidence",
      "description": "The broken window pane in the back room: large shards and the frame splinter lie inside the room. Only smaller fragments are outside in the alley. A genuine break-in would show the opposite. Someone broke this pane from inside to simulate forced entry.",
      "strength": "strong",
      "reliability": 0.95,
      "ambiguity": "medium",
      "discoverability": {
        "method": "inspect",
        "location_id": "loc_bookshop_back"
      },
      "supports_conclusion_ids": [
        "conc_staged_scene"
      ],
      "linked_agent_ids": [
        "agent_priya"
      ],
      "linked_object_ids": [
        "obj_broken_window_glass"
      ]
    },
    {
      "clue_id": "clue_letter_opener_wiped",
      "title": "Letter opener \u2014 wiped clean and replaced",
      "clue_type": "physical_evidence",
      "description": "The Victorian letter opener in the pen pot on Isabella's desk. Despite being the nearest heavy implement to the wound, it shows no fingerprints at all \u2014 it has been recently wiped. And the pen pot stands slightly off its usual ring-mark, as if hurriedly returned.",
      "strength": "strong",
      "reliability": 0.9,
      "ambiguity": "medium",
      "discoverability": {
        "method": "inspect",
        "location_id": "loc_bookshop_back"
      },
      "supports_conclusion_ids": [
        "conc_method",
        "conc_priya_means"
      ],
      "linked_agent_ids": [
        "agent_priya"
      ],
      "linked_object_ids": [
        "obj_letter_opener"
      ]
    },
    {
      "clue_id": "clue_invoice_discrepancy",
      "title": "Invoice timestamp mismatch",
      "clue_type": "document",
      "description": "The delivery invoice on the stockroom table is signed by Priya at 12:10. The driver's carbon copy, however, records the delivery complete at 12:05. Five minutes are unaccounted for \u2014 exactly when she claims to have been shelving books, proving she was elsewhere and breaking her alibi.",
      "strength": "medium",
      "reliability": 0.85,
      "ambiguity": "medium",
      "discoverability": {
        "method": "inspect",
        "location_id": "loc_bookshop"
      },
      "supports_conclusion_ids": [
        "conc_priya_opportunity"
      ],
      "linked_agent_ids": [
        "agent_priya"
      ],
      "linked_object_ids": [
        "obj_stockroom_invoice"
      ]
    },
    {
      "clue_id": "clue_ruth_post_sighting",
      "title": "Solicitor's letter delivered sealed",
      "clue_type": "witness_statement",
      "description": "Ruth confirms she pushed the Whittle & Cross letter through the bookshop door sealed and unopened at 11:10. By 12:00, Priya had already read it \u2014 before Isabella arrived. Priya knew exactly what Isabella was about to bring to the solicitor.",
      "strength": "medium",
      "reliability": 0.9,
      "ambiguity": "medium",
      "discoverability": {
        "method": "interview",
        "agent_id": "agent_ruth",
        "question_type": "timeline"
      },
      "supports_conclusion_ids": [
        "conc_priya_motive"
      ],
      "linked_agent_ids": [
        "agent_ruth"
      ],
      "linked_event_ids": [
        "ev_1110_solicitor_letter_delivered",
        "ev_1200_priya_sees_letter"
      ]
    },
    {
      "clue_id": "clue_crash_sound",
      "title": "A crash from the bookshop back room",
      "clue_type": "witness_statement",
      "description": "Ruth heard a sharp crash \u2014 like furniture going over \u2014 from the back of the bookshop at around 12:40 while she was finishing her round along the rear alley. She assumed it was boxes falling in the stockroom.",
      "strength": "medium",
      "reliability": 0.8,
      "ambiguity": "medium",
      "discoverability": {
        "method": "interview",
        "agent_id": "agent_ruth",
        "question_type": "timeline"
      },
      "supports_conclusion_ids": [
        "conc_method",
        "conc_priya_opportunity"
      ],
      "linked_event_ids": [
        "ev_1240_sound_crash"
      ]
    },
    {
      "clue_id": "clue_isabella_early_arrival",
      "title": "Isabella arrived early and went straight inside",
      "clue_type": "witness_statement",
      "description": "Elias saw Isabella arrive at 12:32, nearly half an hour before her usual opening time. She didn't stop to talk to anyone \u2014 just went directly in. Something had brought her in early.",
      "strength": "medium",
      "reliability": 0.8,
      "ambiguity": "medium",
      "discoverability": {
        "method": "interview",
        "agent_id": "agent_elias",
        "question_type": "timeline"
      },
      "supports_conclusion_ids": [
        "conc_priya_motive"
      ],
      "linked_event_ids": [
        "ev_1232_isabella_arrives"
      ]
    },
    {
      "clue_id": "clue_ben_argument_glimpse",
      "title": "Ben saw Priya in the back room mid-argument",
      "clue_type": "witness_statement",
      "description": "At about 12:38, Ben stepped just inside the bookshop with a mis-sorted parcel and glanced through the half-open counter door. He saw Priya in the back room close to Isabella's desk while Isabella, one hand near the telephone, snapped: 'You do not get to decide this for me.' Priya later claimed she never went into the back room at all.",
      "strength": "strong",
      "reliability": 0.85,
      "ambiguity": "medium",
      "discoverability": {
        "method": "interview",
        "agent_id": "agent_ben",
        "question_type": "timeline"
      },
      "supports_conclusion_ids": [
        "conc_priya_opportunity",
        "conc_priya_false_alibi"
      ],
      "linked_agent_ids": [
        "agent_ben",
        "agent_priya",
        "agent_isabella"
      ],
      "linked_event_ids": [
        "ev_1238_ben_argument_glimpse"
      ]
    },
    {
      "clue_id": "clue_owen_bookshop_pass",
      "title": "Owen lingered at the bookshop window",
      "clue_type": "witness_statement",
      "description": "Elias noticed Owen pausing at the bookshop window at 12:25, a rolled-up letter in hand. Owen had received a new debt-demand notice from Isabella that morning.",
      "strength": "medium",
      "reliability": 0.75,
      "ambiguity": "medium",
      "discoverability": {
        "method": "interview",
        "agent_id": "agent_elias",
        "question_type": "timeline"
      },
      "supports_conclusion_ids": [
        "conc_owen_red_herring"
      ],
      "linked_agent_ids": [
        "agent_owen"
      ],
      "linked_event_ids": [
        "ev_1225_owen_confronts_bookshop"
      ]
    },
    {
      "clue_id": "clue_owen_debt_folder",
      "title": "Owen's debt folder in Isabella's desk",
      "clue_type": "document",
      "description": "A folder in Isabella's drawer: letters to Owen Price demanding repayment of a personal loan by month's end, with a note in Isabella's hand \u2014 'next step: solicitor, 11th.' Today is the 11th.",
      "strength": "medium",
      "reliability": 0.9,
      "ambiguity": "medium",
      "discoverability": {
        "method": "inspect",
        "location_id": "loc_bookshop_back"
      },
      "supports_conclusion_ids": [
        "conc_owen_red_herring"
      ],
      "linked_agent_ids": [
        "agent_owen"
      ],
      "linked_object_ids": [
        "obj_owen_debt_folder"
      ]
    },
    {
      "clue_id": "clue_owen_yard_alibi",
      "title": "Owen was in his yard all lunchtime",
      "clue_type": "witness_statement",
      "description": "Owen says he was pouring a concrete pad in his yard from 11:00 until 13:30 and that two of his lads were with him the whole time. The job would have been hard to abandon, but this account comes from Owen himself.",
      "strength": "medium",
      "reliability": 0.75,
      "ambiguity": "medium",
      "discoverability": {
        "method": "interview",
        "agent_id": "agent_owen",
        "question_type": "alibi"
      },
      "supports_conclusion_ids": [
        "conc_owen_innocent"
      ],
      "linked_agent_ids": [
        "agent_owen"
      ]
    },
    {
      "clue_id": "clue_ben_broken_window",
      "title": "Ben noticed the broken window",
      "clue_type": "witness_statement",
      "description": "Ben mentioned at the cafe at 13:00 that the bookshop's back window looked broken. When he passed the alley at about 12:50, he noticed a scatter of glass outside but a larger shard still sitting inside on the sill \u2014 enough to strike him as odd even before he heard Isabella was dead.",
      "strength": "medium",
      "reliability": 0.8,
      "ambiguity": "medium",
      "discoverability": {
        "method": "interview",
        "agent_id": "agent_ben",
        "question_type": "timeline"
      },
      "supports_conclusion_ids": [
        "conc_staged_scene"
      ],
      "linked_event_ids": [
        "ev_1250_ruth_alley_sighting"
      ],
      "linked_location_ids": [
        "loc_rear_alley"
      ]
    },
    {
      "clue_id": "clue_priya_stockroom_claim",
      "title": "Priya claims she was shelving stock all lunchtime",
      "clue_type": "witness_statement",
      "description": "Priya says she was in the stockroom from 11:00 until Nadia arrived. But she cannot account for the gap between 12:10 (when the invoice was signed) and 12:48 (when she was heard shelving books).",
      "strength": "medium",
      "reliability": 0.4,
      "ambiguity": "high",
      "discoverability": {
        "method": "interview",
        "agent_id": "agent_priya",
        "question_type": "alibi"
      },
      "supports_conclusion_ids": [
        "conc_priya_false_alibi"
      ],
      "linked_agent_ids": [
        "agent_priya"
      ]
    },
    {
      "clue_id": "clue_priya_scarf_missing_thread",
      "title": "Loose thread on Priya's scarf",
      "clue_type": "physical_evidence",
      "description": "Priya's green scarf hangs in the stockroom. Inspect it closely: one end has a small pulled loop, matching exactly the thread snagged on the rear door latch \u2014 same weight, same shade, same twist direction.",
      "strength": "medium",
      "reliability": 0.85,
      "ambiguity": "medium",
      "discoverability": {
        "method": "inspect",
        "location_id": "loc_bookshop",
        "required_prior_clue_ids": [
          "clue_scarf_thread"
        ]
      },
      "supports_conclusion_ids": [
        "conc_priya_opportunity"
      ],
      "linked_agent_ids": [
        "agent_priya"
      ],
      "linked_object_ids": [
        "obj_priya_scarf"
      ]
    }
  ],
  "conclusions": [
    {
      "conclusion_id": "conc_priya_motive",
      "type": "motive",
      "summary": "Priya had forged Isabella's signature on the partnership transfer. Isabella had discovered this and booked a solicitor. Priya read the letter before Isabella arrived \u2014 she knew she had hours.",
      "target_agent_id": "agent_priya",
      "required_for_solution": true,
      "supported_by_clue_ids": [
        "clue_solicitor_letter",
        "clue_forged_document",
        "clue_ruth_post_sighting"
      ]
    },
    {
      "conclusion_id": "conc_priya_opportunity",
      "type": "opportunity",
      "summary": "Ben saw Priya with Isabella in the back room during the murder window. Her invoice alibi has a 40-minute gap, and the green thread puts her at the rear door she claims not to have used.",
      "target_agent_id": "agent_priya",
      "required_for_solution": true,
      "supported_by_clue_ids": [
        "clue_ben_argument_glimpse",
        "clue_invoice_discrepancy",
        "clue_scarf_thread",
        "clue_priya_scarf_missing_thread",
        "clue_priya_stockroom_claim"
      ]
    },
    {
      "conclusion_id": "conc_priya_means",
      "type": "means",
      "summary": "The letter opener was the nearest heavy object and has been recently wiped clean \u2014 it was used and returned.",
      "target_agent_id": "agent_priya",
      "required_for_solution": true,
      "supported_by_clue_ids": [
        "clue_letter_opener_wiped"
      ]
    },
    {
      "conclusion_id": "conc_method",
      "type": "method",
      "summary": "Isabella was struck with the Victorian letter opener in the back room at approximately 12:43.",
      "required_for_solution": true,
      "supported_by_clue_ids": [
        "clue_letter_opener_wiped",
        "clue_crash_sound"
      ]
    },
    {
      "conclusion_id": "conc_staged_scene",
      "type": "staged_scene",
      "summary": "The broken window was staged from the inside to suggest an unknown intruder. The glass distribution proves it.",
      "required_for_solution": false,
      "supported_by_clue_ids": [
        "clue_staged_breakin",
        "clue_ben_broken_window"
      ]
    },
    {
      "conclusion_id": "conc_priya_false_alibi",
      "type": "false_alibi",
      "summary": "Priya's claim to have been in the stockroom all lunchtime is undermined by the invoice gap and the thread on the rear door.",
      "target_agent_id": "agent_priya",
      "required_for_solution": true,
      "supported_by_clue_ids": [
        "clue_ben_argument_glimpse",
        "clue_invoice_discrepancy",
        "clue_scarf_thread",
        "clue_priya_stockroom_claim"
      ]
    },
    {
      "conclusion_id": "conc_owen_red_herring",
      "type": "red_herring",
      "summary": "Owen had a significant debt to Isabella that was due today and was seen lingering outside the bookshop in anger.",
      "target_agent_id": "agent_owen",
      "supported_by_clue_ids": [
        "clue_owen_bookshop_pass",
        "clue_owen_debt_folder"
      ]
    },
    {
      "conclusion_id": "conc_owen_innocent",
      "type": "innocence_anchor",
      "summary": "Owen was in his yard pouring concrete with two workers present from 11:00 until 13:30.",
      "target_agent_id": "agent_owen",
      "supported_by_clue_ids": [
        "clue_owen_yard_alibi"
      ]
    }
  ]
}

--- events.json ---
[
  {
    "event_id": "ev_1030_priya_wakes",
    "time": "10:30",
    "location_id": "loc_priya_flat",
    "agent_ids": [
      "agent_priya"
    ],
    "event_type": "routine",
    "truth_description": "Priya rises, dresses, and tucks the green scarf around her neck. She sits at her kitchen table for twenty minutes, very still.",
    "visibility": "private",
    "importance": 3
  },
  {
    "event_id": "ev_1040_elias_bench",
    "time": "10:40",
    "location_id": "loc_village_square",
    "agent_ids": [
      "agent_elias"
    ],
    "event_type": "routine",
    "truth_description": "Elias settles onto his usual bench with a flask, facing the bookshop and cafe.",
    "visibility": "public",
    "importance": 2
  },
  {
    "event_id": "ev_1050_nadia_shift",
    "time": "10:50",
    "location_id": "loc_clinic",
    "agent_ids": [
      "agent_nadia"
    ],
    "event_type": "routine",
    "truth_description": "Nadia opens the clinic for the early shift.",
    "visibility": "public",
    "importance": 2
  },
  {
    "event_id": "ev_1100_priya_arrives_bookshop",
    "time": "11:00",
    "location_id": "loc_bookshop",
    "agent_ids": [
      "agent_priya"
    ],
    "event_type": "arrival",
    "truth_description": "Priya lets herself into the bookshop with her key and goes directly to the stockroom.",
    "visibility": "public",
    "visible_to_agent_ids": [
      "agent_elias"
    ],
    "importance": 3
  },
  {
    "event_id": "ev_1110_solicitor_letter_delivered",
    "time": "11:10",
    "location_id": "loc_bookshop",
    "agent_ids": [
      "agent_ruth"
    ],
    "event_type": "routine",
    "truth_description": "Ruth delivers the post. She slots a letter from Whittle & Cross through the bookshop door \u2014 it lands on the mat.",
    "player_description": "The postwoman delivers letters to the bookshop.",
    "visibility": "public",
    "visible_to_agent_ids": [
      "agent_elias"
    ],
    "importance": 5,
    "object_ids": [
      "obj_solicitor_letter"
    ],
    "linked_clue_ids": [
      "clue_solicitor_letter"
    ]
  },
  {
    "event_id": "ev_1130_ben_round",
    "time": "11:30",
    "location_id": "loc_village_square",
    "agent_ids": [
      "agent_ben"
    ],
    "event_type": "movement",
    "truth_description": "Ben parks his van by the square and starts his delivery round.",
    "visibility": "public",
    "importance": 3
  },
  {
    "event_id": "ev_1200_priya_sees_letter",
    "time": "12:00",
    "location_id": "loc_bookshop",
    "agent_ids": [
      "agent_priya"
    ],
    "event_type": "object_use",
    "truth_description": "Priya picks up the post from the mat and reads the solicitor's letter. The colour drains from her face. She folds it back into its envelope and goes to the back room.",
    "visibility": "hidden",
    "object_ids": [
      "obj_solicitor_letter"
    ],
    "importance": 9,
    "linked_clue_ids": [
      "clue_solicitor_letter",
      "clue_ruth_post_sighting"
    ]
  },
  {
    "event_id": "ev_1205_priya_safe",
    "time": "12:05",
    "location_id": "loc_bookshop_back",
    "agent_ids": [
      "agent_priya"
    ],
    "event_type": "hidden_action",
    "truth_description": "Priya opens the safe, removes the forged document, and reads it again. She replaces it and sits at the desk.",
    "visibility": "hidden",
    "object_ids": [
      "obj_forged_document"
    ],
    "importance": 8
  },
  {
    "event_id": "ev_1210_invoice_signed",
    "time": "12:10",
    "location_id": "loc_bookshop",
    "agent_ids": [
      "agent_priya"
    ],
    "event_type": "object_use",
    "truth_description": "Priya signs the delivery invoice in the stockroom \u2014 but the driver has already gone. She back-dates it by five minutes.",
    "player_description": "A delivery receipt on the stockroom table, signed by Priya at 12:10.",
    "visibility": "public",
    "object_ids": [
      "obj_stockroom_invoice"
    ],
    "importance": 6,
    "linked_clue_ids": [
      "clue_invoice_discrepancy"
    ]
  },
  {
    "event_id": "ev_1225_owen_confronts_bookshop",
    "time": "12:25",
    "location_id": "loc_village_square",
    "agent_ids": [
      "agent_owen"
    ],
    "event_type": "movement",
    "truth_description": "Owen strides past the bookshop, glances in, and keeps walking. He looks furious \u2014 another late notice on the debt arrived this afternoon.",
    "player_description": "Owen Price walks past the bookshop with a rolled-up letter in his fist. He pauses at the window.",
    "visibility": "public",
    "visible_to_agent_ids": [
      "agent_elias"
    ],
    "importance": 7,
    "linked_clue_ids": [
      "clue_owen_bookshop_pass"
    ]
  },
  {
    "event_id": "ev_1232_isabella_arrives",
    "time": "12:32",
    "location_id": "loc_bookshop",
    "agent_ids": [
      "agent_isabella"
    ],
    "event_type": "arrival",
    "truth_description": "Isabella arrives at the bookshop and goes straight to the back room. She finds the solicitor's letter already opened on the desk.",
    "player_description": "Isabella Reed arrives at the bookshop earlier than usual and goes directly inside.",
    "visibility": "public",
    "visible_to_agent_ids": [
      "agent_elias",
      "agent_ruth"
    ],
    "importance": 7,
    "linked_clue_ids": [
      "clue_isabella_early_arrival"
    ]
  },
  {
    "event_id": "ev_1235_confrontation",
    "time": "12:35",
    "location_id": "loc_bookshop_back",
    "agent_ids": [
      "agent_isabella",
      "agent_priya"
    ],
    "event_type": "argument",
    "truth_description": "Isabella confronts Priya about the forged signature. Voices rise. Priya insists the transfer was inevitable anyway; Isabella says inevitability is not consent and gives her until 13:30 to tell the truth before she hands everything to the solicitor.",
    "visibility": "hidden",
    "audible_to_agent_ids": [],
    "importance": 10,
    "object_ids": [
      "obj_forged_document",
      "obj_solicitor_letter"
    ]
  },
  {
    "event_id": "ev_1238_ben_argument_glimpse",
    "time": "12:38",
    "location_id": "loc_bookshop",
    "agent_ids": [
      "agent_ben",
      "agent_isabella",
      "agent_priya"
    ],
    "event_type": "sighting",
    "truth_description": "Ben steps into the front shop with a mis-sorted parcel for Hobbs Cafe. Through the half-open counter door he catches a glimpse of Priya in the back room, close to Isabella's desk, while Isabella stands by the telephone saying, 'You do not get to decide this for me.' Ben retreats, embarrassed to have walked in on it.",
    "player_description": "Ben briefly steps into the bookshop front and backs out again, looking awkward.",
    "visibility": "public_partial",
    "visible_to_agent_ids": [
      "agent_ben"
    ],
    "importance": 8,
    "linked_clue_ids": [
      "clue_ben_argument_glimpse"
    ]
  },
  {
    "event_id": "ev_1240_sound_crash",
    "time": "12:40",
    "location_id": "loc_rear_alley",
    "agent_ids": [],
    "event_type": "sound",
    "truth_description": "A sharp crash \u2014 a chair overturning \u2014 is audible from the bookshop back room.",
    "player_description": "A sharp crack, like furniture going over, from the back of the bookshop.",
    "visibility": "public_partial",
    "audible_to_agent_ids": [
      "agent_ruth"
    ],
    "importance": 8,
    "linked_clue_ids": [
      "clue_crash_sound"
    ]
  },
  {
    "event_id": "ev_1243_murder",
    "time": "12:43",
    "location_id": "loc_bookshop_back",
    "agent_ids": [
      "agent_priya",
      "agent_isabella"
    ],
    "event_type": "murder",
    "truth_description": "Isabella reaches for the desk telephone. Priya lunges across the desk, seizes the heavy brass letter opener, and brings it down in a panicked blow to Isabella's head. Isabella collapses. Priya stands trembling for thirty seconds, then acts.",
    "visibility": "hidden",
    "object_ids": [
      "obj_letter_opener"
    ],
    "importance": 10
  },
  {
    "event_id": "ev_1245_priya_stages",
    "time": "12:45",
    "location_id": "loc_bookshop_back",
    "agent_ids": [
      "agent_priya"
    ],
    "event_type": "hidden_action",
    "truth_description": "Priya wipes the letter opener and replaces it in the pen pot. She breaks the window pane from inside using a crate corner and scatters a crate across the alley side. She leaves through the rear door, snagging her scarf on the latch.",
    "visibility": "hidden",
    "object_ids": [
      "obj_letter_opener",
      "obj_broken_window_glass",
      "obj_priya_scarf"
    ],
    "importance": 10,
    "linked_clue_ids": [
      "clue_staged_breakin",
      "clue_scarf_thread"
    ]
  },
  {
    "event_id": "ev_1248_priya_stockroom_return",
    "time": "12:48",
    "location_id": "loc_bookshop",
    "agent_ids": [
      "agent_priya"
    ],
    "event_type": "arrival",
    "truth_description": "Priya re-enters through the bookshop front door \u2014 she had slipped out through the rear alley and come around the square. She goes to the stockroom, removes her scarf (noticing the loose thread too late), and begins loudly shelving books.",
    "player_description": "Priya is shelving stock in the back of the shop when others arrive.",
    "visibility": "public_partial",
    "object_ids": [
      "obj_priya_scarf"
    ],
    "importance": 8
  },
  {
    "event_id": "ev_1250_ruth_alley_sighting",
    "time": "12:50",
    "location_id": "loc_rear_alley",
    "agent_ids": [
      "agent_ruth"
    ],
    "event_type": "sighting",
    "truth_description": "Ruth, finishing her round, passes the rear alley and notices the broken pane and a single green thread caught on the bookshop's rear door latch. She pauses, frowns, and walks on.",
    "player_description": "The postwoman pauses in the rear alley, looking at something near the bookshop's back door.",
    "visibility": "public_partial",
    "visible_to_agent_ids": [
      "agent_ben"
    ],
    "importance": 7,
    "linked_clue_ids": [
      "clue_scarf_thread",
      "clue_staged_breakin"
    ]
  },
  {
    "event_id": "ev_1300_ben_cafe_chat",
    "time": "13:00",
    "location_id": "loc_hobbs_cafe",
    "agent_ids": [
      "agent_ben"
    ],
    "event_type": "routine",
    "truth_description": "Ben finishes his round and stops for a coffee at Hobbs. He mentions to the person behind the counter that 'something looked off at the bookshop back' \u2014 the broken window.",
    "visibility": "public",
    "importance": 5,
    "linked_clue_ids": [
      "clue_ben_broken_window"
    ]
  },
  {
    "event_id": "ev_1315_nadia_discovery",
    "time": "13:15",
    "location_id": "loc_bookshop_back",
    "agent_ids": [
      "agent_nadia",
      "agent_isabella"
    ],
    "event_type": "body_discovery",
    "truth_description": "Nadia stops by to borrow a medical reference from Isabella. When Priya says Isabella must be in the back, Nadia pushes through the counter door and finds Isabella collapsed behind the desk.",
    "player_description": "Nadia Cole finds Isabella Reed dead in the bookshop back room. The rear window is broken. The back door is ajar.",
    "visibility": "public",
    "importance": 10
  },
  {
    "event_id": "ev_bg_sal_0",
    "time": "11:32",
    "location_id": "loc_village_square",
    "agent_ids": [
      "agent_bg_sal"
    ],
    "event_type": "arrival",
    "truth_description": "Sal is seen near Village Square, leaving bottles on the step.",
    "importance": 2,
    "to_location_id": "loc_village_square"
  },
  {
    "event_id": "ev_bg_sal_1",
    "time": "11:52",
    "location_id": "loc_hobbs_cafe",
    "agent_ids": [
      "agent_bg_sal"
    ],
    "event_type": "movement",
    "truth_description": "Sal is seen near Hobbs Cafe, leaving bottles on the step.",
    "importance": 2,
    "from_location_id": "loc_village_square",
    "to_location_id": "loc_hobbs_cafe"
  },
  {
    "event_id": "ev_bg_wren_0",
    "time": "11:39",
    "location_id": "loc_hobbs_cafe",
    "agent_ids": [
      "agent_bg_wren"
    ],
    "event_type": "arrival",
    "truth_description": "Wren is seen near Hobbs Cafe, tuning up for a lunchtime busk.",
    "importance": 2,
    "to_location_id": "loc_hobbs_cafe"
  },
  {
    "event_id": "ev_bg_wren_1",
    "time": "11:54",
    "location_id": "loc_clinic",
    "agent_ids": [
      "agent_bg_wren"
    ],
    "event_type": "movement",
    "truth_description": "Wren is seen near Village Clinic, tuning up for a lunchtime busk.",
    "importance": 2,
    "from_location_id": "loc_hobbs_cafe",
    "to_location_id": "loc_clinic"
  },
  {
    "event_id": "ev_bg_wren_2",
    "time": "12:09",
    "location_id": "loc_owen_house",
    "agent_ids": [
      "agent_bg_wren"
    ],
    "event_type": "movement",
    "truth_description": "Wren is seen near Owen Price's House & Yard, tuning up for a lunchtime busk.",
    "importance": 2,
    "from_location_id": "loc_clinic",
    "to_location_id": "loc_owen_house"
  },
  {
    "event_id": "ev_bg_min_0",
    "time": "11:46",
    "location_id": "loc_clinic",
    "agent_ids": [
      "agent_bg_min"
    ],
    "event_type": "arrival",
    "truth_description": "Min is seen near Village Clinic, carrying a tray of loaves.",
    "importance": 2,
    "to_location_id": "loc_clinic"
  },
  {
    "event_id": "ev_bg_min_1",
    "time": "12:01",
    "location_id": "loc_owen_house",
    "agent_ids": [
      "agent_bg_min"
    ],
    "event_type": "movement",
    "truth_description": "Min is seen near Owen Price's House & Yard, carrying a tray of loaves.",
    "importance": 2,
    "from_location_id": "loc_clinic",
    "to_location_id": "loc_owen_house"
  },
  {
    "event_id": "ev_bg_min_2",
    "time": "12:16",
    "location_id": "loc_fountain",
    "agent_ids": [
      "agent_bg_min"
    ],
    "event_type": "movement",
    "truth_description": "Min is seen near Fountain, carrying a tray of loaves.",
    "importance": 2,
    "from_location_id": "loc_owen_house",
    "to_location_id": "loc_fountain"
  },
  {
    "event_id": "ev_bg_cole_0",
    "time": "11:53",
    "location_id": "loc_owen_house",
    "agent_ids": [
      "agent_bg_cole"
    ],
    "event_type": "arrival",
    "truth_description": "Cole is seen near Owen Price's House & Yard, wiping down the windows.",
    "importance": 2,
    "to_location_id": "loc_owen_house"
  },
  {
    "event_id": "ev_bg_cole_1",
    "time": "12:08",
    "location_id": "loc_fountain",
    "agent_ids": [
      "agent_bg_cole"
    ],
    "event_type": "movement",
    "truth_description": "Cole is seen near Fountain, wiping down the windows.",
    "importance": 2,
    "from_location_id": "loc_owen_house",
    "to_location_id": "loc_fountain"
  },
  {
    "event_id": "ev_bg_cole_2",
    "time": "12:23",
    "location_id": "loc_village_square",
    "agent_ids": [
      "agent_bg_cole"
    ],
    "event_type": "movement",
    "truth_description": "Cole is seen near Village Square, wiping down the windows.",
    "importance": 2,
    "from_location_id": "loc_fountain",
    "to_location_id": "loc_village_square"
  },
  {
    "event_id": "ev_bg_birdie_0",
    "time": "12:00",
    "location_id": "loc_fountain",
    "agent_ids": [
      "agent_bg_birdie"
    ],
    "event_type": "arrival",
    "truth_description": "Birdie is seen near Fountain, sweeping the front step.",
    "importance": 2,
    "to_location_id": "loc_fountain"
  },
  {
    "event_id": "ev_bg_birdie_1",
    "time": "12:15",
    "location_id": "loc_village_square",
    "agent_ids": [
      "agent_bg_birdie"
    ],
    "event_type": "movement",
    "truth_description": "Birdie is seen near Village Square, sweeping the front step.",
    "importance": 2,
    "from_location_id": "loc_fountain",
    "to_location_id": "loc_village_square"
  },
  {
    "event_id": "ev_bg_birdie_2",
    "time": "12:30",
    "location_id": "loc_hobbs_cafe",
    "agent_ids": [
      "agent_bg_birdie"
    ],
    "event_type": "movement",
    "truth_description": "Birdie is seen near Hobbs Cafe, sweeping the front step.",
    "importance": 2,
    "from_location_id": "loc_village_square",
    "to_location_id": "loc_hobbs_cafe"
  },
  {
    "event_id": "ev_bg_rosa_0",
    "time": "11:37",
    "location_id": "loc_village_square",
    "agent_ids": [
      "agent_bg_rosa"
    ],
    "event_type": "arrival",
    "truth_description": "Rosa is seen near Village Square, tending the flowerbeds.",
    "importance": 2,
    "to_location_id": "loc_village_square"
  },
  {
    "event_id": "ev_bg_rosa_1",
    "time": "11:52",
    "location_id": "loc_hobbs_cafe",
    "agent_ids": [
      "agent_bg_rosa"
    ],
    "event_type": "movement",
    "truth_description": "Rosa is seen near Hobbs Cafe, tending the flowerbeds.",
    "importance": 2,
    "from_location_id": "loc_village_square",
    "to_location_id": "loc_hobbs_cafe"
  },
  {
    "event_id": "ev_bg_rosa_2",
    "time": "12:07",
    "location_id": "loc_clinic",
    "agent_ids": [
      "agent_bg_rosa"
    ],
    "event_type": "movement",
    "truth_description": "Rosa is seen near Village Clinic, tending the flowerbeds.",
    "importance": 2,
    "from_location_id": "loc_hobbs_cafe",
    "to_location_id": "loc_clinic"
  },
  {
    "event_id": "ev_bg_gus_0",
    "time": "11:44",
    "location_id": "loc_hobbs_cafe",
    "agent_ids": [
      "agent_bg_gus"
    ],
    "event_type": "arrival",
    "truth_description": "Gus is seen near Hobbs Cafe, setting out the lunchtime papers.",
    "importance": 2,
    "to_location_id": "loc_hobbs_cafe"
  },
  {
    "event_id": "ev_bg_gus_1",
    "time": "12:04",
    "location_id": "loc_clinic",
    "agent_ids": [
      "agent_bg_gus"
    ],
    "event_type": "movement",
    "truth_description": "Gus is seen near Village Clinic, setting out the lunchtime papers.",
    "importance": 2,
    "from_location_id": "loc_hobbs_cafe",
    "to_location_id": "loc_clinic"
  },
  {
    "event_id": "ev_bg_effie_0",
    "time": "11:51",
    "location_id": "loc_clinic",
    "agent_ids": [
      "agent_bg_effie"
    ],
    "event_type": "arrival",
    "truth_description": "Effie is seen near Village Clinic, walking the dog past.",
    "importance": 2,
    "to_location_id": "loc_clinic"
  },
  {
    "event_id": "ev_bg_effie_1",
    "time": "12:06",
    "location_id": "loc_owen_house",
    "agent_ids": [
      "agent_bg_effie"
    ],
    "event_type": "movement",
    "truth_description": "Effie is seen near Owen Price's House & Yard, walking the dog past.",
    "importance": 2,
    "from_location_id": "loc_clinic",
    "to_location_id": "loc_owen_house"
  },
  {
    "event_id": "ev_bg_effie_2",
    "time": "12:21",
    "location_id": "loc_fountain",
    "agent_ids": [
      "agent_bg_effie"
    ],
    "event_type": "movement",
    "truth_description": "Effie is seen near Fountain, walking the dog past.",
    "importance": 2,
    "from_location_id": "loc_owen_house",
    "to_location_id": "loc_fountain"
  },
  {
    "event_id": "ev_bg_tam_0",
    "time": "11:58",
    "location_id": "loc_owen_house",
    "agent_ids": [
      "agent_bg_tam"
    ],
    "event_type": "arrival",
    "truth_description": "Tam is seen near Owen Price's House & Yard, finishing a post round.",
    "importance": 2,
    "to_location_id": "loc_owen_house"
  },
  {
    "event_id": "ev_bg_tam_1",
    "time": "12:13",
    "location_id": "loc_fountain",
    "agent_ids": [
      "agent_bg_tam"
    ],
    "event_type": "movement",
    "truth_description": "Tam is seen near Fountain, finishing a post round.",
    "importance": 2,
    "from_location_id": "loc_owen_house",
    "to_location_id": "loc_fountain"
  },
  {
    "event_id": "ev_bg_tam_2",
    "time": "12:28",
    "location_id": "loc_village_square",
    "agent_ids": [
      "agent_bg_tam"
    ],
    "event_type": "movement",
    "truth_description": "Tam is seen near Village Square, finishing a post round.",
    "importance": 2,
    "from_location_id": "loc_fountain",
    "to_location_id": "loc_village_square"
  },
  {
    "event_id": "ev_bg_dez_0",
    "time": "11:35",
    "location_id": "loc_fountain",
    "agent_ids": [
      "agent_bg_dez"
    ],
    "event_type": "arrival",
    "truth_description": "Dez is seen near Fountain, setting up a stall.",
    "importance": 2,
    "to_location_id": "loc_fountain"
  },
  {
    "event_id": "ev_bg_dez_1",
    "time": "11:50",
    "location_id": "loc_village_square",
    "agent_ids": [
      "agent_bg_dez"
    ],
    "event_type": "movement",
    "truth_description": "Dez is seen near Village Square, setting up a stall.",
    "importance": 2,
    "from_location_id": "loc_fountain",
    "to_location_id": "loc_village_square"
  },
  {
    "event_id": "ev_bg_dez_2",
    "time": "12:05",
    "location_id": "loc_hobbs_cafe",
    "agent_ids": [
      "agent_bg_dez"
    ],
    "event_type": "movement",
    "truth_description": "Dez is seen near Hobbs Cafe, setting up a stall.",
    "importance": 2,
    "from_location_id": "loc_village_square",
    "to_location_id": "loc_hobbs_cafe"
  }
]

--- interviews.json ---
[
  {
    "agent_id": "agent_priya",
    "default_answers": {
      "alibi": "I was in the stockroom all lunchtime. It was a big delivery \u2014 boxes everywhere. I barely came out.",
      "timeline": "Stockroom from eleven. Sorting, shelving. I didn't hear anything unusual.",
      "last_seen_victim": "Just before nine, briefly, when she arrived. She went straight to the back. I didn't disturb her.",
      "relationship": "Isabella gave me everything. This job, this life. I can't believe she's gone.",
      "evidence": "I don't know what that could mean.",
      "location": "I don't have much reason to go back there. That's Isabella's space."
    },
    "rules": [
      {
        "question_type": "alibi",
        "answer_text": "I was in the stockroom from eleven until Nadia came through. Sorting the week's delivery on my own \u2014 there was a mix-up with the invoice but I got it sorted. I heard Nadia come in and went through to see what was happening. That's when I understood.",
        "answer_type": "claim",
        "truthfulness": "false",
        "emotional_shift": "quiet_grief",
        "claims": [
          {
            "claim_id": "claim_priya_stockroom_all_morning",
            "summary": "Priya claims she was in the stockroom from 11:00 until Nadia arrived at 13:15.",
            "claim_type": "alibi",
            "time_reference": "12:45",
            "location_reference_id": "loc_bookshop",
            "truthfulness": "false"
          }
        ],
        "suggested_followups": [
          "Did you hear anything from the back room?",
          "When exactly did you sign the delivery invoice?"
        ]
      },
      {
        "question_type": "timeline",
        "time_from": "12:30",
        "time_to": "13:00",
        "answer_text": "That whole stretch I was in the stockroom. I put some music on quietly \u2014 through one earphone, so I could hear if Isabella needed me. She didn't call out. I didn't check on her. I should have.",
        "answer_type": "claim",
        "truthfulness": "false",
        "emotional_shift": "regretful",
        "claims": [
          {
            "claim_id": "claim_priya_stockroom_all_morning",
            "summary": "Priya claims she was in the stockroom from 11:00 until Nadia arrived at 13:15.",
            "claim_type": "alibi",
            "time_reference": "12:45",
            "location_reference_id": "loc_bookshop",
            "truthfulness": "false"
          }
        ]
      },
      {
        "question_type": "last_seen_victim",
        "answer_text": "She came in around half twelve \u2014 earlier than usual. She said good morning and went through to the back. She sounded like herself. Normal. Nothing in her voice that would have told me...anything.",
        "answer_type": "claim",
        "truthfulness": "false",
        "emotional_shift": "careful_sadness",
        "claims": [
          {
            "claim_id": "claim_priya_last_saw_isabella",
            "summary": "Priya claims she last saw Isabella when she arrived at 12:32 and heard nothing further.",
            "claim_type": "sighting",
            "time_reference": "12:32",
            "location_reference_id": "loc_bookshop",
            "truthfulness": "false"
          }
        ],
        "suggested_followups": [
          "Was anything said about documents or the solicitor?"
        ]
      },
      {
        "question_type": "relationship",
        "min_ask_count": 1,
        "answer_text": "I remember the day we met. I was just looking for a chance, and they took a leap of faith on me. I owe them so much for giving me a start when no one else would.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "reflective",
        "claims": [],
        "reveals_clue_ids": [],
        "reveals_memory_ids": [],
        "suggested_followups": []
      },
      {
        "question_type": "relationship",
        "answer_text": "She was demanding. Precise. If a shelf was crooked by half an inch, she'd see it from the doorway and make you feel six years old. But she also trusted me with more than anyone ever had. That's the worst of it. She could make you feel chosen and judged in the same breath.",
        "answer_type": "claim",
        "truthfulness": "mistaken",
        "emotional_shift": "controlled",
        "claims": [
          {
            "claim_id": "claim_priya_relationship",
            "summary": "Priya acknowledges tension with Isabella lately but frames it as ordinary workplace pressure.",
            "claim_type": "relationship",
            "truthfulness": "mistaken"
          }
        ],
        "suggested_followups": [
          "How did you two first meet?"
        ]
      },
      {
        "question_type": "evidence",
        "topic_clue_id": "clue_forged_document",
        "answer_text": "That document? Isabella signed it herself. I was there. She was... satisfied with the arrangement. Whoever says otherwise is wrong.",
        "answer_type": "denial",
        "truthfulness": "false",
        "emotional_shift": "brittle",
        "claims": [
          {
            "claim_id": "claim_priya_signature_genuine",
            "summary": "Priya insists Isabella signed the partnership document herself.",
            "claim_type": "statement",
            "truthfulness": "false"
          }
        ]
      },
      {
        "question_type": "evidence",
        "topic_clue_id": "clue_scarf_thread",
        "answer_text": "My scarf? I wore it this afternoon, it catches on everything in that stockroom \u2014 shelves, corners. A thread on a door latch means nothing. I go through that back door all the time for deliveries.",
        "answer_type": "denial",
        "truthfulness": "false",
        "emotional_shift": "sharp",
        "claims": [
          {
            "claim_id": "claim_priya_scarf_routine",
            "summary": "Priya claims the thread on the rear latch is from routine deliveries, not the murder.",
            "claim_type": "statement",
            "truthfulness": "false"
          }
        ]
      },
      {
        "question_type": "evidence",
        "topic_clue_id": "clue_invoice_discrepancy",
        "answer_text": "The driver left before I got the chance to sign. I went out to catch him and we did it at the van \u2014 he must have logged the time wrong on his copy. Happens all the time.",
        "answer_type": "denial",
        "truthfulness": "false",
        "emotional_shift": "defensive",
        "claims": [
          {
            "claim_id": "claim_priya_invoice_explanation",
            "summary": "Priya says the timestamp mismatch is the driver's error.",
            "claim_type": "statement",
            "truthfulness": "false"
          }
        ]
      },
      {
        "question_type": "location",
        "topic_location_id": "loc_bookshop_back",
        "answer_text": "I didn't go into the back room this afternoon \u2014 that was Isabella's private space and she hadn't called for me. I respected that boundary.",
        "answer_type": "denial",
        "truthfulness": "false",
        "emotional_shift": "composed",
        "claims": [
          {
            "claim_id": "claim_priya_not_in_back",
            "summary": "Priya denies entering the bookshop back room this afternoon.",
            "claim_type": "statement",
            "location_reference_id": "loc_bookshop_back",
            "truthfulness": "false"
          }
        ]
      },
      {
        "question_type": "evidence",
        "topic_clue_id": "clue_ben_argument_glimpse",
        "answer_text": "Ben was in the front for seconds. He caught a fragment and built a story around it. Isabella was upset with me, yes, but I never crossed that doorway. People hear one sharp sentence and imagine the rest.",
        "answer_type": "denial",
        "truthfulness": "false",
        "emotional_shift": "frayed"
      }
    ]
  },
  {
    "agent_id": "agent_owen",
    "default_answers": {
      "alibi": "My yard. All morning. Concrete to pour \u2014 doesn't wait for anyone.",
      "timeline": "Yard from eleven. Danny and Lee were with me until half past one.",
      "last_seen_victim": "Couple of days ago. She sent me another letter \u2014 her solicitor, third reminder. Like I hadn't heard the first two.",
      "relationship": "She lent me money and enjoyed reminding me of it. I'm not going to pretend it was friendly.",
      "evidence": "You'd need to be more specific.",
      "location": "I've got no business at that bookshop."
    },
    "rules": [
      {
        "question_type": "alibi",
        "answer_text": "I was pouring a concrete base in my yard from eleven this afternoon. Danny Marsh and Lee Tuck were with me. Concrete sets when it sets \u2014 you can't leave it. We finished around half past one. Ask them both.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "steady",
        "claims": [
          {
            "claim_id": "claim_owen_yard",
            "summary": "Owen was pouring concrete with two workers from 11:00 to approximately 13:30.",
            "claim_type": "alibi",
            "time_reference": "12:45",
            "location_reference_id": "loc_owen_house",
            "truthfulness": "true"
          }
        ],
        "reveals_clue_ids": [
          "clue_owen_yard_alibi"
        ]
      },
      {
        "question_type": "relationship",
        "min_ask_count": 1,
        "answer_text": "We first met over a job. The roof was leaking and I came to patch it. We shook hands on a fair price, and that was the start of a long working relationship. It's a shame how things turned out.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "reflective",
        "claims": [],
        "reveals_clue_ids": [],
        "reveals_memory_ids": [],
        "suggested_followups": []
      },
      {
        "question_type": "relationship",
        "answer_text": "She played the benefactor but she watched every penny. The loan wasn't a favour, it was leverage. I was behind on the repayment and she knew it. But I didn't kill her. I shouted at Marcus over money \u2014 that didn't end in murder either. Some of us solve things with words.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "defensive",
        "claims": [
          {
            "claim_id": "claim_owen_debt_admitted",
            "summary": "Owen admits he owed Isabella money and was behind on repayment.",
            "claim_type": "statement",
            "truthfulness": "true"
          }
        ],
        "suggested_followups": [
          "How did you two first meet?"
        ]
      },
      {
        "question_type": "evidence",
        "topic_clue_id": "clue_owen_debt_folder",
        "answer_text": "Yes, that's my file. She kept everything. Third reminder this week \u2014 she was going to hand it to Whittle & Cross today, she said. Nice timing for someone, isn't it. Just not me.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "grim",
        "reveals_clue_ids": [
          "clue_owen_yard_alibi"
        ]
      }
    ]
  },
  {
    "agent_id": "agent_elias",
    "default_answers": {
      "alibi": "The bench, as always. Six-forty until the fuss started.",
      "timeline": "I can tell you who went where all lunchtime from that bench. My memory's perfectly good.",
      "last_seen_victim": "Isabella, going into the bookshop around half twelve. Earlier than usual.",
      "relationship": "Fine woman. Ran a tight ship. She and I never had a cross word.",
      "evidence": "Ask me something specific.",
      "location": "I see the square better than anyone."
    },
    "rules": [
      {
        "question_type": "timeline",
        "time_from": "12:20",
        "time_to": "13:00",
        "answer_text": "Owen was prowling past the bookshop around twenty-five past twelve, waving a bit of paper. He stood at the window for a good ten seconds \u2014 I thought he was going to go in. He didn't. Then Isabella arrived at half past, went straight in. Nothing unusual until the carrying-on inside.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "animated",
        "claims": [
          {
            "claim_id": "claim_elias_owen_window",
            "summary": "Elias says Owen paused at the bookshop window at 12:25 before walking on.",
            "claim_type": "sighting",
            "time_reference": "12:25",
            "location_reference_id": "loc_bookshop",
            "truthfulness": "true"
          },
          {
            "claim_id": "claim_elias_isabella_arrival",
            "summary": "Elias confirms Isabella arrived at 12:32, earlier than her usual time.",
            "claim_type": "sighting",
            "time_reference": "12:32",
            "location_reference_id": "loc_bookshop",
            "truthfulness": "true"
          }
        ],
        "reveals_clue_ids": [
          "clue_owen_bookshop_pass",
          "clue_isabella_early_arrival"
        ],
        "suggested_followups": [
          "Did you see Priya leave or re-enter the bookshop?"
        ]
      },
      {
        "question_type": "alibi",
        "answer_text": "Bench, ten-forty. I saw Priya arrive at the bookshop at eleven on the dot \u2014 she's like a clock, that one. Then the postwoman. Then Owen making a face at the window. Then Isabella. Then nothing until Nadia ran out.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "precise",
        "claims": [
          {
            "claim_id": "claim_elias_morning_account",
            "summary": "Elias's full lunchtime account: Priya at 11:00, Ruth at 11:10, Owen at 12:25, Isabella at 12:32.",
            "claim_type": "sighting",
            "time_reference": "12:32",
            "location_reference_id": "loc_village_square",
            "truthfulness": "true"
          }
        ]
      }
    ]
  },
  {
    "agent_id": "agent_nadia",
    "default_answers": {
      "alibi": "At the clinic until I went to the bookshop just after one.",
      "timeline": "Clinic all lunchtime. I stop by the bookshop sometimes to borrow reference books.",
      "last_seen_victim": "Yesterday, briefly, at the clinic door. She looked distracted.",
      "relationship": "Neighbours for years. Professional respect.",
      "evidence": "I can tell you what I observed at the scene.",
      "location": "I know the back room well \u2014 Isabella lets me use her anatomy texts."
    },
    "rules": [
      {
        "question_type": "evidence",
        "topic_clue_id": "clue_staged_breakin",
        "answer_text": "The glass. Yes. I noticed that immediately. When a window is broken from outside, the force carries the shards inward \u2014 you get the largest pieces inside. Here it was the reverse: the big fragments were inside. Someone broke that pane from in the room and then tried to make it look like a break-in. Basic physics.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "measured",
        "reveals_clue_ids": [
          "clue_staged_breakin"
        ],
        "claims": [
          {
            "claim_id": "claim_nadia_glass_analysis",
            "summary": "Nadia observes the glass distribution proves the window was broken from the inside.",
            "claim_type": "statement",
            "truthfulness": "true"
          }
        ]
      },
      {
        "question_type": "evidence",
        "topic_clue_id": "clue_scarf_thread",
        "answer_text": "The green thread on the door latch \u2014 yes, I noticed it before I touched anything. Emerald green. Fine wool. I can't tell you whose it is, but it didn't come from outside.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "precise"
      },
      {
        "question_type": "timeline",
        "time_from": "12:30",
        "time_to": "13:15",
        "answer_text": "I was at the clinic until one-ten. I walked over to borrow a book. Priya said Isabella was in the back. I went through. I wish she'd been right.",
        "answer_type": "claim",
        "truthfulness": "true"
      }
    ]
  },
  {
    "agent_id": "agent_ruth",
    "default_answers": {
      "alibi": "My round. I do the same streets every morning. I can give you the times.",
      "timeline": "I'm methodical. I know exactly where I was and when.",
      "last_seen_victim": "I don't often speak to her. I just deliver the post.",
      "relationship": "Nothing beyond deliveries. She tips at Christmas.",
      "evidence": "Tell me what you're looking at.",
      "location": "I know every house and door on this round."
    },
    "rules": [
      {
        "question_type": "timeline",
        "time_from": "11:00",
        "time_to": "12:00",
        "answer_text": "I delivered to the bookshop at eleven-ten. Sealed letter from Whittle & Cross \u2014 I remember because it's a solicitor's franking, you notice those. Pushed it through the slot and moved on. Nothing unusual.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "factual",
        "claims": [
          {
            "claim_id": "claim_ruth_letter_time",
            "summary": "Ruth delivered the Whittle & Cross letter at 11:10, sealed.",
            "claim_type": "statement",
            "time_reference": "11:10",
            "location_reference_id": "loc_bookshop",
            "truthfulness": "true"
          }
        ],
        "reveals_clue_ids": [
          "clue_ruth_post_sighting"
        ]
      },
      {
        "question_type": "timeline",
        "time_from": "12:35",
        "time_to": "13:00",
        "answer_text": "I was back along the rear alley finishing up at about twenty to nine. I heard something from the back of the bookshop \u2014 a bang, like a chair going over. I thought nothing of it. Then at about ten-to, I noticed the back window was broken and there was a bit of thread on the door latch. Green. I only thought to mention it when the fuss started.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "troubled",
        "claims": [
          {
            "claim_id": "claim_ruth_crash",
            "summary": "Ruth heard a crash at about 12:40 from the bookshop back room, and later noticed a broken window and green thread on the rear latch.",
            "claim_type": "sighting",
            "time_reference": "12:40",
            "location_reference_id": "loc_rear_alley",
            "truthfulness": "true"
          }
        ],
        "reveals_clue_ids": [
          "clue_crash_sound",
          "clue_scarf_thread"
        ],
        "suggested_followups": [
          "What did the thread look like?",
          "Was the rear door open or shut?"
        ]
      }
    ]
  },
  {
    "agent_id": "agent_ben",
    "default_answers": {
      "alibi": "My round, as per usual. Van by the square from half eleven.",
      "timeline": "Square, deliveries, van. Same as every day.",
      "last_seen_victim": "Last proper conversation? Yesterday, when she signed for a parcel.",
      "relationship": "She was all right to me. Bit cool, but fair.",
      "evidence": "Couldn't help you there.",
      "location": "I go everywhere."
    },
    "rules": [
      {
        "question_type": "timeline",
        "time_from": "12:35",
        "time_to": "13:00",
        "answer_text": "It wasn't just the alley bit. A couple of minutes before the bang \u2014 call it twenty-two to or thereabouts \u2014 I stepped into the front shop with a parcel for Hobbs that had landed in the wrong stack. Through the counter door I saw Priya in the back room, right up near Isabella's desk, and Isabella said, proper sharp, 'You do not get to decide this for me.' I left the parcel and got out of there. Then around ten-to I was in the alley for an empty crate and noticed the broken pane.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "shocked",
        "claims": [
          {
            "claim_id": "claim_ben_argument_glimpse",
            "summary": "Ben saw Priya near Isabella's desk in the back room at about 12:38 and heard Isabella snap, 'You do not get to decide this for me.'",
            "claim_type": "sighting",
            "time_reference": "12:38",
            "location_reference_id": "loc_bookshop_back",
            "truthfulness": "true"
          },
          {
            "claim_id": "claim_ben_window",
            "summary": "Ben noticed the broken bookshop back window at about 12:50 in the rear alley.",
            "claim_type": "sighting",
            "time_reference": "12:50",
            "location_reference_id": "loc_rear_alley",
            "truthfulness": "true"
          }
        ],
        "reveals_clue_ids": [
          "clue_ben_argument_glimpse",
          "clue_ben_broken_window"
        ],
        "suggested_followups": [
          "Which side did you see most of the glass on?"
        ]
      },
      {
        "question_type": "relationship",
        "min_ask_count": 1,
        "answer_text": "Priya and me? We got into the habit of taking coffee when my round crossed hers. She'd been wound tight all week, talking like one conversation was going to decide the rest of her life. I thought she meant asking Isabella for more responsibility. Maybe I was kidding myself.",
        "answer_type": "claim",
        "truthfulness": "true",
        "emotional_shift": "guarded",
        "claims": [],
        "reveals_memory_ids": [
          "mem_ben_priya_restless"
        ]
      },
      {
        "question_type": "evidence",
        "topic_clue_id": "clue_staged_breakin",
        "answer_text": "The glass? Yeah, now that you ask \u2014 there was some in the alley, sure, but the biggest bit was still inside on the sill and there were more jagged pieces in the room than there ought to have been. I remember thinking: if someone smashed their way in, why's the room keeping the worst of it?",
        "answer_type": "claim",
        "truthfulness": "true",
        "reveals_clue_ids": [
          "clue_staged_breakin"
        ]
      }
    ]
  }
]

--- locations.json ---
[
  {
    "location_id": "loc_village_square",
    "name": "Village Square",
    "description": "The open heart of the village, with a stone fountain, benches, and a view of the cafe and bookshop fronts.",
    "connected_location_ids": [
      "loc_hobbs_cafe",
      "loc_bookshop",
      "loc_clinic",
      "loc_rear_alley",
      "loc_owen_house"
    ],
    "visibility_type": "public",
    "camera_coverage": false
  },
  {
    "location_id": "loc_bookshop",
    "name": "Reed & Bell Bookshop",
    "description": "Isabella Reed's bookshop. Front area with shelves and a counter; a door behind the counter leads to the back room.",
    "connected_location_ids": [
      "loc_village_square",
      "loc_bookshop_back",
      "loc_rear_alley"
    ],
    "visibility_type": "public"
  },
  {
    "location_id": "loc_bookshop_back",
    "name": "Bookshop Back Room",
    "description": "A cramped back office and stockroom behind the bookshop counter. Isabella's desk, the safe, shelves of stock. A rear door opens onto the alley.",
    "connected_location_ids": [
      "loc_bookshop",
      "loc_rear_alley"
    ],
    "access_rules": [
      "staff",
      "keyholder"
    ],
    "visibility_type": "private",
    "audible_from_location_ids": [
      "loc_bookshop",
      "loc_rear_alley"
    ],
    "murder_suitable": true
  },
  {
    "location_id": "loc_rear_alley",
    "name": "Rear Alley",
    "description": "A narrow service alley running behind the bookshop. Bins, crates, and the bookshop's rear door.",
    "connected_location_ids": [
      "loc_village_square",
      "loc_bookshop_back",
      "loc_bookshop"
    ],
    "visibility_type": "public",
    "audible_from_location_ids": [
      "loc_bookshop_back"
    ]
  },
  {
    "location_id": "loc_hobbs_cafe",
    "name": "Hobbs Cafe",
    "description": "The village cafe. Counter, tables, and the till at the front; kitchen behind.",
    "connected_location_ids": [
      "loc_village_square"
    ],
    "visibility_type": "public",
    "audible_from_location_ids": [
      "loc_village_square"
    ],
    "camera_coverage": false
  },
  {
    "location_id": "loc_clinic",
    "name": "Village Clinic",
    "description": "A small clinic on the square where Nadia Cole works the early shift.",
    "connected_location_ids": [
      "loc_village_square"
    ],
    "visibility_type": "public"
  },
  {
    "location_id": "loc_owen_house",
    "name": "Owen Price's House & Yard",
    "description": "Owen's house and builder's timber yard on the far side of the square.",
    "connected_location_ids": [
      "loc_village_square"
    ],
    "access_rules": [
      "owner"
    ],
    "visibility_type": "public"
  },
  {
    "location_id": "loc_priya_flat",
    "name": "Priya's Flat",
    "description": "Priya's rented flat two streets behind the square. Small and tidy.",
    "connected_location_ids": [
      "loc_village_square"
    ],
    "access_rules": [
      "owner"
    ],
    "visibility_type": "private"
  },
  {
    "location_id": "loc_fountain",
    "name": "Fountain",
    "description": "The stone fountain in the middle of the village square.",
    "connected_location_ids": [
      "loc_village_square"
    ],
    "visibility_type": "public"
  }
]

--- memories.json ---
[
  {
    "memory_id": "mem_priya_forgery",
    "owner_agent_id": "agent_priya",
    "known_by_agent_ids": [
      "agent_priya"
    ],
    "memory_type": "private_secret",
    "case_function": "killer_motive",
    "truth_status": "true",
    "summary": "Priya forged Isabella's signature on the partnership transfer six weeks ago, after Marcus told her the expansion was hers. She did not want to wait for Isabella to agree \u2014 she feared Isabella would contest it.",
    "emotional_weight": 10,
    "shareability": "will_hide",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_forged_document"
    ],
    "linked_agent_ids": [
      "agent_isabella"
    ]
  },
  {
    "memory_id": "mem_priya_letter_read",
    "owner_agent_id": "agent_priya",
    "known_by_agent_ids": [
      "agent_priya"
    ],
    "memory_type": "private_secret",
    "case_function": "killer_trigger",
    "truth_status": "true",
    "summary": "Priya read the solicitor's letter at 12:00 and knew immediately it was about the forged signature. She had until 13:30 before everything unravelled.",
    "emotional_weight": 10,
    "shareability": "will_hide",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_solicitor_letter",
      "clue_ruth_post_sighting"
    ]
  },
  {
    "memory_id": "mem_priya_cover_story",
    "owner_agent_id": "agent_priya",
    "known_by_agent_ids": [
      "agent_priya"
    ],
    "memory_type": "cover_story",
    "case_function": "false_alibi_reason",
    "truth_status": "false",
    "summary": "Priya's prepared story: she was in the stockroom sorting deliveries all lunchtime and only came through when Nadia arrived. She says she heard nothing unusual.",
    "emotional_weight": 9,
    "shareability": "will_lie",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_priya_stockroom_claim"
    ]
  },
  {
    "memory_id": "mem_priya_rear_door",
    "owner_agent_id": "agent_priya",
    "known_by_agent_ids": [
      "agent_priya"
    ],
    "memory_type": "private_secret",
    "case_function": "object_trail",
    "truth_status": "true",
    "summary": "Priya knows her scarf snagged on the rear door latch when she fled through the alley. She did not notice the thread was left behind until she checked the scarf in the stockroom.",
    "emotional_weight": 9,
    "shareability": "will_hide",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_scarf_thread",
      "clue_priya_scarf_missing_thread"
    ],
    "linked_location_ids": [
      "loc_bookshop_back"
    ]
  },
  {
    "memory_id": "mem_isabella_solicitor",
    "owner_agent_id": "agent_isabella",
    "known_by_agent_ids": [
      "agent_isabella"
    ],
    "memory_type": "private_secret",
    "case_function": "victim_trigger",
    "truth_status": "true",
    "summary": "Isabella noticed the reversed 'R' signature two days ago when reviewing the expansion paperwork. She booked Whittle & Cross immediately and told no one.",
    "emotional_weight": 8,
    "shareability": "will_hide",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_solicitor_letter",
      "clue_forged_document"
    ]
  },
  {
    "memory_id": "mem_isabella_second_chance",
    "owner_agent_id": "agent_isabella",
    "known_by_agent_ids": [
      "agent_isabella"
    ],
    "memory_type": "private_secret",
    "case_function": "victim_emotional_anchor",
    "truth_status": "true",
    "summary": "Isabella decided she would confront Priya privately before the solicitor meeting and give her one chance to confess. She was angry, but she still hoped to contain the damage without destroying Priya outright.",
    "emotional_weight": 8,
    "shareability": "will_hide",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_solicitor_letter"
    ],
    "linked_agent_ids": [
      "agent_priya"
    ]
  },
  {
    "memory_id": "mem_owen_debt_letter",
    "owner_agent_id": "agent_owen",
    "known_by_agent_ids": [
      "agent_owen",
      "agent_isabella"
    ],
    "memory_type": "private_secret",
    "case_function": "red_herring_motive",
    "truth_status": "true",
    "summary": "Owen received Isabella's final demand letter this afternoon. Repay by the end of the week or she hands it to her solicitor. He is furious but has no real plan.",
    "emotional_weight": 8,
    "shareability": "will_deflect",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_owen_debt_folder",
      "clue_owen_bookshop_pass"
    ]
  },
  {
    "memory_id": "mem_owen_anchor",
    "owner_agent_id": "agent_owen",
    "known_by_agent_ids": [
      "agent_owen"
    ],
    "memory_type": "observed",
    "case_function": "innocence_anchor",
    "truth_status": "true",
    "summary": "Owen was pouring a concrete pad in his yard from 11:00 with two workers \u2014 Danny Marsh and Lee Tuck \u2014 present until gone half past one.",
    "emotional_weight": 4,
    "shareability": "will_share_if_asked",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_owen_yard_alibi"
    ]
  },
  {
    "memory_id": "mem_ruth_delivery",
    "owner_agent_id": "agent_ruth",
    "known_by_agent_ids": [
      "agent_ruth"
    ],
    "memory_type": "witness_fragment",
    "case_function": "clue_support",
    "truth_status": "true",
    "summary": "Ruth delivered the Whittle & Cross letter sealed at 11:10. She is certain of the time \u2014 the bookshop is third on her route.",
    "emotional_weight": 4,
    "confidence": 0.9,
    "shareability": "will_share_if_asked",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_ruth_post_sighting"
    ],
    "linked_event_ids": [
      "ev_1110_solicitor_letter_delivered"
    ]
  },
  {
    "memory_id": "mem_ruth_crash",
    "owner_agent_id": "agent_ruth",
    "known_by_agent_ids": [
      "agent_ruth"
    ],
    "memory_type": "witness_fragment",
    "case_function": "clue_support",
    "truth_status": "true",
    "summary": "Ruth heard a loud crash from the bookshop back room at around 12:40 and noticed the green thread on the rear door latch at 12:50. She did not think to connect them at the time.",
    "emotional_weight": 6,
    "confidence": 0.8,
    "shareability": "will_share_if_asked",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_crash_sound",
      "clue_scarf_thread"
    ]
  },
  {
    "memory_id": "mem_ben_broken_window",
    "owner_agent_id": "agent_ben",
    "known_by_agent_ids": [
      "agent_ben"
    ],
    "memory_type": "witness_fragment",
    "case_function": "clue_support",
    "truth_status": "true",
    "summary": "Ben passed the rear alley at about 12:50 and noticed the broken pane in the bookshop back window. He mentioned it over coffee at Hobbs.",
    "emotional_weight": 4,
    "confidence": 0.8,
    "shareability": "will_share",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_ben_broken_window"
    ]
  },
  {
    "memory_id": "mem_ben_argument_glimpse",
    "owner_agent_id": "agent_ben",
    "known_by_agent_ids": [
      "agent_ben"
    ],
    "memory_type": "witness_fragment",
    "case_function": "clue_support",
    "truth_status": "true",
    "summary": "Ben stepped into the shop at about 12:38 with a mis-sorted parcel and saw Priya standing close to Isabella's desk in the back room. Isabella had one hand near the telephone and snapped, 'You do not get to decide this for me.' He left before either woman noticed him.",
    "emotional_weight": 7,
    "confidence": 0.85,
    "shareability": "will_share",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_ben_argument_glimpse"
    ],
    "linked_event_ids": [
      "ev_1238_ben_argument_glimpse"
    ]
  },
  {
    "memory_id": "mem_ben_priya_restless",
    "owner_agent_id": "agent_ben",
    "known_by_agent_ids": [
      "agent_ben",
      "agent_priya"
    ],
    "memory_type": "private_secret",
    "case_function": "character_texture",
    "truth_status": "true",
    "summary": "Over coffees after his round, Ben had started seeing Priya quietly. All week she had been wound tight, saying that by Friday night everything would either finally be hers or be over. Ben assumed she meant a promotion or a move away with him. He never guessed she meant the forged transfer.",
    "emotional_weight": 7,
    "shareability": "will_share_if_asked",
    "discoverable_by_player": true,
    "linked_agent_ids": [
      "agent_priya"
    ]
  },
  {
    "memory_id": "mem_elias_early_arrival",
    "owner_agent_id": "agent_elias",
    "known_by_agent_ids": [
      "agent_elias"
    ],
    "memory_type": "witness_fragment",
    "case_function": "clue_support",
    "truth_status": "true",
    "summary": "Elias noticed Isabella arrive at 12:32 \u2014 nearly 30 minutes before her usual time. She looked purposeful rather than panicked.",
    "emotional_weight": 5,
    "confidence": 0.8,
    "shareability": "will_share",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_isabella_early_arrival"
    ]
  },
  {
    "memory_id": "mem_elias_owen_pass",
    "owner_agent_id": "agent_elias",
    "known_by_agent_ids": [
      "agent_elias"
    ],
    "memory_type": "witness_fragment",
    "case_function": "red_herring_motive",
    "truth_status": "true",
    "summary": "Elias noticed Owen glaring through the bookshop window at 12:25, waving a piece of paper. He's convinced Owen did it \u2014 'the man's always two steps from the edge'.",
    "emotional_weight": 5,
    "confidence": 0.75,
    "shareability": "will_share",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_owen_bookshop_pass"
    ]
  },
  {
    "memory_id": "mem_nadia_discovery",
    "owner_agent_id": "agent_nadia",
    "known_by_agent_ids": [
      "agent_nadia"
    ],
    "memory_type": "observed",
    "case_function": "clue_support",
    "truth_status": "true",
    "summary": "Nadia found Isabella face-down behind the desk at 13:15. The rear door was ajar. A green thread was visible on the latch. The window was broken inward \u2014 Nadia's medical training tells her the glass distribution is wrong for an external break.",
    "emotional_weight": 10,
    "shareability": "will_share",
    "discoverable_by_player": true,
    "linked_clue_ids": [
      "clue_staged_breakin",
      "clue_scarf_thread"
    ],
    "linked_location_ids": [
      "loc_bookshop_back"
    ]
  }
]

--- objects.json ---
[
  {
    "object_id": "obj_letter_opener",
    "name": "Victorian letter opener",
    "description": "A heavy brass letter opener with a decorated handle, normally kept upright in a pen pot on Isabella's desk.",
    "is_weapon": true,
    "normal_location_id": "loc_bookshop_back",
    "final_location_id": "loc_bookshop_back",
    "access_rules": [
      "staff"
    ],
    "touched_by_agent_ids": [
      "agent_priya",
      "agent_isabella"
    ],
    "last_seen_time": "12:20",
    "hidden_state": "wiped_and_replaced_in_pot",
    "clue_relevance": "weapon"
  },
  {
    "object_id": "obj_forged_document",
    "name": "Forged partnership transfer",
    "description": "A typewritten document transferring the bookshop expansion rights to Priya Shah, bearing a signature in Isabella's name \u2014 the pen strokes slightly too regular, the 'R' in Reed looping the wrong way.",
    "normal_location_id": "loc_bookshop_back",
    "final_location_id": "loc_bookshop_back",
    "access_rules": [
      "owner"
    ],
    "touched_by_agent_ids": [
      "agent_priya",
      "agent_isabella"
    ],
    "last_seen_time": "12:35",
    "hidden_state": "locked_in_safe_behind_loose_panel",
    "clue_relevance": "motive"
  },
  {
    "object_id": "obj_broken_window_glass",
    "name": "Broken window pane (staged)",
    "description": "A small pane in the bookshop back room window, broken from the inside \u2014 a scatter of glass lies outside in the alley, but the larger shards and frame splinters remain inside the room.",
    "normal_location_id": "loc_bookshop_back",
    "final_location_id": "loc_rear_alley",
    "access_rules": [],
    "touched_by_agent_ids": [
      "agent_priya"
    ],
    "last_seen_time": "12:48",
    "hidden_state": "glass_shards_on_both_sides_but_majority_inside",
    "clue_relevance": "staged_scene"
  },
  {
    "object_id": "obj_priya_scarf",
    "name": "Priya's green scarf",
    "description": "Priya's emerald wool scarf, often worn on cool mornings. A single green thread was caught on the latch of the bookshop back door.",
    "normal_location_id": "loc_priya_flat",
    "final_location_id": "loc_bookshop",
    "access_rules": [],
    "touched_by_agent_ids": [
      "agent_priya"
    ],
    "last_seen_time": "12:48",
    "hidden_state": "thread_caught_on_door_latch",
    "clue_relevance": "opportunity"
  },
  {
    "object_id": "obj_solicitor_letter",
    "name": "Solicitor's letter",
    "description": "A letter on Isabella's desk from the firm Whittle & Cross confirming their meeting at 13:30 to discuss 'irregularities in the bookshop partnership documents'.",
    "normal_location_id": "loc_bookshop_back",
    "final_location_id": "loc_bookshop_back",
    "access_rules": [
      "owner"
    ],
    "touched_by_agent_ids": [
      "agent_priya",
      "agent_isabella"
    ],
    "last_seen_time": "12:35",
    "clue_relevance": "motive"
  },
  {
    "object_id": "obj_owen_debt_folder",
    "name": "Owen's debt correspondence",
    "description": "A manila folder in Isabella's desk drawer: letters from Owen Price regarding a loan Isabella had called in. Owen was due to repay or face repossession of his yard.",
    "normal_location_id": "loc_bookshop_back",
    "final_location_id": "loc_bookshop_back",
    "access_rules": [
      "owner"
    ],
    "touched_by_agent_ids": [
      "agent_isabella"
    ],
    "last_seen_time": "12:35",
    "clue_relevance": "red_herring_motive"
  },
  {
    "object_id": "obj_stockroom_invoice",
    "name": "Signed delivery invoice",
    "description": "A delivery receipt on the stockroom table signed by Priya at 12:10 \u2014 but the driver's copy records the delivery as complete by 12:05, leaving Priya's time unaccounted from 12:10 to 13:00.",
    "normal_location_id": "loc_bookshop",
    "final_location_id": "loc_bookshop",
    "access_rules": [],
    "touched_by_agent_ids": [
      "agent_priya"
    ],
    "last_seen_time": "12:10",
    "clue_relevance": "opportunity"
  }
]

--- solution.json ---
{
  "killer_id": "agent_priya",
  "motive": {
    "canonical": "Priya forged Isabella's signature on the partnership transfer documents and killed Isabella to prevent her exposing the forgery to the solicitor.",
    "concept_groups": [
      [
        "forge",
        "forged",
        "fake",
        "faked",
        "signature",
        "document",
        "signed",
        "falsified"
      ],
      [
        "partnership",
        "transfer",
        "expansion",
        "bookshop",
        "inheritance"
      ],
      [
        "solicitor",
        "expose",
        "reveal",
        "discover",
        "found out",
        "letter",
        "whittle"
      ]
    ],
    "min_groups": 2
  },
  "method": {
    "canonical": "Blunt force with the brass letter opener on Isabella's desk, in the bookshop back room.",
    "concept_groups": [
      [
        "blunt",
        "struck",
        "strike",
        "hit",
        "bludgeon",
        "blow",
        "beat",
        "impact"
      ],
      [
        "letter opener",
        "opener",
        "brass",
        "desk"
      ]
    ],
    "min_groups": 2
  },
  "opportunity": {
    "canonical": "Priya was with Isabella in the back room during the murder window. Ben saw them arguing by Isabella's desk, the invoice gap breaks Priya's stockroom alibi, and the green thread proves she used the rear exit.",
    "concept_groups": [
      [
        "ben",
        "argument",
        "arguing",
        "desk",
        "telephone",
        "together"
      ],
      [
        "stockroom",
        "no alibi",
        "unaccounted",
        "gap",
        "invoice"
      ],
      [
        "scarf",
        "thread",
        "green",
        "latch",
        "rear door"
      ],
      [
        "back room",
        "office",
        "behind counter"
      ]
    ],
    "min_groups": 1
  },
  "key_clue_ids": [
    "clue_forged_document",
    "clue_solicitor_letter",
    "clue_ben_argument_glimpse",
    "clue_scarf_thread",
    "clue_invoice_discrepancy",
    "clue_staged_breakin",
    "clue_letter_opener_wiped"
  ],
  "explanation": "Correct. Priya Shah killed Isabella Reed. Priya had forged Isabella's signature on the bookshop partnership transfer after Marcus Bell named her his successor \u2014 she didn't trust Isabella to agree. When the solicitor's letter arrived at 11:10 confirming Isabella had discovered the forgery and booked a 13:30 appointment, Priya read it first and understood her window was closing. Ben's glimpse through the counter door places Priya and Isabella together in the back room at 12:38, mid-argument, with Isabella by the telephone. Minutes later, when Isabella reached for that telephone, Priya seized the Victorian letter opener and struck her. She staged a break-in by smashing the window pane from inside \u2014 but the glass fell the wrong way. Her scarf snagged on the rear latch as she fled through the alley, and the invoice timestamp proves her stockroom alibi is false."
}
