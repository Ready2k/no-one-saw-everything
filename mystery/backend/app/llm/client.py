"""LLM Provider abstraction."""

# import os  # UNUSED — commented out during code review [2026-07-19]
import json
import logging
import urllib.error
import urllib.request
from typing import Protocol, Type, TypeVar, Any
from pydantic import BaseModel

from .http_safety import urlopen_no_redirect

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

# A "thinking" model spends most of a turn on reasoning the player never sees.
# Measured on gemma4:latest rewriting one line of Clara's dialogue: ~1,800
# characters of hidden reasoning to produce ~220 characters of speech, at a
# median of 12.5s per turn. With reasoning off the same prompt takes 1.6s — and
# acceptance under the sanitiser was *identical* (4/6 either way, same failure),
# so the thinking bought latency and nothing else. An interview is a
# conversation; ten seconds of silence per line is the difference between a
# suspect and a progress bar.
#
# `reasoning_effort` is an OpenAI-API parameter, not an Ollama one, so it is not
# universally accepted — and "none" specifically is what disables thinking
# ("low" does not; measured). Rather than force a setting on the player or
# assume the endpoint supports it, the first call to a given endpoint tries it
# and remembers the answer: a server that rejects the field is retried once
# without it and never sent it again.
_REASONING_OFF = {"reasoning_effort": "none"}
_reasoning_supported: dict[tuple[str, str], bool] = {}


def reset_reasoning_probe() -> None:
    """Forget which endpoints accept `reasoning_effort`. For tests."""
    _reasoning_supported.clear()

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
    "weather": "fog",
    "weather_intensity": "light",
    "wind": "breezy",
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

# A small but complete timeline the deterministic compiler can turn into a valid
# morning — one ambient beat per suspect role plus a routine per role. Kept
# minimal on purpose so offline generation and the timeline tests exercise the
# compiler's spine/coverage guarantees rather than the LLM's richness.
FAKE_TIMELINE = {
    "beats": [
        {"role": "{VICTIM_ID}", "location_role": "victim_home", "action_summary": "Goes over the books at home.", "public_summary": None, "visibility": "private", "beat_kind": "routine", "order_hint": 0},
        {"role": "{KILLER_ID}", "location_role": "public", "action_summary": "Opens up and sets out chairs.", "public_summary": "Someone sets out chairs.", "visibility": "public", "beat_kind": "routine", "order_hint": 1},
        {"role": "{RH1_ID}", "location_role": "public", "action_summary": "Crosses the square on the delivery round.", "public_summary": "A figure crosses the square.", "visibility": "public_partial", "beat_kind": "sighting", "order_hint": 2},
        {"role": "{RH2_ID}", "location_role": "role_home", "action_summary": "Reads the morning post.", "public_summary": None, "visibility": "private", "beat_kind": "routine", "order_hint": 3},
        {"role": "{WITNESS1_ID}", "location_role": "public", "action_summary": "Wipes down the counter.", "public_summary": "The counter is wiped down.", "visibility": "public", "beat_kind": "routine", "order_hint": 4},
        {"role": "{WITNESS2_ID}", "location_role": "witness_spot", "action_summary": "Takes a shortcut past the shops.", "public_summary": "Someone hurries past the shops.", "visibility": "public_partial", "beat_kind": "sighting", "order_hint": 5},
        {"role": "{WITNESS3_ID}", "location_role": "public", "action_summary": "Sits on the bench with a flask.", "public_summary": "An old regular sits with a flask.", "visibility": "public", "beat_kind": "routine", "order_hint": 6},
        {"role": "{WITNESS4_ID}", "location_role": "role_home", "action_summary": "Gets ready for the day.", "public_summary": None, "visibility": "private", "beat_kind": "routine", "order_hint": 7},
    ],
    "routines": [
        {"role": "{VICTIM_ID}", "routine_summary": "An early riser who reviews accounts before anyone else is about."},
        {"role": "{KILLER_ID}", "routine_summary": "First to open up, methodical and unhurried."},
        {"role": "{RH1_ID}", "routine_summary": "On the delivery round through the square from first light."},
        {"role": "{RH2_ID}", "routine_summary": "A creature of habit who reads the post over breakfast."},
        {"role": "{WITNESS1_ID}", "routine_summary": "Behind the counter well before the doors open."},
        {"role": "{WITNESS2_ID}", "routine_summary": "Cuts through the shops on the way to a shift."},
        {"role": "{WITNESS3_ID}", "routine_summary": "Takes the same bench in the square every morning."},
        {"role": "{WITNESS4_ID}", "routine_summary": "Slow to start, always the last one out the door."},
    ],
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
                    "weather": "fog",
                    "weather_intensity": "light",
                    "wind": "breezy",
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
            if schema.__name__ == "TimelinePlan":
                return schema.model_validate(FAKE_TIMELINE)
        
        last_message = messages[-1]["content"] if messages else ""
        if "plot outline" in last_message.lower():
            return json.dumps({
                "title": "The Fake Planner Murder",
                "weather": "fog",
                "weather_intensity": "light",
                "wind": "breezy",
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

    def _post(self, url: str, payload: dict, timeout_seconds: int) -> dict:
        """POST a chat-completions payload, suppressing hidden reasoning where
        the endpoint allows it (see `_REASONING_OFF`).

        A server that rejects the field is retried once without it, and the
        result is cached per (endpoint, model) so the probe costs at most one
        extra request per configuration rather than one per turn.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        key = (self.base_url, self.model)
        include = _reasoning_supported.get(key, True)

        def send(body: dict) -> dict:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode("utf-8"), headers=headers
            )
            with urlopen_no_redirect(req, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))

        if not include:
            return send(payload)

        try:
            result = send({**payload, **_REASONING_OFF})
        except urllib.error.HTTPError:
            # Most likely an endpoint that does not know the field. Confirm by
            # retrying without it: if that succeeds, the field was the problem.
            result = send(payload)
            _reasoning_supported[key] = False
            logger.info(
                "%s does not accept reasoning_effort; sending without it from now on",
                self.model,
            )
            return result

        _reasoning_supported.setdefault(key, True)
        return result

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
        
        try:
            resp_data = self._post(url, data, timeout_seconds)
            content = resp_data["choices"][0]["message"]["content"]
            if not content:
                raise RuntimeError("LLM returned empty response")
            return schema.model_validate_json(content)
        except Exception as e:
            raise RuntimeError(f"LLM API Error: {e}") from e

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
            
        try:
            resp_data = self._post(url, data, timeout_seconds)
            content = resp_data["choices"][0]["message"]["content"]
            if schema is not None:
                if not content:
                    raise RuntimeError("LLM returned empty response")
                return schema.model_validate_json(content)
            return content
        except Exception as e:
            raise RuntimeError(f"LLM API Error: {e}") from e



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
