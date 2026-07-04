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

class FlavourPlan(BaseModel):
    interview_flavour: Dict[str, Dict[str, Any]] = {}
    reveal_narration: str = ""
