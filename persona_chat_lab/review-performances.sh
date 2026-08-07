#!/usr/bin/env bash
set -euo pipefail

shopt -s nullglob
CLIPS=(/tmp/owen-*/*/owen_source--owen_{guarded,considering,answering}.mp4 /tmp/owen-*/owen_source--owen_{guarded,considering,answering}.mp4)

if [[ ${#CLIPS[@]} -eq 0 ]]; then
  echo "No Owen performance candidates found. Run the render step first."
  exit 1
fi

echo "Opening ${#CLIPS[@]} Owen performance candidate(s)…"
open "${CLIPS[@]}"
