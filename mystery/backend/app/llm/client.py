"""LLM Provider abstraction."""

import os
import json
import urllib.request
from typing import Protocol, Type, TypeVar, Any
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMClient(Protocol):
    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Type[T],
        temperature: float = 0.2,
        timeout_seconds: int = 60,
    ) -> T:
        ...


VALID_FAKE_PLAN = {
    "case_type": "blackmail",
    "title": "The Fake Planner Murder",
    "motive_variant": "The victim was blackmailed.",
    "victim_rationale": "Victim was angry.",
    "killer_rationale": "Killer had enough.",
    "red_herring_rationales": {
        "{RH1_ID}": "Has a dark secret.",
        "{RH2_ID}": "Wanted the victim dead too."
    },
    "seeded_memories": [
        {
            "owner_role": "{KILLER_ID}",
            "known_by_roles": ["{KILLER_ID}"],
            "memory_type": "private_secret",
            "case_function": "killer_motive",
            "truth_status": "true",
            "summary": "Stole money.",
            "intended_discovery_path": "Found ledger.",
            "linked_clue_purpose": "Proof of theft."
        },
        {
            "owner_role": "{KILLER_ID}",
            "known_by_roles": ["{KILLER_ID}"],
            "memory_type": "private_secret",
            "case_function": "opportunity_setup",
            "truth_status": "true",
            "summary": "Waited in the alley.",
            "intended_discovery_path": "Found footprints.",
            "linked_clue_purpose": "Proves location."
        },
        {
            "owner_role": "{KILLER_ID}",
            "known_by_roles": ["{KILLER_ID}"],
            "memory_type": "private_secret",
            "case_function": "false_alibi_reason",
            "truth_status": "true",
            "summary": "Lied about being home.",
            "intended_discovery_path": "Witness saw them leave.",
            "linked_clue_purpose": "Breaks alibi."
        }
    ],
    "clue_plans": [
        {
            "clue_type": "document",
            "supports_conclusion_type": "motive",
            "discovery_method": "inspect",
            "ambiguity_level": "low",
            "linked_role": "{KILLER_ID}",
            "player_facing_description": "A ledger showing theft."
        },
        {
            "clue_type": "physical_evidence",
            "supports_conclusion_type": "method",
            "discovery_method": "inspect",
            "ambiguity_level": "low",
            "linked_role": "{KILLER_ID}",
            "player_facing_description": "A bloody weapon."
        },
        {
            "clue_type": "witness_statement",
            "supports_conclusion_type": "opportunity",
            "discovery_method": "interview",
            "ambiguity_level": "medium",
            "linked_role": "{KILLER_ID}",
            "player_facing_description": "Saw the killer nearby."
        }
    ],
    "witness_fragments": [
        {
            "witness_role": "{WITNESS1_ID}",
            "observation_summary": "Saw a shadow.",
            "reliability": "low",
            "complicates_timeline_for_role": "{KILLER_ID}"
        }
    ],
    "interview_flavour": {},
    "reveal_narration": "And that is how the fake murder happened."
}


class FakeLLMClient:
    def __init__(self, override_response: dict[str, Any] | None = None, fail_count: int = 0):
        self.override_response = override_response
        self.fail_count = fail_count
        self.calls = 0

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Type[T],
        temperature: float = 0.2,
        timeout_seconds: int = 60,
    ) -> T:
        self.calls += 1
        if self.calls <= self.fail_count:
            raise RuntimeError("Fake LLM timeout or error")
            
        if self.override_response is not None:
            return schema.model_validate(self.override_response)
            
        if schema.__name__ == "CasePlan":
            return schema.model_validate(VALID_FAKE_PLAN)
            
        if schema.__name__ == "DialogueRewrite":
            return schema.model_validate({"rewritten_text": "Fake rewritten text."})
            
        raise ValueError(f"FakeLLMClient doesn't know how to mock {schema.__name__}")


class OpenAICompatibleLLMClient:
    def __init__(self, base_url: str, api_key: str | None, model: str):
        self.base_url = base_url
        self.api_key = api_key or "optional"
        self.model = model
        
    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Type[T],
        temperature: float = 0.2,
        timeout_seconds: int = 60,
    ) -> T:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }
        
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                content = resp_data["choices"][0]["message"]["content"]
                return schema.model_validate_json(content)
        except Exception as e:
            raise RuntimeError(f"LLM API Error: {e}")


def get_llm_client() -> LLMClient:
    from .config import get_llm_config
    config = get_llm_config()
    
    if config.provider == "openai_compatible" and config.configured:
        return OpenAICompatibleLLMClient(
            base_url=config.base_url, # type: ignore
            api_key=config.api_key,
            model=config.model # type: ignore
        )
    return FakeLLMClient()
