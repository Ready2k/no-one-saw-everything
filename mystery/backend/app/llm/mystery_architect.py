"""Orchestrates LLM generation, assembly, validation, and repair."""

import json
import logging
from pathlib import Path

from ..models import CaseData
from .schemas import CasePlan
from .client import get_llm_client
from .case_assembler import assemble_case
from ..validator import validate_case

logger = logging.getLogger(__name__)

MAX_LLM_REPAIR_ATTEMPTS = 3

PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text()

def generate_llm_case(
    base_case_data: CaseData,
    roles: dict[str, str],
    case_type: str,
    difficulty: str,
    seed: int
) -> tuple[CaseData | None, str | None, int]:
    """
    1. Calls LLM to generate CasePlan
    2. Assembles CaseData
    3. Validates CaseData
    4. Repeats (repair) if invalid up to max attempts
    
    Returns: (assembled_case, fallback_reason, repair_attempts)
    """
    from .config import get_llm_config
    config = get_llm_config()
    if not config.configured:
        return None, config.fallback_reason or "llm_not_configured", 0

    client = get_llm_client()
    
    sys_prompt = load_prompt("case_plan_system")
    user_prompt = load_prompt("case_plan_user").format(
        case_type=case_type,
        difficulty=difficulty,
        VICTIM_ID="{VICTIM_ID}",
        KILLER_ID="{KILLER_ID}",
        RH1_ID="{RH1_ID}",
        RH2_ID="{RH2_ID}",
        WITNESS1_ID="{WITNESS1_ID}",
        WITNESS2_ID="{WITNESS2_ID}",
        WITNESS3_ID="{WITNESS3_ID}",
        WITNESS4_ID="{WITNESS4_ID}"
    )
    
    try:
        plan = client.generate_json(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            schema=CasePlan,
            temperature=0.2
        )
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return None, "provider_error", 0
        
    for attempt in range(MAX_LLM_REPAIR_ATTEMPTS + 1):
        # Assemble
        assembled_case = assemble_case(plan, base_case_data, roles, seed)
        
        # Validate
        val_result = validate_case(assembled_case)
        if val_result["valid"]:
            return assembled_case, None, attempt
            
        logger.warning(f"LLM Case validation failed on attempt {attempt}: {val_result['errors']}")
        
        if attempt == MAX_LLM_REPAIR_ATTEMPTS:
            return None, "repair_exhausted", attempt
            
        # Repair
        repair_sys = load_prompt("repair_system")
        repair_user = load_prompt("repair_user").format(
            errors=json.dumps(val_result["errors"], indent=2),
            original_plan=plan.model_dump_json(indent=2),
            VICTIM_ID="{VICTIM_ID}",
            KILLER_ID="{KILLER_ID}",
            RH1_ID="{RH1_ID}",
            RH2_ID="{RH2_ID}",
            WITNESS1_ID="{WITNESS1_ID}",
            WITNESS2_ID="{WITNESS2_ID}",
            WITNESS3_ID="{WITNESS3_ID}",
            WITNESS4_ID="{WITNESS4_ID}"
        )
        
        try:
            plan = client.generate_json(
                system_prompt=repair_sys,
                user_prompt=repair_user,
                schema=CasePlan,
                temperature=0.2
            )
        except Exception as e:
            logger.error(f"LLM repair failed: {e}")
            return None, "provider_error", attempt
        
    return None, "repair_exhausted", MAX_LLM_REPAIR_ATTEMPTS
