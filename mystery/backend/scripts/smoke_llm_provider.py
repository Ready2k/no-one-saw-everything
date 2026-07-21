import os
import sys
import time
from pathlib import Path
from pydantic import BaseModel

# Add backend dir to path so we can import app modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.llm.config import get_llm_config
from app.llm.client import get_llm_client

class DummySchema(BaseModel):
    message: str
    status: str

def main():
    config = get_llm_config()
    
    if not config.configured:
        print(f"Provider: {config.provider}")
        print(f"Fallback reason: {config.fallback_reason}")
        print("LLM is not configured properly. Exiting smoke test.")
        sys.exit(1)
        
    print(f"Provider: {config.provider}")
    print(f"Model: {config.model or 'default'}")
    
    client = get_llm_client()
    
    start_time = time.time()
    try:
        response = client.generate_json(
            system_prompt="You are a helpful test assistant. Respond in JSON with a 'message' and 'status'='ok'.",
            user_prompt="Say hello.",
            schema=DummySchema,
            temperature=0.0
        )
    except Exception as e:
        latency = time.time() - start_time
        print(f"Latency: {latency:.2f}s")
        print(f"Error: {e}")
        sys.exit(1)
        
    latency = time.time() - start_time
    print(f"Latency: {latency:.2f}s")
    
    # We do not print raw output or prompts, just validation
    if isinstance(response, DummySchema) and response.status == "ok":
        print("Schema parse: OK")
    else:
        print("Schema parse: FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
