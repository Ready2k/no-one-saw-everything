// Ambient time-of-day tint for the map. Each keyframe is an RGB color applied
// via CSS `multiply` blend, so one number does double duty: a color near
// white leaves the map untouched (midday), while a darker/saturated color
// both dims and colors it (dusk, night) in a single composite pass.
type Keyframe = { t: number; rgb: [number, number, number] };

const KEYFRAMES: Keyframe[] = [
  { t: 0, rgb: [35, 38, 70] }, // midnight
  { t: 300, rgb: [35, 38, 70] }, // 05:00 — pre-dawn
  { t: 390, rgb: [150, 120, 140] }, // 06:30 — dawn
  { t: 480, rgb: [235, 215, 195] }, // 08:00 — early morning
  { t: 720, rgb: [255, 255, 250] }, // 12:00 — noon
  { t: 900, rgb: [255, 238, 205] }, // 15:00 — afternoon
  { t: 1050, rgb: [255, 185, 130] }, // 17:30 — early evening
  { t: 1170, rgb: [190, 110, 105] }, // 19:30 — dusk
  { t: 1260, rgb: [80, 65, 110] }, // 21:00 — night falls
  { t: 1440, rgb: [35, 38, 70] }, // wraps to midnight
];

function lerp(a: number, b: number, f: number): number {
  return a + (b - a) * f;
}

/** Multiply-blend tint for the map at a given minutes-since-midnight (wraps at 1440). */
export function lightingTint(minutesOfDay: number): string {
  const t = ((minutesOfDay % 1440) + 1440) % 1440;
  let i = 0;
  while (i < KEYFRAMES.length - 1 && KEYFRAMES[i + 1].t <= t) i++;
  const a = KEYFRAMES[i];
  const b = KEYFRAMES[Math.min(i + 1, KEYFRAMES.length - 1)];
  const span = b.t - a.t || 1;
  const f = (t - a.t) / span;
  const [r, g, bch] = [0, 1, 2].map((k) => Math.round(lerp(a.rgb[k], b.rgb[k], f)));
  return `rgb(${r}, ${g}, ${bch})`;
}
