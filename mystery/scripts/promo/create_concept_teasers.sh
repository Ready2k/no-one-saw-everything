#!/usr/bin/env bash
# Builds the original-art concept campaign. Run from repository root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/marketing/promo/concept"
WORK="$OUT/.work"
ART="$ROOT/marketing/promo/original-art"
FONT_SERIF="/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
FONT_SANS="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
mkdir -p "$OUT" "$WORK"
rm -f "$WORK"/*.mp4 "$WORK"/*.txt

# input duration output width height headline subhead treatment
clip() {
  local input="$1" duration="$2" output="$3" width="$4" height="$5" headline="$6" subhead="$7" treatment="$8"
  local fade_start vf
  fade_start=$(awk "BEGIN {print $duration - 0.35}")
  vf="scale=${width}:${height}:force_original_aspect_ratio=increase,crop=${width}:${height},zoompan=z='min(zoom+0.00065,1.15)':d=${duration}*30:s=${width}x${height}:fps=30,eq=contrast=1.12:brightness=-0.03:saturation=0.95,fade=t=in:st=0:d=0.35,fade=t=out:st=${fade_start}:d=0.35"
  if [[ "$treatment" == "short" ]]; then
    vf+=",drawbox=x=0:y=ih*0.68:w=iw:h=ih*0.20:color=0x030814@0.76:t=fill,drawtext=fontfile=${FONT_SANS}:text='${headline}':fontcolor=0xF8F1E4:fontsize=$((width/17)):x=(w-text_w)/2:y=h*0.715:shadowcolor=black@1:shadowx=3:shadowy=3,drawtext=fontfile=${FONT_SANS}:text='${subhead}':fontcolor=0xE9B85C:fontsize=$((width/30)):x=(w-text_w)/2:y=h*0.80:shadowcolor=black@1:shadowx=2:shadowy=2"
  else
    vf+=",drawbox=x=0:y=ih*0.68:w=iw:h=ih*0.21:color=0x030814@0.72:t=fill,drawtext=fontfile=${FONT_SERIF}:text='${headline}':fontcolor=0xF6E6C0:fontsize=$((width/23)):x=(w-text_w)/2:y=h*0.715:shadowcolor=black@1:shadowx=3:shadowy=3,drawtext=fontfile=${FONT_SANS}:text='${subhead}':fontcolor=0xE9B85C:fontsize=$((width/48)):x=(w-text_w)/2:y=h*0.815:shadowcolor=black@1:shadowx=2:shadowy=2"
  fi
  ffmpeg -y -loglevel error -loop 1 -i "$input" -t "$duration" -vf "$vf" -r 30 -pix_fmt yuv420p -c:v libx264 -crf 18 -preset medium "$output"
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

AUDIO="$ROOT/frontend/public/audio/ambient"

# Short 1: the high-concept mechanic hook.
clip "$ART/short-rewind-key-art.png" 5 "$WORK/rewind_01.mp4" 1080 1920 "THE CLOCK STOPPED" "AT 08.12" short
clip "$ART/short-rewind-key-art.png" 5 "$WORK/rewind_02.mp4" 1080 1920 "SO DID THE TRUTH" "EVERYONE REMEMBERS IT DIFFERENTLY" short
clip "$ART/short-rewind-key-art.png" 5 "$WORK/rewind_03.mp4" 1080 1920 "REWIND THE MORNING" "FOLLOW EVERY FOOTSTEP" short
clip "$ART/short-rewind-key-art.png" 5 "$WORK/rewind_04.mp4" 1080 1920 "FIND THE LIE" "BEFORE IT DISAPPEARS" short
clip "$ART/short-rewind-key-art.png" 7 "$WORK/rewind_05.mp4" 1080 1920 "NO ONE SAW EVERYTHING" "A MURDER MYSTERY GAME" short
finish "short-01-rewind" "$AUDIO/investigation.mp3" 0.88 "$WORK/rewind_01.mp4" "$WORK/rewind_02.mp4" "$WORK/rewind_03.mp4" "$WORK/rewind_04.mp4" "$WORK/rewind_05.mp4"

# Short 2: psychological hook, designed to be silent-viewing friendly.
clip "$ART/short-shadows-key-art.png" 5 "$WORK/shadows_01.mp4" 1080 1920 "THEY ALL SAW SOMETHING" "OR SO THEY SAY" short
clip "$ART/short-shadows-key-art.png" 5 "$WORK/shadows_02.mp4" 1080 1920 "THREE STORIES" "ONE DEAD MAN" short
clip "$ART/short-shadows-key-art.png" 5 "$WORK/shadows_03.mp4" 1080 1920 "WATCH THEIR SHADOWS" "THEY NEVER LIE" short
clip "$ART/short-shadows-key-art.png" 5 "$WORK/shadows_04.mp4" 1080 1920 "PICK A SUSPECT" "THEN PROVE IT" short
clip "$ART/short-shadows-key-art.png" 7 "$WORK/shadows_05.mp4" 1080 1920 "NO ONE SAW EVERYTHING" "COMING SOON" short
finish "short-02-shadows" "$AUDIO/The_Clock_Across_The_Room.mp3" 0.86 "$WORK/shadows_01.mp4" "$WORK/shadows_02.mp4" "$WORK/shadows_03.mp4" "$WORK/shadows_04.mp4" "$WORK/shadows_05.mp4"

# Trailer: a slower, premium promise; the portrait art becomes a deliberately graphic montage.
clip "$ART/trailer-village-key-art.png" 7 "$WORK/trailer_01.mp4" 1920 1080 "A VILLAGE OF WITNESSES" "EVERYONE HAS A VERSION OF THE MORNING" trailer
clip "$ART/short-rewind-key-art.png" 7 "$WORK/trailer_02.mp4" 1920 1080 "ONE MORNING TO REWIND" "EVERY MINUTE LEAVES A TRACE" trailer
clip "$ART/short-shadows-key-art.png" 7 "$WORK/trailer_03.mp4" 1920 1080 "ONE LIE TO FIND" "THE SHADOWS KNOW WHAT HAPPENED" trailer
clip "$ART/trailer-village-key-art.png" 7 "$WORK/trailer_04.mp4" 1920 1080 "NO ONE SAW EVERYTHING" "A FAIR-PLAY MURDER MYSTERY • COMING SOON" trailer
finish "trailer-01-no-one-saw" "$AUDIO/The_Last_Testimony.mp3" 0.80 "$WORK/trailer_01.mp4" "$WORK/trailer_02.mp4" "$WORK/trailer_03.mp4" "$WORK/trailer_04.mp4"

for file in "$OUT"/*.mp4; do
  printf '%s — ' "$(basename "$file")"
  ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 "$file" | awk '{printf "%0.2fs\n", $1}'
done
