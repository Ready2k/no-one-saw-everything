#!/usr/bin/env bash
set -euo pipefail

# Case 005 is set outside at wet dawn. Keep the rain low, broad and irregular:
# this deliberately avoids the full-band white-noise bed that reads as static.
root_dir="$(cd "$(dirname "$0")/../.." && pwd)"
output="$root_dir/frontend/public/audio/ambient/case_005_rain_dawn_balanced.mp3"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "anoisesrc=color=pink:amplitude=0.72:sample_rate=44100:duration=90" \
  -f lavfi -i "anoisesrc=color=brown:amplitude=0.75:sample_rate=44100:duration=90" \
  -f lavfi -i "anoisesrc=color=white:amplitude=0.4:sample_rate=44100:duration=90" \
  -f lavfi -i "sine=frequency=38:sample_rate=44100:duration=90" \
  -filter_complex "
    [0:a]highpass=f=520,lowpass=f=6700,volume=0.18,pan=stereo|c0=0.92*c0|c1=0.62*c0[rain];
    [1:a]lowpass=f=260,volume=0.11,pan=stereo|c0=0.65*c0|c1=0.9*c0[wind];
    [2:a]highpass=f=1850,lowpass=f=5000,tremolo=f=0.1:d=0.45,volume=0.045,pan=stereo|c0=0.42*c0|c1=0.78*c0[wet_ground];
    [3:a]volume='if(between(t,24,31),0.16*exp(-0.65*(t-24)),if(between(t,63,71),0.12*exp(-0.58*(t-63)),0))',aecho=0.8:0.55:240|490:0.35|0.18,pan=stereo|c0=0.78*c0|c1=0.9*c0[thunder];
    [rain][wind][wet_ground][thunder]amix=inputs=4:normalize=0,volume=2.6,alimiter=limit=0.89[out]" \
  -map "[out]" -ac 2 -ar 44100 -c:a libmp3lame -b:a 160k "$output"

echo "Created $output"
