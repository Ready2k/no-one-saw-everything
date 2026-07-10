import sys
import json
import os
import argparse
sys.path.append('backend')
from app.llm.client import get_llm_client

def run_reviewer():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', default='case_002', help='Case ID to review, e.g., case_003')
    args = parser.parse_args()

    case_id = args.case

    with open('reviewers/prompt.md', 'r') as f:
        system_prompt = f.read()

    case_dir = f'backend/app/data/{case_id}'
    case_data = {}
    for filename in sorted(os.listdir(case_dir)):
        if filename.endswith('.json'):
            with open(os.path.join(case_dir, filename), 'r') as f:
                case_data[filename] = json.load(f)

    user_prompt = f"Here is the data for {case_id}:\n\n" + json.dumps(case_data, indent=2)

    client = get_llm_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    print("Calling LLM...")
    response = client.generate_chat(
        messages=messages,
        timeout_seconds=300,
        response_format_json=False
    )
    
    output_file = f'reviewers/{case_id}_review.md'
    with open(output_file, 'w') as f:
        f.write(response)
        
    print(f"Review saved to {output_file}")

if __name__ == '__main__':
    run_reviewer()
