#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PUBLIC_DIR="$PROJECT_DIR/frontend/public"
CONFIG="$SCRIPT_DIR/confessions.json"
OPEN_FOLDER="$PUBLIC_DIR/art/ui/detective-desk-case-file-open-v1.avif"
CLOSED_FOLDER="$PUBLIC_DIR/art/ui/detective-desk-case-file-closed-v1.avif"
MUSIC="$PUBLIC_DIR/audio/ambient/The_Last_Testimony.mp3"

if (( $# > 0 )); then
  case_ids=("$@")
else
  case_ids=()
  while IFS= read -r configured_case_id; do
    case_ids+=("$configured_case_id")
  done < <(jq -r 'keys[]' "$CONFIG")
fi

for case_id in "${case_ids[@]}"; do
  if ! jq -e --arg id "$case_id" 'has($id)' "$CONFIG" >/dev/null; then
    echo "Unknown confession case: $case_id" >&2
    exit 1
  fi

  work_dir="$(mktemp -d)"
  title="$(jq -r --arg id "$case_id" '.[$id].title' "$CONFIG")"
  killer="$(jq -r --arg id "$case_id" '.[$id].killer' "$CONFIG")"
  victim="$(jq -r --arg id "$case_id" '.[$id].victim' "$CONFIG")"
  file_number="${case_id#case_}"
  output="$PUBLIC_DIR/cinematics/${case_id//_/-}-confession.mp4"

  beats=()
  while IFS= read -r beat; do
    beats+=("$beat")
  done < <(jq -r --arg id "$case_id" '.[$id].beats[]' "$CONFIG")
  configured_images=()
  while IFS= read -r configured_image; do
    configured_images+=("$configured_image")
  done < <(jq -r --arg id "$case_id" '.[$id].images[]' "$CONFIG")
  if (( ${#beats[@]} != 8 || ${#configured_images[@]} != 8 )); then
    echo "$case_id must define exactly eight beats and eight images" >&2
    exit 1
  fi

  images=("$OPEN_FOLDER")
  for image in "${configured_images[@]}"; do
    images+=("$PUBLIC_DIR/$image")
  done
  images+=("$CLOSED_FOLDER")

  for image in "${images[@]}"; do
    if [[ ! -f "$image" ]]; then
      echo "Missing confession image: $image" >&2
      exit 1
    fi
  done

  : > "$work_dir/scenes.txt"
  for index in "${!images[@]}"; do
    ffmpeg -y -loglevel error \
      -loop 1 -t 7 -i "${images[$index]}" \
      -vf "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fade=t=in:st=0:d=0.55,fade=t=out:st=6.45:d=0.55,format=yuv420p" \
      -an -c:v libx264 -preset veryfast -crf 18 -r 30 \
      "$work_dir/scene_${index}.mp4"
    printf "file '%s'\n" "$work_dir/scene_${index}.mp4" >> "$work_dir/scenes.txt"
  done
  ffmpeg -y -loglevel error -f concat -safe 0 -i "$work_dir/scenes.txt" -c copy "$work_dir/picture.mp4"

  : > "$work_dir/audio.txt"
  ffmpeg -y -loglevel error -f lavfi -i anullsrc=r=44100:cl=stereo -t 7 -c:a pcm_s16le "$work_dir/voice_0.wav"
  printf "file '%s'\n" "$work_dir/voice_0.wav" >> "$work_dir/audio.txt"
  for index in "${!beats[@]}"; do
    printf '%s\n' "${beats[$index]}" > "$work_dir/beat.txt"
    say -v Daniel -r 175 -f "$work_dir/beat.txt" -o "$work_dir/beat.aiff"
    beat_duration="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$work_dir/beat.aiff")"
    if awk -v duration="$beat_duration" 'BEGIN { exit !(duration > 6.9) }'; then
      echo "$case_id beat $((index + 1)) is too long for its scene (${beat_duration}s)" >&2
      exit 1
    fi
    audio_index=$((index + 1))
    ffmpeg -y -loglevel error -i "$work_dir/beat.aiff" \
      -af "apad=whole_dur=7" -t 7 -ar 44100 -ac 2 -c:a pcm_s16le \
      "$work_dir/voice_${audio_index}.wav"
    printf "file '%s'\n" "$work_dir/voice_${audio_index}.wav" >> "$work_dir/audio.txt"
  done
  ffmpeg -y -loglevel error -f lavfi -i anullsrc=r=44100:cl=stereo -t 7 -c:a pcm_s16le "$work_dir/voice_9.wav"
  printf "file '%s'\n" "$work_dir/voice_9.wav" >> "$work_dir/audio.txt"
  ffmpeg -y -loglevel error -f concat -safe 0 -i "$work_dir/audio.txt" -c copy "$work_dir/narration.wav"

  ass_file="$work_dir/confession.ass"
  title_upper="$(printf '%s' "$title" | tr '[:lower:]' '[:upper:]')"
  killer_upper="$(printf '%s' "$killer" | tr '[:lower:]' '[:upper:]')"
  {
    printf '%s\n' '[Script Info]' "Title: $killer Confession" 'ScriptType: v4.00+' 'PlayResX: 1920' 'PlayResY: 1080' 'WrapStyle: 0' ''
    printf '%s\n' '[V4+ Styles]' 'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding'
    printf '%s\n' 'Style: Confession,Georgia,54,&H00F3E8D0,&H000000FF,&H00100C08,&H9A000000,-1,0,0,0,100,100,0,0,3,2,1,2,150,150,74,1'
    printf '%s\n' 'Style: Card,Georgia,66,&H00D3A755,&H000000FF,&H00100C08,&H00000000,-1,0,0,0,100,100,2,0,1,3,1,5,100,100,100,1'
    printf '%s\n' 'Style: File,American Typewriter,42,&H00E8DEC8,&H000000FF,&H00100C08,&H88000000,0,0,0,0,100,100,3,0,3,1,1,5,120,120,100,1' ''
    printf '%s\n' '[Events]' 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'
    printf 'Dialogue: 2,0:00:00.70,0:00:06.20,File,,0,0,0,,%s\\NCASE FILE %s  •  RECORDED CONFESSION\\N%s — %s\n' "$title_upper" "$file_number" "$killer" "$victim"
    printf 'Dialogue: 1,0:00:07.00,0:00:10.20,Card,,0,0,0,,%s — CONFESSION\n' "$killer_upper"
    for index in "${!beats[@]}"; do
      start=$((7 + index * 7))
      end=$((start + 7))
      start_stamp="$(printf '0:%02d:%02d.00' $((start / 60)) $((start % 60)))"
      end_stamp="$(printf '0:%02d:%02d.00' $((end / 60)) $((end % 60)))"
      printf 'Dialogue: 0,%s,%s,Confession,,0,0,0,,%s\n' "$start_stamp" "$end_stamp" "${beats[$index]}"
    done
  } > "$ass_file"

  mkdir -p "$(dirname "$output")"
  ffmpeg -y -loglevel error \
    -i "$work_dir/picture.mp4" -i "$work_dir/narration.wav" -stream_loop -1 -i "$MUSIC" \
    -filter_complex "[1:a]volume=1.45[voice];[2:a]volume=0.085[music];[voice][music]amix=inputs=2:duration=first:normalize=0[a]" \
    -vf "ass='$ass_file'" -map 0:v -map "[a]" -t 70 \
    -c:v libx264 -preset fast -crf 19 -c:a aac -b:a 192k -movflags +faststart \
    "$output"

  rm -rf "$work_dir"
  echo "Created $output"
done
