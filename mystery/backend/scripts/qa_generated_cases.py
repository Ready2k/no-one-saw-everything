#!/usr/bin/env python3
import argparse
import sys
import json
from pathlib import Path

# Add backend to path so we can import app
sys.path.append(str(Path(__file__).parent.parent))

from app.generator import generate_case
from app.validator import validate_case
from app.session import Session
from app.projections import build_playtest_export
from app.judge import judge_accusation
from app.models import AccusationRequest

FORBIDDEN_KEYS = [
    "killer_id",
    "true_timeline",
    "hidden_murder",
    "solution_concepts",
    "truthfulness",
    "is_killer",
    "red_herring_role",
    "raw_llm_output",
    "case_plan",
    "repair_prompt"
]

def check_no_leaks(export_dict) -> list[str]:
    export_json = json.dumps(export_dict)
    leaks = []
    for key in FORBIDDEN_KEYS:
        if f'"{key}"' in export_json:
            leaks.append(key)
    return leaks

def run_qa(case_types: list[str], seeds: int) -> int:
    total_generated = 0
    failures = 0
    clue_counts = []
    red_herring_counts = []
    
    for case_type in case_types:
        print(f"Testing {seeds} seeds for case type: {case_type}...")
        for i in range(1, seeds + 1):
            seed = 1000 + i
            total_generated += 1
            
            try:
                # 1. Generate Case
                case, fallback, reason, repairs = generate_case(
                    case_type=case_type,
                    difficulty="standard",
                    seed=seed,
                    mode="deterministic",
                    fallback_allowed=False
                )
                
                # 2. Validate
                val_result = validate_case(case)
                if not val_result["valid"]:
                    print(f"  ❌ Seed {seed} failed validation: {val_result['errors']}")
                    failures += 1
                    continue
                
                # 3. Check graph density
                clue_count = len(case.clues)
                rh_count = len([c for c in case.conclusions if c.type == "red_herring"])
                clue_counts.append(clue_count)
                red_herring_counts.append(rh_count)
                
                if clue_count < 10:
                    print(f"  ❌ Seed {seed} has too few clues ({clue_count}).")
                    failures += 1
                    continue
                
                # 4. Challenge suggestions exist
                if not case.challenge_rules:
                    print(f"  ❌ Seed {seed} has no challenge rules.")
                    failures += 1
                    continue
                
                # 5. Pre-reveal leak check
                sess = Session(case.case.case_id)
                # simulate finding all clues to ensure projection doesn't leak
                sess.discovered_clue_ids = {c.clue_id for c in case.clues}
                export = build_playtest_export(sess, case, include_reveal=False)
                leaks = check_no_leaks(export)
                if leaks:
                    print(f"  ❌ Seed {seed} leaked forbidden keys pre-reveal: {leaks}")
                    failures += 1
                    continue
                
                # 6. Accusation works and reveal is generated
                req = AccusationRequest(
                    accused_agent_id=case.agents[0].agent_id, # just guess first agent
                    motive_answer="Motive",
                    method_answer="Method",
                    opportunity_answer="Opportunity",
                    supporting_clue_ids=[],
                    supporting_note_ids=[]
                )
                res = judge_accusation(case, sess, req)
                if not res.verdict:
                    print(f"  ❌ Seed {seed} accusation failed.")
                    failures += 1
                    continue
                
            except Exception as e:
                print(f"  ❌ Seed {seed} raised exception: {e}")
                failures += 1
                
    # Summary
    print("\n" + "="*40)
    print("QA Run Summary")
    print("="*40)
    print(f"Generated cases tested: {total_generated}")
    print(f"Valid: {total_generated - failures}")
    print(f"Failures: {failures}")
    if clue_counts:
        print(f"Average clue count: {sum(clue_counts)/len(clue_counts):.1f}")
        print(f"Average red herring count: {sum(red_herring_counts)/len(red_herring_counts):.1f}")
    
    return failures

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QA generated cases for Playtest mode.")
    parser.add_argument("--seeds", type=int, default=10, help="Number of seeds to generate per type.")
    parser.add_argument("--case-type", type=str, default="all", help="Specific case type to test (or 'all').")
    
    args = parser.parse_args()
    
    types = ["blackmail", "debt", "betrayal"] if args.case_type == "all" else [args.case_type]
    
    failed = run_qa(types, args.seeds)
    if failed > 0:
        sys.exit(1)
    sys.exit(0)
