"""Pydantic schemas for LLM mystery generation."""

from typing import Dict, List, Literal, Any
from pydantic import BaseModel


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


class TimelinePlan(BaseModel):
    beats: List["BeatPlan"] = []
    routines: List["RoutinePlan"] = []


class CasePlan(BaseModel):
    case_type: Literal["blackmail", "debt", "betrayal"]
    title: str
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

class PlotOutlinePlan(BaseModel):
    title: str
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
