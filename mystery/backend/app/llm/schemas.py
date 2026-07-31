"""Pydantic schemas for LLM mystery generation."""

import re
from typing import Dict, List, Literal, Any, Optional
from pydantic import BaseModel, field_validator

# `Agent.routine_summary` is player-visible (projections.project_agent) and is rendered on the
# Suspects screen before a single clue has been discovered. Cases 004/005/006 shipped with
# routines that stated the killer's motive, announced that an alibi was false, and gave away
# case 006's identity twist. The prompt now forbids this; this is the belt-and-braces check for
# when the model ignores the prompt anyway.
_ROUTINE_LEAK_PATTERNS = [
    r"\bthat night\b",
    r"\bwill need to be\b",
    r"\bwill matter\b",
    r"\bwill have seen\b",
    r"\bwill recognise\b",
    r"\b(?:forged|false) alibi\b",
    r"\b(?:he|she|they) lied\b",
    r"\bsecretly (?:owed|killed|poisoned|followed|paid)\b",
    r"\bthe (?:killer|murderer)\b",
    r"\bif anyone asked\b",
    r"\bmaiden name\b",
]


class SeededMemoryPlan(BaseModel):
    owner_role: str
    known_by_roles: List[str]
    memory_type: str
    case_function: str
    truth_status: str
    summary: str
    intended_discovery_path: str | None = None
    linked_clue_purpose: str | None = None


class CluePlan(BaseModel):
    clue_type: str
    supports_conclusion_type: str
    discovery_method: str
    ambiguity_level: str
    linked_role: str
    player_facing_description: str


class WitnessFragmentPlan(BaseModel):
    witness_role: str
    observation_summary: str
    reliability: str
    complicates_timeline_for_role: str | None = None


class BeatPlan(BaseModel):
    """One story beat in the generated morning. The LLM authors the *content*
    (who/where-semantically/what/how-visible); the deterministic compiler
    (timeline_compiler.py) assigns concrete times, real location ids, and
    fresh event ids while enforcing the fairness invariants. The murder and
    body-discovery beats are NOT authored here — the compiler synthesises them
    from the case's fixed timing so they can never be leaked or mis-timed."""
    role: str                        # {VICTIM_ID}/{KILLER_ID}/{RH1_ID}/{WITNESS1_ID}...
    location_role: str               # "public"|"victim_home"|"killer_home"|"murder_scene"|"role_home"|"witness_spot"
    action_summary: str              # truth_description prose (may reference {ROLE_NAME})
    public_summary: str | None = None  # player_description if visible; null if private
    visibility: str = "public"       # public | public_partial | private | hidden
    beat_kind: str = "routine"       # routine|approach|opportunity|suspicious|sighting|cover
    order_hint: int = 0              # relative order within the morning
    supports_clue_purpose: str | None = None  # motive|means|opportunity|red_herring|innocence|null


class RoutinePlan(BaseModel):
    role: str
    routine_summary: str

    @field_validator("routine_summary")
    @classmethod
    def _no_truth_leak(cls, v: str) -> str:
        hits = [p for p in _ROUTINE_LEAK_PATTERNS if re.search(p, v, re.IGNORECASE)]
        if hits:
            raise ValueError(
                "routine_summary is shown to the player before any clue is discovered and must "
                f"describe ordinary habits only — it must not carry case truth (matched: {hits})"
            )
        return v


class TimelinePlan(BaseModel):
    beats: List["BeatPlan"] = []
    routines: List["RoutinePlan"] = []


class CasePlan(BaseModel):
    case_type: Literal["blackmail", "debt", "betrayal"]
    title: str
    weather: Literal["clear", "overcast", "rain", "fog", "wind", "storm", "snow", "slush"] = "overcast"
    weather_intensity: Literal["light", "moderate", "heavy"] = "moderate"
    wind: Literal["calm", "breezy", "strong"] = "calm"
    motive_variant: str
    victim_rationale: str
    killer_rationale: str
    red_herring_rationales: Dict[str, str]
    scene_description: str
    seeded_memories: List[SeededMemoryPlan]
    clue_plans: List[CluePlan]
    witness_fragments: List[WitnessFragmentPlan]
    interview_flavour: Dict[str, Dict[str, Any]]
    reveal_narration: str
    # Optional so the deterministic path and pre-existing plans stay valid; the
    # timeline phase populates it in llm_assisted mode. Empty/None => the
    # assembler keeps the template events/routines (fallback, no regression).
    timeline: "TimelinePlan | None" = None

class DialogueRewrite(BaseModel):
    rewritten_text: str
    # Layer 7 §9.2: which of the agent's own recorded claims this rewrite drew
    # on.
    #
    # None and [] are deliberately different, and the distinction is the whole
    # point. `None` is the field *absent* — the model said nothing about its
    # sources, which is what §9.3 calls maximally dangerous and refuses. `[]` is
    # the model explicitly answering "I drew on none of them", which is an
    # honest answer and frequently the correct one: most rewrites restate a
    # single grounded line and rest on no prior claim at all.
    #
    # Collapsing the two (the original `= []`) punished the only models that
    # answer accurately. Measured: gemma4:latest cites the right claim 4/4 when
    # the answer rests on one and returns [] 4/4 when it does not, while
    # llama3.1:8b cites every claim it was shown regardless of use — so the
    # naive rule rejected the honest model and passed the indiscriminate one.
    #
    # Capped at danger_table.MAX_SOURCE_CLAIMS at check time, not here, so an
    # over-citing model produces a rejection with a reason rather than a schema
    # error that reads as a provider fault.
    source_claim_ids: Optional[List[str]] = None

class PlotOutlinePlan(BaseModel):
    title: str
    weather: Literal["clear", "overcast", "rain", "fog", "wind", "storm", "snow", "slush"] = "overcast"
    weather_intensity: Literal["light", "moderate", "heavy"] = "moderate"
    wind: Literal["calm", "breezy", "strong"] = "calm"
    motive_variant: str
    victim_rationale: str
    killer_rationale: str
    red_herring_rationales: Dict[str, str] = {}
    scene_description: str

class CluesPlan(BaseModel):
    clue_plans: List[CluePlan] = []

class MemoriesPlan(BaseModel):
    seeded_memories: List[SeededMemoryPlan] = []
    witness_fragments: List[WitnessFragmentPlan] = []

class RoleMemoriesPlan(BaseModel):
    """One suspect role's seeded memories — memories are generated per-role
    (see mystery_architect.py) rather than for all suspects in a single call,
    since a combined call's required output size scales with num_suspects
    and can exceed small local models' context/output budget."""
    memories: List[SeededMemoryPlan] = []

class WitnessFragmentsPlan(BaseModel):
    witness_fragments: List[WitnessFragmentPlan] = []

class FlavourPlan(BaseModel):
    interview_flavour: Dict[str, Dict[str, Any]] = {}
    reveal_narration: str = ""

class CharacterIdentity(BaseModel):
    full_name: str
    occupation: str

class CharacterIdentitiesPlan(BaseModel):
    """Per-role cast identities, generated once up front (before the
    deterministic template is filled in) so every mention of a character
    across the whole case — interviews, memories, events, clues — uses the
    same LLM-authored name/occupation instead of the fixed case_001 cast."""
    identities: Dict[str, CharacterIdentity] = {}
