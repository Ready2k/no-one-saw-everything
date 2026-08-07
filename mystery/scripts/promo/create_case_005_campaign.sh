#!/usr/bin/env bash
# Builds the Case 005 YouTube campaign from player-safe game artwork.
# Run from the repository root: ./scripts/promo/create_case_005_campaign.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/marketing/promo/case_005"
WORK="$OUT/.work"
ART="$ROOT/frontend/public/art/case_005"
AUDIO="$ROOT/frontend/public/audio/ambient"
FONT_SERIF="/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
FONT_SANS="/System/Library/Fonts/Supplemental/Arial Bold.ttf"

mkdir -p "$OUT" "$WORK"
rm -f "$WORK"/*.mp4 "$WORK"/*.txt

# One rendered, captioned still.  The modest push-in keeps the films lively
# while retaining a clean, readable frame for YouTube's silent autoplay.
clip() {
  local input="$1" duration="$2" output="$3" width="$4" height="$5"
  local headline="$6" subhead="$7" style="$8"
  local fade_start text_size sub_size
  fade_start=$(awk "BEGIN {print $duration - 0.35}")
  if [[ "$style" == "short" ]]; then
    text_size=$((width / 15)); sub_size=$((width / 29))
  else
    text_size=$((width / 21)); sub_size=$((width / 46))
  fi
  ffmpeg -y -loglevel error -loop 1 -i "$input" -t "$duration" \
    -vf "scale=${width}:${height}:force_original_aspect_ratio=increase,crop=${width}:${height},zoompan=z='min(zoom+0.0007,1.16)':d=${duration}*30:s=${width}x${height}:fps=30,eq=contrast=1.10:brightness=-0.03:saturation=0.94,drawbox=x=0:y=ih*0.68:w=iw:h=ih*0.22:color=0x030814@0.75:t=fill,drawtext=fontfile=${FONT_SERIF}:text='${headline}':fontcolor=0xF6E6C0:fontsize=${text_size}:x=(w-text_w)/2:y=h*0.715:shadowcolor=black@1:shadowx=3:shadowy=3,drawtext=fontfile=${FONT_SANS}:text='${subhead}':fontcolor=0xE9B85C:fontsize=${sub_size}:x=(w-text_w)/2:y=h*0.815:shadowcolor=black@1:shadowx=2:shadowy=2,fade=t=in:st=0:d=0.35,fade=t=out:st=${fade_start}:d=0.35" \
    -r 30 -pix_fmt yuv420p -c:v libx264 -crf 18 -preset medium "$output"
}

finish() {
  local name="$1" audio="$2" volume="$3"; shift 3
  local list="$WORK/${name}.txt"
  : > "$list"
  local source
  for source in "$@"; do printf "file '%s'\n" "$source" >> "$list"; done
  ffmpeg -y -loglevel error -f concat -safe 0 -i "$list" -stream_loop -1 -i "$audio" \
    -filter_complex "[1:a]volume=${volume},afade=t=in:st=0:d=0.35,afade=t=out:st=26.1:d=0.9[a]" \
    -map 0:v -map '[a]' -t 27 -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k -movflags +faststart "$OUT/${name}.mp4"
}

# Short 01 — immediate crime-scene hook.
clip "$ART/rear_alley_fire_hd.avif" 5 "$WORK/alley_01.mp4" 1080 1920 "A FIRE HIDES NOTHING" "NOT IN THIS VILLAGE" short
clip "$ART/evidence/melted_lighter.avif" 5 "$WORK/alley_02.mp4" 1080 1920 "LOOK CLOSER" "EVERY OBJECT HAS A STORY" short
clip "$ART/map/case_005_village_map_dawn.avif" 5 "$WORK/alley_03.mp4" 1080 1920 "FOLLOW THE ROUTE" "THE BACK LANE SAW NO ONE" short
clip "$ART/portraits/owen_price_cracking.avif" 5 "$WORK/alley_04.mp4" 1080 1920 "PRESS THE LIE" "WATCH THE STORY CHANGE" short
clip "$ART/overhead/rear_alley_overhead_dawn.avif" 7 "$WORK/alley_05.mp4" 1080 1920 "NO ONE SAW EVERYTHING" "PLAY THE CASE" short
finish "case-005-short-01-fire" "$AUDIO/investigation.mp3" 0.88 "$WORK/alley_01.mp4" "$WORK/alley_02.mp4" "$WORK/alley_03.mp4" "$WORK/alley_04.mp4" "$WORK/alley_05.mp4"

# Short 02 — character-led, designed to hold without sound.
clip "$ART/portraits/ben_carter_defensive.avif" 5 "$WORK/witness_01.mp4" 1080 1920 "EVERYONE REMEMBERS" "SOMETHING DIFFERENT" short
clip "$ART/portraits/nadia_cole_defensive.avif" 5 "$WORK/witness_02.mp4" 1080 1920 "ASK AGAIN" "LISTEN FOR THE PAUSE" short
clip "$ART/portraits/elias_grant_cracking.avif" 5 "$WORK/witness_03.mp4" 1080 1920 "THEIR FACES CHANGE" "WHEN THE EVIDENCE FITS" short
clip "$ART/evidence/mortgage_deed.avif" 5 "$WORK/witness_04.mp4" 1080 1920 "BUILD THE CASE" "ONE CLUE AT A TIME" short
clip "$ART/village_square_dawn_hd.avif" 7 "$WORK/witness_05.mp4" 1080 1920 "NO ONE SAW EVERYTHING" "A FAIR-PLAY MYSTERY" short
finish "case-005-short-02-witnesses" "$AUDIO/The_Clock_Across_The_Room.mp3" 0.84 "$WORK/witness_01.mp4" "$WORK/witness_02.mp4" "$WORK/witness_03.mp4" "$WORK/witness_04.mp4" "$WORK/witness_05.mp4"

# Trailer — geographic, investigative, then psychological escalation.
clip "$ART/map/case_005_village_map_dawn.avif" 7 "$WORK/trailer_01.mp4" 1920 1080 "ONE VILLAGE" "ONE UNSEEN ROUTE" trailer
clip "$ART/rear_alley_fire_hd.avif" 7 "$WORK/trailer_02.mp4" 1920 1080 "ONE MORNING TO REWIND" "THE REAR ALLEY FIRE WAS NO ACCIDENT" trailer
clip "$ART/evidence/builders_belt.avif" 6 "$WORK/trailer_03.mp4" 1920 1080 "EVERY CLUE CONNECTS" "IF YOU KNOW WHERE TO LOOK" trailer
clip "$ART/portraits/owen_price_cracking.avif" 7 "$WORK/trailer_04.mp4" 1920 1080 "NO ONE SAW EVERYTHING" "PLAY THE CASE" trailer
finish "case-005-trailer-rear-alley-fire" "$AUDIO/The_Last_Testimony.mp3" 0.80 "$WORK/trailer_01.mp4" "$WORK/trailer_02.mp4" "$WORK/trailer_03.mp4" "$WORK/trailer_04.mp4"

for file in "$OUT"/*.mp4; do
  printf '%s — ' "$(basename "$file")"
  ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 "$file" | awk '{printf "%0.2fs\\n", $1}'
done
