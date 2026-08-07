#!/usr/bin/env bash
# Builds three ≤30 second, royalty-free promos from the game's own art, UI captures,
# and bundled audio. Run from the repository root: ./scripts/promo/create_teasers.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/marketing/promo"
WORK="$OUT/.work"
FONT_SERIF="/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
FONT_SANS="/System/Library/Fonts/Supplemental/Arial Bold.ttf"

mkdir -p "$OUT" "$WORK"
rm -f "$WORK"/*.mp4 "$WORK"/*.txt

require() { command -v "$1" >/dev/null || { echo "Missing required command: $1" >&2; exit 1; }; }
require ffmpeg
require ffprobe

# Arguments: input, seconds, output, width, height, heading, subheading, style
make_clip() {
  local input="$1" duration="$2" output="$3" width="$4" height="$5" heading="$6" subheading="$7" style="$8"
  local vf
  # A restrained slow push gives still assets movement without pretending they are gameplay.
  vf="scale=${width}:${height}:force_original_aspect_ratio=increase,crop=${width}:${height},zoompan=z='min(zoom+0.00055,1.12)':d=${duration}*30:s=${width}x${height}:fps=30,"
  local fade_start
  fade_start=$(awk "BEGIN {print $duration - 0.45}")
  vf+="eq=contrast=1.08:brightness=-0.025:saturation=0.88,fade=t=in:st=0:d=0.45,fade=t=out:st=${fade_start}:d=0.45"
  if [[ "$style" == "cinema" ]]; then
    vf+=",drawbox=x=0:y=0:w=iw:h=ih:color=black@0.18:t=fill,drawtext=fontfile=${FONT_SERIF}:text='${heading}':fontcolor=0xF3E7C6:fontsize=$((width/24)):x=(w-text_w)/2:y=h*0.73:shadowcolor=black@0.85:shadowx=3:shadowy=3,drawtext=fontfile=${FONT_SANS}:text='${subheading}':fontcolor=0xD6C5A0:fontsize=$((width/58)):x=(w-text_w)/2:y=h*0.81:shadowcolor=black@0.9:shadowx=2:shadowy=2"
  elif [[ "$style" == "short" ]]; then
    vf+=",drawbox=x=0:y=ih*0.64:w=iw:h=ih*0.23:color=black@0.58:t=fill,drawtext=fontfile=${FONT_SANS}:text='${heading}':fontcolor=white:fontsize=$((width/12)):x=(w-text_w)/2:y=h*0.67:shadowcolor=black@1:shadowx=3:shadowy=3,drawtext=fontfile=${FONT_SANS}:text='${subheading}':fontcolor=0xE7BD65:fontsize=$((width/23)):x=(w-text_w)/2:y=h*0.79:shadowcolor=black@1:shadowx=2:shadowy=2"
  else
    vf+=",drawbox=x=0:y=ih*0.72:w=iw:h=ih*0.20:color=0x10121A@0.82:t=fill,drawtext=fontfile=${FONT_SANS}:text='${heading}':fontcolor=0xF2D489:fontsize=$((width/29)):x=w*0.055:y=h*0.755:shadowcolor=black@1:shadowx=3:shadowy=3,drawtext=fontfile=${FONT_SANS}:text='${subheading}':fontcolor=white:fontsize=$((width/57)):x=w*0.057:y=h*0.835:shadowcolor=black@1:shadowx=2:shadowy=2"
  fi
  ffmpeg -y -loglevel error -loop 1 -i "$input" -t "$duration" -vf "$vf" -r 30 -pix_fmt yuv420p -c:v libx264 -crf 18 -preset medium "$output"
}

join_with_audio() {
  local name="$1" audio="$2" volume="$3"; shift 3
  local list="$WORK/${name}.txt"
  : > "$list"
  local clip
  for clip in "$@"; do printf "file '%s'\n" "$clip" >> "$list"; done
  ffmpeg -y -loglevel error -f concat -safe 0 -i "$list" -stream_loop -1 -i "$audio" \
    -filter_complex "[1:a]volume=${volume},afade=t=in:st=0:d=0.35,afade=t=out:st=27.2:d=0.8[a]" \
    -map 0:v -map '[a]' -t 28 -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k -movflags +faststart "$OUT/${name}.mp4"
}

ART="$ROOT/frontend/public/art/case_001"
MANUAL="$ROOT/frontend/public/manual"
AUDIO="$ROOT/frontend/public/audio"

# 1. Cinematic mystery — 16:9, 28 seconds. Best for pre-roll and a store-page hero.
make_clip "$ART/village_square_dawn_hd.avif" 5.5 "$WORK/cinematic_01.mp4" 1920 1080 "A village keeps its secrets" "ONE MORNING. ONE MURDER." cinema
make_clip "$ART/cafe_storage_room_hd.avif" 5.5 "$WORK/cinematic_02.mp4" 1920 1080 "Marcus Bell is dead" "THE CLOCK STOPPED AT 08.12" cinema
make_clip "$ART/rear_alley_investigation_v2.avif" 5.5 "$WORK/cinematic_03.mp4" 1920 1080 "Every witness has a story" "NOT EVERY STORY IS TRUE" cinema
make_clip "$ART/marcus_study_investigation_v2.avif" 5.5 "$WORK/cinematic_04.mp4" 1920 1080 "Find the contradiction" "BEFORE THE TRAIL GOES COLD" cinema
make_clip "$MANUAL/08-accuse-full.jpg" 6 "$WORK/cinematic_05.mp4" 1920 1080 "NO ONE SAW EVERYTHING" "COMING SOON" cinema
join_with_audio "teaser-01-cinematic" "$AUDIO/ambient/The_Last_Testimony.mp3" 0.75 "$WORK/cinematic_01.mp4" "$WORK/cinematic_02.mp4" "$WORK/cinematic_03.mp4" "$WORK/cinematic_04.mp4" "$WORK/cinematic_05.mp4"

# 2. Fast social Short — 9:16, 28 seconds. Designed for sound-on feeds, captions remain central.
make_clip "$MANUAL/00-intro-cinematic.jpg" 4.0 "$WORK/short_01.mp4" 1080 1920 "A MAN IS DEAD" "08.12. EVERYONE WAS THERE." short
make_clip "$MANUAL/06-suspects-full.jpg" 4.0 "$WORK/short_02.mp4" 1080 1920 "8 SUSPECTS" "ALL WITH SOMETHING TO HIDE" short
make_clip "$MANUAL/03-rewind-full.jpg" 4.0 "$WORK/short_03.mp4" 1080 1920 "REWIND THE MORNING" "WATCH WHAT THEY DID" short
make_clip "$MANUAL/04-map-full.jpg" 4.0 "$WORK/short_04.mp4" 1080 1920 "FOLLOW EVERY MOVE" "NO DETAIL IS TOO SMALL" short
make_clip "$MANUAL/07-board-full.jpg" 4.0 "$WORK/short_05.mp4" 1080 1920 "CONNECT THE LIES" "BUILD THE CASE" short
make_clip "$MANUAL/08-accuse-full.jpg" 8.0 "$WORK/short_06.mp4" 1080 1920 "WHO DID IT?" "NO ONE SAW EVERYTHING • COMING SOON" short
join_with_audio "teaser-02-social-short" "$AUDIO/ambient/investigation.mp3" 0.90 "$WORK/short_01.mp4" "$WORK/short_02.mp4" "$WORK/short_03.mp4" "$WORK/short_04.mp4" "$WORK/short_05.mp4" "$WORK/short_06.mp4"

# 3. Gameplay proof — 16:9, 28 seconds. Makes the unique investigation loop immediately legible.
make_clip "$MANUAL/02-overview-full.jpg" 4.5 "$WORK/gameplay_01.mp4" 1920 1080 "A fair-play murder mystery" "THE TRUTH IS LOCKED BEFORE YOU BEGIN" gameplay
make_clip "$MANUAL/03-rewind-full.jpg" 4.5 "$WORK/gameplay_02.mp4" 1920 1080 "1. REWIND" "OBSERVE THE MORNING, MINUTE BY MINUTE" gameplay
make_clip "$MANUAL/04-map-full.jpg" 4.5 "$WORK/gameplay_03.mp4" 1920 1080 "2. INVESTIGATE" "SEARCH THE VILLAGE FOR THE MISSING PIECE" gameplay
make_clip "$MANUAL/06-suspects-full.jpg" 4.5 "$WORK/gameplay_04.mp4" 1920 1080 "3. INTERROGATE" "PRESS THE STORY UNTIL IT CRACKS" gameplay
make_clip "$MANUAL/07-board-full.jpg" 4.5 "$WORK/gameplay_05.mp4" 1920 1080 "4. BUILD YOUR CASE" "CONNECT TESTIMONY, CLUES, AND CONTRADICTIONS" gameplay
make_clip "$MANUAL/08-accuse-full.jpg" 5.5 "$WORK/gameplay_06.mp4" 1920 1080 "MAKE THE ACCUSATION" "NO ONE SAW EVERYTHING • COMING SOON" gameplay
join_with_audio "teaser-03-gameplay" "$AUDIO/ambient/accusation.mp3" 0.77 "$WORK/gameplay_01.mp4" "$WORK/gameplay_02.mp4" "$WORK/gameplay_03.mp4" "$WORK/gameplay_04.mp4" "$WORK/gameplay_05.mp4" "$WORK/gameplay_06.mp4"

echo "Created:"
for file in "$OUT"/*.mp4; do
  printf '  %s — ' "$(basename "$file")"
  ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 "$file" | awk '{printf "%0.2fs\n", $1}'
done
