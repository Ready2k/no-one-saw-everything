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

    def generate_chat(
        self,
        *,
        messages: list[dict[str, str]],
        schema: Type[T] | None = None,
        temperature: float = 0.2,
        timeout_seconds: int = 60,
        response_format_json: bool = True,
    ) -> Any:
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
    "scene_description": "The fake murder scene description.",
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

FAKE_IDENTITIES = {
    "VICTIM": {"full_name": "Vera Sinclair", "occupation": "Antiques dealer"},
    "KILLER": {"full_name": "Damon Cole", "occupation": "Shop assistant"},
    "RH1": {"full_name": "Priya Nandan", "occupation": "Courier"},
    "RH2": {"full_name": "Owen Blythe", "occupation": "Accountant"},
    "WITNESS1": {"full_name": "Isla Ferro", "occupation": "Barista"},
    "WITNESS2": {"full_name": "Nora Kade", "occupation": "Nurse"},
    "WITNESS3": {"full_name": "Elton Marsh", "occupation": "Retired teacher"},
    "WITNESS4": {"full_name": "Sana Reyes", "occupation": "Bookshop assistant"},
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

        if schema.__name__ == "QuestionIntent":
            return schema.model_validate({
                "intent": "fallback_unknown",
                "confidence": 0.0,
                "rewritten_structured_question": "Unknown question",
            })

        if schema.__name__ == "AgentBeliefState":
            return schema.model_validate({
                "worry_level": 0.2,
                "current_suspicion_target": None,
                "talking_points": ["I just want this settled quietly."],
            })

        raise ValueError(f"FakeLLMClient doesn't know how to mock {schema.__name__}")

    def generate_chat(
        self,
        *,
        messages: list[dict[str, str]],
        schema: Type[T] | None = None,
        temperature: float = 0.2,
        timeout_seconds: int = 60,
        response_format_json: bool = True,
    ) -> Any:
        self.calls += 1
        if self.calls <= self.fail_count:
            raise RuntimeError("Fake LLM timeout or error")
            
        if self.override_response is not None:
            if schema:
                return schema.model_validate(self.override_response)
            return json.dumps(self.override_response)
            
        if schema is not None:
            if schema.__name__ == "CasePlan":
                return schema.model_validate(VALID_FAKE_PLAN)
            if schema.__name__ == "DialogueRewrite":
                return schema.model_validate({"rewritten_text": "Fake rewritten text."})
            if schema.__name__ == "QuestionIntent":
                return schema.model_validate({
                    "intent": "fallback_unknown",
                    "confidence": 0.0,
                    "rewritten_structured_question": "Unknown question",
                })
            if schema.__name__ == "PlotOutlinePlan":
                return schema.model_validate({
                    "title": "The Fake Planner Murder",
                    "motive_variant": "The victim was blackmailed.",
                    "victim_rationale": "Victim was angry.",
                    "killer_rationale": "Killer had enough.",
                    "red_herring_rationales": {
                        "{RH1_ID}": "Has a dark secret.",
                        "{RH2_ID}": "Wanted the victim dead too."
                    },
                    "scene_description": "The fake murder scene description."
                })
            if schema.__name__ == "CluesPlan":
                return schema.model_validate({"clue_plans": VALID_FAKE_PLAN["clue_plans"]})
            if schema.__name__ == "MemoriesPlan":
                return schema.model_validate({
                    "seeded_memories": VALID_FAKE_PLAN["seeded_memories"],
                    "witness_fragments": VALID_FAKE_PLAN["witness_fragments"]
                })
            if schema.__name__ == "RoleMemoriesPlan":
                last_message = messages[-1]["content"] if messages else ""
                if "{KILLER_ID}" in last_message:
                    return schema.model_validate({"memories": VALID_FAKE_PLAN["seeded_memories"]})
                return schema.model_validate({"memories": []})
            if schema.__name__ == "WitnessFragmentsPlan":
                return schema.model_validate({"witness_fragments": VALID_FAKE_PLAN["witness_fragments"]})
            if schema.__name__ == "CharacterIdentitiesPlan":
                return schema.model_validate({"identities": FAKE_IDENTITIES})
            if schema.__name__ == "FlavourPlan":
                return schema.model_validate({
                    "interview_flavour": VALID_FAKE_PLAN["interview_flavour"],
                    "reveal_narration": VALID_FAKE_PLAN["reveal_narration"]
                })
        
        last_message = messages[-1]["content"] if messages else ""
        if "plot outline" in last_message.lower():
            return json.dumps({
                "title": "The Fake Planner Murder",
                "motive_variant": "The victim was blackmailed.",
                "victim_rationale": "Victim was angry.",
                "killer_rationale": "Killer had enough.",
                "red_herring_rationales": {
                    "{RH1_ID}": "Has a dark secret.",
                    "{RH2_ID}": "Wanted the victim dead too."
                },
                "scene_description": "The fake murder scene description."
            })
        if "clue plans" in last_message.lower():
            return json.dumps({
                "clue_plans": VALID_FAKE_PLAN["clue_plans"]
            })
        if "seeded memories" in last_message.lower():
            return json.dumps({
                "seeded_memories": VALID_FAKE_PLAN["seeded_memories"],
                "witness_fragments": VALID_FAKE_PLAN["witness_fragments"]
            })
        return json.dumps(VALID_FAKE_PLAN)



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
        
        # Inject the JSON schema into the system prompt to guide JSON formatting
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        system_prompt_with_schema = (
            f"{system_prompt}\n\n"
            f"Response format MUST be a JSON object conforming to the following JSON Schema:\n"
            f"{schema_json}"
        )
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt_with_schema},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": 8192,
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

    def generate_chat(
        self,
        *,
        messages: list[dict[str, str]],
        schema: Type[T] | None = None,
        temperature: float = 0.2,
        timeout_seconds: int = 60,
        response_format_json: bool = True,
    ) -> Any:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        processed_messages = []
        for msg in messages:
            processed_messages.append({"role": msg["role"], "content": msg["content"]})
            
        if schema is not None:
            schema_json = json.dumps(schema.model_json_schema(), indent=2)
            for msg in processed_messages:
                if msg["role"] == "system":
                    msg["content"] = (
                        f"{msg['content']}\n\n"
                        f"Response format MUST be a JSON object conforming to the following JSON Schema:\n"
                        f"{schema_json}"
                    )
                    break
            else:
                processed_messages.insert(0, {
                    "role": "system",
                    "content": f"Response format MUST be a JSON object conforming to the following JSON Schema:\n{schema_json}"
                })
        
        data = {
            "model": self.model,
            "messages": processed_messages,
            "temperature": temperature,
            "max_tokens": 8192,
        }
        if response_format_json:
            data["response_format"] = {"type": "json_object"}
            
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                content = resp_data["choices"][0]["message"]["content"]
                if schema is not None:
                    return schema.model_validate_json(content)
                return content
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
