# Inference Settings (Host + Model + Profile Configuration)

This project now supports **unified inference settings** allowing you to:
1. Choose between **multiple LLM hosts** (Ollama remote or vMLX local)
2. Select the **model** available on that host
3. Choose the **prompt profile** optimized for your model size

This gives you flexibility to switch between your remote Ollama server on Desktop-HomePC and your local vMLX servers on your MacBook.

## Quick Start

1. **Access the Inference Settings UI:**
   ```
   http://localhost:8000/settings/inference/
   ```
   
   Or click **Inference settings →** from the Launcher or Simulation pages.

2. **How it works:**
   - Select an **LLM Host** (Ollama Remote or vMLX Local)
   - Page automatically fetches available models from that host
   - Select a **Model** from the dropdown
   - Select a **Prompt Profile** optimized for your model size
   - Click "Save Settings" to persist the selection
   - Backend automatically uses the selected host/model/profile on next restart

## Available LLM Hosts

### 🖥️ Ollama (Remote)
- **Host:** `Desktop-HomePC.local:11434`
- **GPU:** RTX 2070 (CUDA)
- **Best for:** Ollama models (Qwen, Gemma, etc.)

### 💻 vMLX Quality (Local)
- **Host:** `Jamess-MacBook-Pro-2.local:8001`
- **GPU:** Apple M4 Pro (Metal)
- **Models:** Qwen 27B (high quality)

### ⚡ vMLX Fast (Local)
- **Host:** `Jamess-MacBook-Pro-2.local:8002`
- **GPU:** Apple M4 Pro (Metal)
- **Models:** Gemma 3 12B (fast inference)

## What is a Prompt Profile?

Different models perform better with different prompt structures:
- **chat-small** — Optimized for small models like Gemma 4B/7B
- **chat-large** — Optimized for large models like Qwen 14B+ (recommended for Qwen2.5-Coder, Qwen 27B)
- **gpt** — Optimized for OpenAI GPT models
- **cloud** — Optimized for cloud APIs

The profile determines which prompt templates are loaded from `reverie/backend_server/persona/prompt_template/profiles/`.

## API Endpoints

### Get Available Hosts, Models & Profiles
```bash
GET /api/inference/settings/
```
Response:
```json
{
  "ok": true,
  "hosts": [
    {
      "id": "ollama-remote",
      "label": "Ollama (Remote)",
      "endpoint": "http://Desktop-HomePC.local:11434",
      "description": "Ollama server on Desktop-HomePC (RTX 2070)"
    },
    {
      "id": "vmlx-local-quality",
      "label": "vMLX Quality (Local)",
      "endpoint": "http://Jamess-MacBook-Pro-2.local:8001",
      "description": "MLX on MacBook Pro M4 - Quality (Qwen 27B)"
    }
  ],
  "models": [
    {
      "name": "qwen2.5-coder-14b",
      "display_name": "qwen2.5-coder-14b",
      "size": 8192000000,
      "modified": "2026-07-01T..."
    }
  ],
  "profiles": [
    {"value": "chat-small", "label": "chat-small", "hint": "local small model (Gemma 4B)"},
    {"value": "chat-large", "label": "chat-large", "hint": "local large model (Qwen 14B)"},
    {"value": "gpt", "label": "gpt", "hint": "OpenAI GPT-3.5/4"},
    {"value": "cloud", "label": "cloud", "hint": "cloud API"}
  ],
  "current": {
    "host_id": "ollama-remote",
    "model": "qwen2.5-coder-14b",
    "profile": "chat-large"
  }
}
```

### Get Models for a Specific Host
```bash
GET /api/inference/host/models/?host_id=ollama-remote
```
Response:
```json
{
  "ok": true,
  "models": [
    {
      "name": "qwen2.5-coder-14b",
      "display_name": "qwen2.5-coder-14b",
      "size": 8192000000,
      "modified": "2026-07-01T..."
    }
  ]
}
```

### Save Settings (Host + Model + Profile)
```bash
POST /api/inference/settings/save/
Content-Type: application/json

{
  "host_id": "vmlx-local-quality",
  "model": "qwen:27b",
  "profile": "chat-large"
}
```

## Configuration Storage

Unified inference settings are stored in:
```
environment/frontend_server/temp_storage/inference_settings.json
```

Example:
```json
{
  "host_id": "ollama-remote",
  "model": "qwen2.5-coder-14b",
  "profile": "chat-large",
  "updated_at": "2026-07-01T12:34:56.789..."
}
```

## How the Backend Loads Settings

The backend (`reverie/backend_server/utils.py`) automatically:
1. Checks if `inference_settings.json` exists
2. Reads `host_id`, `model`, and `profile` fields
3. Maps `host_id` to the correct API endpoint:
   - `ollama-remote` → `http://Desktop-HomePC.local:11434/v1`
   - `vmlx-local-quality` → `http://Jamess-MacBook-Pro-2.local:8001/v1`
   - `vmlx-local-fast` → `http://Jamess-MacBook-Pro-2.local:8002/v1`
4. Falls back to defaults if not set:
   - Host: `ollama-remote`
   - Model: `qwen2.5-coder-14b`
   - Profile: `chat-large`

When you start the backend, it will use whichever settings were last saved via the UI.

## Recommended Configurations

### ✅ Best Quality: vMLX Qwen 27B (Local)
- **Host:** vMLX Quality (Local)
- **Model:** qwen:27b
- **Profile:** chat-large
- **Why:** Highest quality reasoning, best for complex persona psychology. Uses local Apple Silicon for fast inference with no network overhead.

### ⚡ Balanced: Ollama Qwen2.5-Coder (Remote)
- **Host:** Ollama (Remote)
- **Model:** qwen2.5-coder-14b
- **Profile:** chat-large
- **Why:** Good quality/speed tradeoff. Excellent at instruction following and JSON output. Uses CUDA GPU.

### 🚀 Fast: vMLX Gemma (Local)
- **Host:** vMLX Fast (Local)
- **Model:** gemma3:12b
- **Profile:** chat-large
- **Why:** Fastest inference for quick iterations. Good enough quality for testing. Local execution = no network delays.

### 🧪 Testing: Ollama Gemma4 (Remote)
- **Host:** Ollama (Remote)
- **Model:** gemma4:7b or gemma4:13b
- **Profile:** chat-small (for 7B) or chat-large (for 13B)
- **Why:** Lightweight, good for quick tests or low-resource scenarios

## Testing

To verify a host is reachable and list models manually:

### Ollama (Remote)
```bash
curl http://Desktop-HomePC.local:11434/api/tags
```

### vMLX Quality (Local)
```bash
curl http://Jamess-MacBook-Pro-2.local:8001/api/tags
```

### vMLX Fast (Local)
```bash
curl http://Jamess-MacBook-Pro-2.local:8002/api/tags
```

## Troubleshooting

**Models not loading in UI?**
- Verify the host is reachable: `ping <hostname>` (e.g., `ping Desktop-HomePC.local`)
- Check the LLM service is running on that host
- Verify the endpoint responds: `curl http://<host>:port/api/tags`
- Check browser console for network errors

**Backend not using selected settings?**
- Verify `inference_settings.json` exists and has `host_id`, `model`, and `profile` fields
- Restart the backend process (it reads the config at startup)
- Check backend logs to see which host/model/profile it loaded
- Verify the selected host is reachable from the backend's network

**Models available on one host but not the other?**
- Different hosts have different models installed
- Use the UI to switch hosts and see what's available
- Install missing models on the desired host first

**Model works but output is poor/malformed?**
- Try a different prompt profile (some models work better with different structures)
- Switch to a larger/more capable model
- Check if the model is instruct-tuned (required for structured output like JSON)
- Increase max_tokens in gpt_structure.py if responses are truncated
- Try switching between local (vMLX) and remote (Ollama) hosts to compare quality/speed
