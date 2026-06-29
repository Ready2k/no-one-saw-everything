#!/usr/bin/env bash
# Starts the generative-agents reverie simulation server (interactive).
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$REPO/.venv/bin/python"
STORAGE="$REPO/environment/frontend_server/storage"

# ── List available simulations ────────────────────────────────────────────────
echo ""
echo "Available simulations to fork from:"
echo "────────────────────────────────────"
SIMS=()
while IFS= read -r line; do
  SIMS+=("$line")
done < <(ls -1 "$STORAGE" | sort)

for i in "${!SIMS[@]}"; do
  printf "  [%2d] %s\n" "$((i+1))" "${SIMS[$i]}"
done
echo ""

# ── Fork name: accept number or name ─────────────────────────────────────────
read -rp "Enter number or name of simulation to fork from: " FORK_INPUT

if [[ "$FORK_INPUT" =~ ^[0-9]+$ ]]; then
  IDX=$(( FORK_INPUT - 1 ))
  if [[ $IDX -lt 0 || $IDX -ge ${#SIMS[@]} ]]; then
    echo "Invalid number. Exiting." && exit 1
  fi
  FORK="${SIMS[$IDX]}"
  echo "  → $FORK"
else
  FORK="$FORK_INPUT"
fi

# ── New simulation name with timestamped default ──────────────────────────────
DEFAULT_NAME="${FORK}-run-$(date +%Y%m%d-%H%M)"
echo ""
read -rp "Enter name for new simulation [${DEFAULT_NAME}]: " NEW_NAME
NEW_NAME="${NEW_NAME:-$DEFAULT_NAME}"

# Warn if spaces in name (URLs are cleaner with hyphens, but spaces now work)
if [[ "$NEW_NAME" == *" "* ]]; then
  echo "  ⚠  Note: simulation name contains spaces — these are allowed but hyphens are tidier in URLs."
fi

MODEL=$(grep '^local_model' "$REPO/reverie/backend_server/utils.py" | grep -o '"[^"]*"' | head -1)

# ── LLM Profile selector ──────────────────────────────────────────────────────
echo ""
echo "Select LLM profile:"
echo "  [1] chat-small  — local small model (e.g. Gemma 4B)"
echo "  [2] chat-large  — local large model (e.g. Qwen 14B)"
echo "  [3] gpt         — OpenAI GPT-3.5/4 via API"
echo "  [4] cloud       — Cloud API (OpenAI / Gemini / Claude)"
echo ""
read -rp "Enter profile number or name [1]: " PROFILE_INPUT

case "$PROFILE_INPUT" in
  2|chat-large)  PROMPT_PROFILE="chat-large" ;;
  3|gpt)         PROMPT_PROFILE="gpt" ;;
  4|cloud)       PROMPT_PROFILE="cloud" ;;
  *)             PROMPT_PROFILE="chat-small" ;;
esac
export PROMPT_PROFILE

# For cloud profile, remind user to check .env
if [[ "$PROMPT_PROFILE" == "cloud" ]]; then
  ENV_FILE="$REPO/.env"
  if [[ ! -f "$ENV_FILE" ]]; then
    echo ""
    echo "  ⚠  No .env file found at project root. Cloud API keys are needed."
    echo "     Create $ENV_FILE with OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY."
    echo ""
  fi
fi

echo ""
echo "Forking:  $FORK"
echo "New name: $NEW_NAME"
echo "Model:    $MODEL"
echo "Profile:  $PROMPT_PROFILE"
echo "────────────────────────────────────"
echo ""

# Write the chosen profile so the Django frontend can display it
TEMP_STORAGE="$REPO/environment/frontend_server/temp_storage"
mkdir -p "$TEMP_STORAGE"
printf '{"profile": "%s"}' "$PROMPT_PROFILE" > "$TEMP_STORAGE/llm_profile.json"

cd "$REPO/reverie/backend_server"
# Feed the two setup answers, then hand stdin back to the terminal
# so the interactive "Enter option:" loop keeps working.
{ printf '%s\n%s\n' "$FORK" "$NEW_NAME"; cat; } | PYTHONPATH=. PROMPT_PROFILE="$PROMPT_PROFILE" "$PYTHON" reverie.py
