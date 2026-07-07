"""Core data models for the murder mystery engine.

These mirror the schemas in spec 11 (data schemas). The case file and
everything linked from it is immutable once loaded ("locked truth");
player-session state (notes, discovered clues, interview transcripts)
lives in session.py and is mutable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

Visibility = Literal[
    "public",          # player sees directly in rewind
    "public_partial",  # player sees an ambiguous version
    "private",         # hidden unless discovered; may show a locked placeholder
    "hidden",          # never shown directly (e.g. the murder itself)
]

TruthStatus = Literal["true", "false", "mistaken", "rumour", "unknown"]

MemoryType = Literal[
    "private_secret",
    "shared_secret",
    "rumour",
    "witness_fragment",
    "false_belief",
    "deliberate_lie",
    "innocent_secret",
    "observed",
    "cover_story",
]

Shareability = Literal[
    "will_share",
    "will_share_if_asked",
    "will_hide",
    "will_lie",
    "will_deflect",
]

ClueStrength = Literal["weak", "medium", "strong", "critical"]

ClaimStatus = Literal["claimed", "disputed", "reframed", "confirmed", "resolved"]

ChallengeOutcome = Literal[
    "deny",                    # rejects the evidence; claim unchanged
    "deflect",                 # redirects; claim disputed but not admitted
    "reframe",                 # offers an innocent explanation
    "partial_admission",      # concedes part of the hidden truth
    "reveal_innocent_secret",  # red herring explains suspicious behaviour
    "contradiction_locked",   # claim is provably false; recorded as such
]

NoteType = Literal[
    "manual",
    "event",
    "evidence",
    "interview",
    "contradiction",
    "theory",
    "question",
]

SuspicionLevel = Literal[
    "unknown",
    "person_of_interest",
    "suspect",
    "prime_suspect",
    "likely_innocent",
    "cleared",
]

QuestionType = Literal[
    "alibi",            # where were you during the murder window?
    "timeline",         # what were you doing at/around <time>?
    "last_seen_victim", # when did you last see the victim?
    "relationship",     # what was your relationship with the victim?
    "evidence",         # what do you know about <clue/object>?
    "location",         # why were you at / what do you know about <location>?
]

VisualEventType = Literal[
    "agent_move",
    "agent_present",
    "object_marker",
    "sound_marker",
    "body_discovery",
    "unknown_figure",
    "hidden_activity",
    "conversation_marker",
    "clue_marker",
]

QuestionIntentType = Literal[
    "alibi",
    "timeline",
    "last_seen_victim",
    "relationship",
    "evidence",
    "location",
    "motive",
    "object",
    "contradiction",
    "explicit_challenge",
    "fallback_unknown"
]


# ---------------------------------------------------------------------------
# Locked case truth
# ---------------------------------------------------------------------------

class MapPosition(BaseModel):
    """A point on the map image, in map-image pixel coordinates."""

    x: float
    y: float


class MapBounds(BaseModel):
    """A rectangle on the map image, in map-image pixel coordinates."""

    x: float
    y: float
    width: float
    height: float


class Relationship(BaseModel):
    target_agent_id: str
    relationship_type: str
    affinity: float = 0.0
    trust: float = 0.0
    tension: float = 0.0


class PortraitState(BaseModel):
    """Optional per-expression portrait asset paths (cosmetic only).

    Any state may be absent; the frontend falls back through
    cracking > defensive > calm > the legacy emoji `portrait`.
    """

    calm: Optional[str] = None
    defensive: Optional[str] = None
    cracking: Optional[str] = None


class Agent(BaseModel):
    agent_id: str
    full_name: str
    age: int
    occupation: str
    traits: list[str] = []
    portrait: Optional[str] = None  # emoji or asset path for MVP
    portrait_art: Optional[PortraitState] = None
    home_location_id: Optional[str] = None
    work_location_id: Optional[str] = None
    routine_summary: str = ""
    # Authored speech mannerisms fed into rewrite prompts (spec 15 Phase B),
    # e.g. "clips his sentences when defensive". Purely descriptive flavour.
    voice_card: Optional[str] = None
    relationships: list[Relationship] = []
    observation_skill: float = 0.5
    memory_reliability: float = 0.5
    honesty_baseline: float = 0.5
    gossip_tendency: float = 0.5
    conflict_avoidance: float = 0.5
    is_victim: bool = False
    # Ambient character: appears and moves on the map for flavor, but is not
    # interviewable, accusable, or listed as a suspect.
    is_background: bool = False
    # Visual-only avatar metadata; the mystery character remains canonical.
    sprite_id: Optional[str] = None
    sprite_asset: Optional[str] = None


class Location(BaseModel):
    location_id: str
    name: str
    description: str = ""
    # Optional establishing-shot asset path (cosmetic only); absent means the
    # client falls back to a map crop or skips the transition.
    illustration: Optional[str] = None
    connected_location_ids: list[str] = []
    access_rules: list[str] = []
    visibility_type: Literal["public", "private"] = "public"
    audible_from_location_ids: list[str] = []
    camera_coverage: bool = False
    murder_suitable: bool = False
    # Visual-only placement on the map image; never drives case logic.
    map_position: Optional[MapPosition] = None
    map_bounds: Optional[MapBounds] = None
    visual_layer: Optional[Literal["exterior", "interior"]] = None
    location_type: Optional[Literal["public", "private", "home", "work", "crime_scene", "discovery", "neutral"]] = None


class GameObject(BaseModel):
    object_id: str
    name: str
    description: str = ""
    normal_location_id: Optional[str] = None
    final_location_id: Optional[str] = None
    access_rules: list[str] = []
    touched_by_agent_ids: list[str] = []
    last_seen_time: Optional[str] = None
    hidden_state: Optional[str] = None
    clue_relevance: Optional[str] = None


class SeededMemory(BaseModel):
    memory_id: str
    owner_agent_id: str
    known_by_agent_ids: list[str] = []
    memory_type: MemoryType
    case_function: str
    truth_status: TruthStatus = "true"
    summary: str
    emotional_weight: int = 5
    confidence: float = 1.0
    shareability: Shareability = "will_share_if_asked"
    discoverable_by_player: bool = True
    linked_clue_ids: list[str] = []
    linked_agent_ids: list[str] = []
    linked_location_ids: list[str] = []


class Event(BaseModel):
    event_id: str
    time: str  # "HH:MM"
    location_id: str
    agent_ids: list[str] = []
    event_type: str
    truth_description: str
    player_description: Optional[str] = None  # shown for public_partial
    visibility: Visibility = "public"
    visible_to_agent_ids: list[str] = []
    audible_to_agent_ids: list[str] = []
    object_ids: list[str] = []
    importance: int = 5
    linked_clue_ids: list[str] = []
    # Visual projection hints for the map replay layer (optional).
    visual_event_type: Optional[VisualEventType] = None
    from_location_id: Optional[str] = None
    to_location_id: Optional[str] = None


class Discoverability(BaseModel):
    method: Literal["observation", "interview", "inspect", "challenge", "initial"]
    # For interview: agent + question type that reveals it.
    agent_id: Optional[str] = None
    question_type: Optional[QuestionType] = None
    # For inspect: location or object that yields it.
    location_id: Optional[str] = None
    object_id: Optional[str] = None
    required_prior_clue_ids: list[str] = []
    
    # Hotspot fields for map inspection or body examination
    # Note: For body examination ("reveal_on": ["examine_body"]), you can author 
    # specific coordinates here. If omitted, the game falls back to deterministic 
    # random placement over the victim's portrait.
    x: Optional[float] = None          # Percentage 0-100 across the image
    y: Optional[float] = None          # Percentage 0-100 down the image
    radius: Optional[float] = 8.0      # Radius percentage
    discovery_text: Optional[str] = None
    
    # Authoring guidance: use `["examine_body"]` for clues found via victim body examination.
    reveal_on: list[str] = Field(default_factory=list)


class Clue(BaseModel):
    clue_id: str
    title: str
    clue_type: str
    description: str
    strength: ClueStrength = "medium"
    reliability: float = 0.7
    ambiguity: Literal["low", "medium", "high"] = "medium"
    discoverability: Discoverability
    supports_conclusion_ids: list[str] = []
    linked_event_ids: list[str] = []
    linked_agent_ids: list[str] = []
    linked_location_ids: list[str] = []
    linked_object_ids: list[str] = []


class Conclusion(BaseModel):
    conclusion_id: str
    type: str  # motive / opportunity / means / method / false_alibi / red_herring...
    summary: str
    target_agent_id: Optional[str] = None
    required_for_solution: bool = False
    supported_by_clue_ids: list[str] = []


class CaseFile(BaseModel):
    case_id: str
    case_type: str
    title: str
    status: Literal["locked"] = "locked"
    victim_id: str
    killer_id: str
    motive_summary: str
    method: str
    weapon_id: Optional[str] = None
    murder_location_id: str
    time_of_death: str
    discovery_time: str
    discovered_by: str
    discovery_location_id: str
    sim_start_time: str = "06:00"
    murder_window: tuple[str, str] = ("07:45", "08:00")
    overview_text: str = ""
    # Optional flavour text for the body-discovery intro scene; empty means
    # the client falls back to overview_text.
    scene_description: str = ""
    
    # Authoring guidance: use `cause_of_death_observed` for player-facing 
    # body examination text. Do not rely on `method` for narrative output unless 
    # it contains only a generic category (e.g. poisoning, blunt_force).
    cause_of_death_observed: Optional[str] = None


# ---------------------------------------------------------------------------
# Interview data (hand-authored grounded answers for the structured engine)
# ---------------------------------------------------------------------------

class AnswerClaim(BaseModel):
    claim_id: str
    summary: str
    claim_type: str = "statement"  # alibi / sighting / relationship / statement
    time_reference: Optional[str] = None
    location_reference_id: Optional[str] = None
    truthfulness: TruthStatus = "true"


class AnswerRule(BaseModel):
    """One grounded answer an agent can give to a structured question."""

    question_type: QuestionType
    # Optional matchers narrowing when this rule applies:
    time_from: Optional[str] = None
    time_to: Optional[str] = None
    topic_clue_id: Optional[str] = None
    topic_object_id: Optional[str] = None
    topic_location_id: Optional[str] = None
    # Depth gating: the rule only matches once the player has already asked
    # this question type at least this many times (0 = always). Rules are
    # first-match, so depth rules must precede the base rule in the pack.
    min_ask_count: int = 0
    answer_text: str
    answer_type: Literal["claim", "denial", "uncertain", "refusal", "gossip"] = "claim"
    truthfulness: TruthStatus = "true"
    emotional_shift: Optional[str] = None
    claims: list[AnswerClaim] = []
    reveals_clue_ids: list[str] = []
    reveals_memory_ids: list[str] = []
    suggested_followups: list[str] = []


class AgentInterviewPack(BaseModel):
    agent_id: str
    default_answers: dict[str, str] = {}  # question_type -> fallback text
    rules: list[AnswerRule] = []


# ---------------------------------------------------------------------------
# Challenge data (hand-authored scripted outcomes for the challenge engine)
# ---------------------------------------------------------------------------

class ChallengeRule(BaseModel):
    """A scripted reaction to a specific claim being challenged with
    specific evidence. First matching rule (in file order) wins."""

    target_agent_id: str
    challenged_claim_id: str
    evidence_clue_ids: list[str] = []
    match_mode: Literal["any", "all"] = "any"
    required_prior_clue_ids: list[str] = []
    outcome: ChallengeOutcome
    response_text: str
    emotional_shift: Optional[str] = None
    pressure_delta: float = 0.0
    new_claims: list[AnswerClaim] = []
    reveals_clue_ids: list[str] = []
    reveals_memory_ids: list[str] = []
    sets_claim_status: Optional[ClaimStatus] = None


# ---------------------------------------------------------------------------
# Solution / judging config (hand-authored; consumed only by the judge & reveal)
# ---------------------------------------------------------------------------

class SolutionCriterion(BaseModel):
    """A gradeable free-text answer field. A concept group matches if any of
    its synonyms appears (case-insensitive substring) in the player's answer.
    The field is 'correct' when at least `min_groups` distinct groups match."""

    canonical: str
    concept_groups: list[list[str]] = []
    min_groups: int = 1


class Solution(BaseModel):
    killer_id: str
    motive: SolutionCriterion
    method: SolutionCriterion
    opportunity: SolutionCriterion
    key_clue_ids: list[str] = []          # the clues that prove the case
    explanation: str = ""                  # shown on a correct reveal
    epilogues: dict[str, str] = Field(default_factory=dict)



# ---------------------------------------------------------------------------
# Bundled case data (everything loaded from disk, immutable in play)
# ---------------------------------------------------------------------------

class CaseData(BaseModel):
    case: CaseFile
    agents: list[Agent]
    locations: list[Location]
    objects: list[GameObject]
    memories: list[SeededMemory]
    events: list[Event]
    clues: list[Clue]
    conclusions: list[Conclusion]
    interview_packs: list[AgentInterviewPack]
    challenge_rules: list[ChallengeRule] = []
    solution: Solution
    metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Mutable player-session models
# ---------------------------------------------------------------------------

class Note(BaseModel):
    note_id: str
    note_type: NoteType = "manual"
    title: str
    body: str = ""
    linked_agent_ids: list[str] = []
    linked_clue_ids: list[str] = []
    linked_event_ids: list[str] = []
    linked_claim_ids: list[str] = []
    player_tags: list[str] = []
    status: Literal["open", "unresolved", "resolved"] = "open"
    pinned_to_agent_id: Optional[str] = None


class Claim(BaseModel):
    claim_id: str
    speaker_agent_id: str
    claim_text: str
    claim_type: str = "statement"
    time_reference: Optional[str] = None
    location_reference_id: Optional[str] = None
    truthfulness: TruthStatus = "unknown"  # hidden from player until reveal
    player_known_status: ClaimStatus = "claimed"


class InterviewMessage(BaseModel):
    speaker: Literal["player", "agent"]
    text: str
    deterministic_text: Optional[str] = None
    question_type: Optional[QuestionType] = None
    generated_claim_ids: list[str] = []
    revealed_clue_ids: list[str] = []
    llm_rewrite_used: bool = False
    llm_rewrite_fallback: bool = False
    llm_rewrite_fallback_reason: Optional[str] = None


class InterviewTranscript(BaseModel):
    agent_id: str
    messages: list[InterviewMessage] = []


class AgentBeliefState(BaseModel):
    """A suspect's private state of mind (spec 15 Phase C). Updated by an
    offline batch LLM call between player actions; only ever read as prompt
    flavour — never by challenge/judge logic, never as allowed facts."""

    worry_level: float = 0.0
    current_suspicion_target: Optional[str] = None
    talking_points: list[str] = []


# ---------------------------------------------------------------------------
# API request/response payloads
# ---------------------------------------------------------------------------

class GenerateCaseRequest(BaseModel):
    case_type: str = "blackmail"
    difficulty: str = "standard"
    seed: int = 12345
    activate: bool = False
    mode: Literal["deterministic", "llm_assisted"] = "deterministic"
    fallback_allowed: bool = True
    num_suspects: Optional[int] = Field(None, ge=3, le=7)
    num_locations: Optional[int] = Field(None, ge=3, le=8)
    theme_preset: Optional[str] = None
    custom_theme: Optional[str] = None
    tone: Optional[str] = None
    llm_notes: Optional[str] = None
    candidate_count: int = Field(1, ge=1, le=5)



class AskRequest(BaseModel):
    agent_id: str
    question_type: QuestionType
    time_reference: Optional[str] = None
    topic_clue_id: Optional[str] = None
    topic_object_id: Optional[str] = None
    topic_location_id: Optional[str] = None
    # The player's actual free-text wording, when this request was derived
    # from a classified free-text question rather than a preformatted button.
    # Used in place of the templated question text so the transcript and the
    # LLM rewrite react to what was really asked, not a generic paraphrase.
    original_question_text: Optional[str] = None


class AskResponse(BaseModel):
    question_text: str
    deterministic_answer_text: str
    display_answer_text: str
    answer_type: str
    emotional_shift: Optional[str] = None
    new_claims: list[Claim] = []
    revealed_clues: list[Clue] = []
    suggested_followups: list[str] = []
    llm_rewrite_used: bool = False
    llm_rewrite_fallback: bool = False
    llm_rewrite_fallback_reason: Optional[str] = None


class QuestionIntent(BaseModel):
    intent: QuestionIntentType
    confidence: float
    referenced_time: Optional[str] = None
    referenced_agent_id: Optional[str] = None
    referenced_location_id: Optional[str] = None
    referenced_object_id: Optional[str] = None
    referenced_clue_id: Optional[str] = None
    rewritten_structured_question: str


class ChallengeSuggestion(BaseModel):
    target_agent_id: str
    challenged_claim_id: str
    claim_text: str
    claim_status: str
    evidence_clue_id: str
    evidence_title: str


class FreeTextAskRequest(BaseModel):
    agent_id: str
    question: str


class FreeTextAskResponse(BaseModel):
    intent: QuestionIntent
    answer: Optional[dict] = None
    challenge_suggestion: Optional[ChallengeSuggestion] = None
    challenge_result: Optional[dict] = None
    fallback_message: Optional[str] = None


class NoteCreate(BaseModel):
    note_type: NoteType = "manual"
    title: str
    body: str = ""
    linked_agent_ids: list[str] = []
    linked_clue_ids: list[str] = []
    linked_event_ids: list[str] = []
    linked_claim_ids: list[str] = []
    player_tags: list[str] = []
    pinned_to_agent_id: Optional[str] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    player_tags: Optional[list[str]] = None
    status: Optional[Literal["open", "unresolved", "resolved"]] = None
    pinned_to_agent_id: Optional[str] = None


class SuspicionUpdate(BaseModel):
    agent_id: str
    level: SuspicionLevel


MarkerType = Literal[
    "important",
    "theory",
    "red_herring",
    "cleared",
    "suspect",
    "prime_suspect",
    "open_question"
]

class MarkerUpdate(BaseModel):
    element_id: str
    marker: MarkerType
    action: Literal["add", "remove", "clear"]


class InspectRequest(BaseModel):
    location_id: Optional[str] = None
    object_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Challenge payloads
# ---------------------------------------------------------------------------

class ChallengeRequest(BaseModel):
    target_agent_id: str
    challenged_claim_id: str
    evidence_clue_ids: list[str] = []
    player_statement: Optional[str] = None


class ChallengeRecord(BaseModel):
    """Full record of a resolved challenge, stored in the session. The
    player-safe projection lives in challenge.py."""

    challenge_id: str
    case_id: str
    target_agent_id: str
    challenged_claim_id: str
    evidence_clue_ids: list[str] = []
    player_statement: Optional[str] = None
    outcome: ChallengeOutcome
    deterministic_response_text: str
    display_response_text: str
    emotional_shift: Optional[str] = None
    new_claim_ids: list[str] = []
    revealed_memory_ids: list[str] = []
    revealed_clue_ids: list[str] = []
    pressure_delta: float = 0.0
    created_note_ids: list[str] = []
    duplicate: bool = False
    llm_rewrite_used: bool = False
    llm_rewrite_fallback: bool = False
    llm_rewrite_fallback_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Accusation payloads
# ---------------------------------------------------------------------------

class AccusationRequest(BaseModel):
    accused_agent_id: str
    motive_answer: str = ""
    method_answer: str = ""
    opportunity_answer: str = ""
    supporting_note_ids: list[str] = []
    supporting_clue_ids: list[str] = []


class RedHerringExplanation(BaseModel):
    agent_id: str
    agent_name: str
    looked_suspicious_because: str
    actually_innocent_because: str


class EpilogueCard(BaseModel):
    agent_id: str
    agent_name: str
    text: str



class TimelineEntry(BaseModel):
    time: str
    description: str
    location_name: str


class AccusationResult(BaseModel):
    accusation_id: str
    case_id: str
    # Who the player accused — only ever returned post-accusation.
    accused_agent_id: str = ""
    accused_name: str = ""
    score: int
    killer_correct: bool
    motive_correct: bool
    method_correct: bool
    opportunity_correct: bool
    evidence_score: float
    missed_key_clues: list[str] = []
    false_assumptions: list[str] = []
    explanation: str
    verdict: str
    # Truth reveal — only ever returned by the accuse/reveal endpoints:
    true_killer_id: str
    true_killer_name: str
    true_motive: str
    true_method: str
    true_timeline: list[TimelineEntry] = []
    key_clues_found: list[str] = []
    key_clues_missed: list[str] = []
    red_herring_explanations: list[RedHerringExplanation] = []
    epilogues: list[EpilogueCard] = Field(default_factory=list)
    player_evidence_used: list[str] = []

    detective_rating: str = ""

# ---------------------------------------------------------------------------
# Feedback payloads
# ---------------------------------------------------------------------------

class Feedback(BaseModel):
    understood_goal: Literal["yes", "mostly", "no"]
    rewind_made_sense: Literal["yes", "mostly", "no"]
    hints_helpfulness: Literal["too_little", "about_right", "too_much", "spoiled"]
    difficulty: Literal["too_easy", "about_right", "too_hard", "confusing"]
    final_reveal_fair: Literal["yes", "mostly", "no"]
    enjoyment_score: int  # 1-5
    confidence_score: int  # 1-5
    suspected_before_reveal: Optional[str] = None
    most_confusing_part: Optional[str] = None
    best_part: Optional[str] = None
    worst_part: Optional[str] = None
    clues_that_felt_unfair: Optional[str] = None
    free_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Case Quality Report
# ---------------------------------------------------------------------------

class CaseQualityReport(BaseModel):
    suspect_distinctiveness: float
    motive_clarity: float
    red_herring_strength: float
    clue_distribution: float
    location_usage_balance: float
    timeline_density: float
    solution_fairness: float
    theme_adherence: float
    tone_consistency: float
    overall_score: float
    warnings: list[str] = []
    suggested_improvements: list[str] = []
