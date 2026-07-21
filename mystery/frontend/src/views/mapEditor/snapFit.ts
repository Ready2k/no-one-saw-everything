// Snap-to-structure: refine a rough location box so its perimeter hugs the
// building outline in the underlay art. The art's structures have strong
// dark wall/stone edges, so we maximise the image gradient component normal
// to the box perimeter, hill-climbing centre / half-extents / rotation in a
// small neighbourhood of the rough placement.

import { Bounds, clamp } from "./editorTypes";

export interface SnapUnderlayTile {
  img: HTMLImageElement;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface RectParams {
  cx: number;
  cy: number;
  hw: number;
  hh: number;
  rot: number;
}

const PPT = 8; // sampled px per world tile (art is 32; 4x downscale smooths noise)
const EDGE_SAMPLE_STEP = 0.15; // tiles between perimeter samples
const POS_RANGE = 2.5; // how far (tiles) the centre may wander from the rough box
const SIZE_RANGE = 2.5; // how much each half-extent may change (tiles)
const ROT_RANGE = 12; // degrees of rotation freedom around the rough angle

export interface SnapResult {
  bounds: Bounds;
  gain: number; // score(final) / score(initial); > 1 means a stronger edge fit
}

export function snapBoundsToStructure(
  bounds: Bounds,
  tiles: SnapUnderlayTile[],
  gridCols: number,
  gridRows: number
): SnapResult | null {
  const margin = Math.max(bounds.w, bounds.h) * 0.6 + 2;
  const wx0 = Math.max(0, bounds.x - margin);
  const wy0 = Math.max(0, bounds.y - margin);
  const wx1 = Math.min(gridCols, bounds.x + bounds.w + margin);
  const wy1 = Math.min(gridRows, bounds.y + bounds.h + margin);
  const W = Math.round((wx1 - wx0) * PPT);
  const H = Math.round((wy1 - wy0) * PPT);
  if (W < 24 || H < 24) return null;

  const cv = document.createElement("canvas");
  cv.width = W;
  cv.height = H;
  const ctx = cv.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  ctx.imageSmoothingEnabled = true;
  let drew = false;
  for (const t of tiles) {
    if (t.x + t.w <= wx0 || t.x >= wx1 || t.y + t.h <= wy0 || t.y >= wy1) continue;
    if (!t.img.complete || !t.img.naturalWidth) continue;
    ctx.drawImage(t.img, (t.x - wx0) * PPT, (t.y - wy0) * PPT, t.w * PPT, t.h * PPT);
    drew = true;
  }
  if (!drew) return null;

  const data = ctx.getImageData(0, 0, W, H).data;
  const gray = new Float32Array(W * H);
  for (let i = 0; i < W * H; i++) {
    gray[i] = 0.299 * data[i * 4] + 0.587 * data[i * 4 + 1] + 0.114 * data[i * 4 + 2];
  }
  // Sobel gradients
  const gxA = new Float32Array(W * H);
  const gyA = new Float32Array(W * H);
  for (let y = 1; y < H - 1; y++) {
    for (let x = 1; x < W - 1; x++) {
      const i = y * W + x;
      gxA[i] =
        gray[i - W + 1] + 2 * gray[i + 1] + gray[i + W + 1] -
        (gray[i - W - 1] + 2 * gray[i - 1] + gray[i + W - 1]);
      gyA[i] =
        gray[i + W - 1] + 2 * gray[i + W] + gray[i + W + 1] -
        (gray[i - W - 1] + 2 * gray[i - W] + gray[i - W + 1]);
    }
  }

  // Average |gradient · edge-normal| over perimeter samples.
  const score = (p: RectParams): number => {
    const r = (p.rot * Math.PI) / 180;
    const cos = Math.cos(r);
    const sin = Math.sin(r);
    let sum = 0;
    let n = 0;
    // Each side: [local edge start, local edge direction, local outward normal]
    const sides: Array<[number, number, number, number, number, number, number]> = [
      // lx0, ly0, dirX, dirY, len, normalX, normalY (all local)
      [-p.hw, -p.hh, 1, 0, p.hw * 2, 0, -1], // top
      [-p.hw, p.hh, 1, 0, p.hw * 2, 0, 1], // bottom
      [-p.hw, -p.hh, 0, 1, p.hh * 2, -1, 0], // left
      [p.hw, -p.hh, 0, 1, p.hh * 2, 1, 0] // right
    ];
    for (const [lx0, ly0, dx, dy, len, nx, ny] of sides) {
      const count = Math.max(6, Math.ceil(len / EDGE_SAMPLE_STEP));
      // Rotate the local normal into world space once per side
      const nwx = nx * cos - ny * sin;
      const nwy = nx * sin + ny * cos;
      for (let k = 0; k <= count; k++) {
        const t = (k / count) * len;
        const lx = lx0 + dx * t;
        const ly = ly0 + dy * t;
        const wxp = p.cx + lx * cos - ly * sin;
        const wyp = p.cy + lx * sin + ly * cos;
        const px = Math.round((wxp - wx0) * PPT);
        const py = Math.round((wyp - wy0) * PPT);
        n++;
        if (px < 1 || py < 1 || px >= W - 1 || py >= H - 1) continue;
        const i = py * W + px;
        sum += Math.abs(gxA[i] * nwx + gyA[i] * nwy);
      }
    }
    return n ? sum / n : 0;
  };

  const orig: RectParams = {
    cx: bounds.x + bounds.w / 2,
    cy: bounds.y + bounds.h / 2,
    hw: bounds.w / 2,
    hh: bounds.h / 2,
    rot: bounds.rotation || 0
  };
  const cur = { ...orig };
  const initial = score(cur) || 1e-6;
  let best = initial;

  const inLimits = (p: RectParams) =>
    Math.abs(p.cx - orig.cx) <= POS_RANGE &&
    Math.abs(p.cy - orig.cy) <= POS_RANGE &&
    Math.abs(p.hw - orig.hw) <= SIZE_RANGE &&
    Math.abs(p.hh - orig.hh) <= SIZE_RANGE &&
    p.hw >= Math.max(0.5, orig.hw * 0.5) &&
    p.hh >= Math.max(0.5, orig.hh * 0.5) &&
    Math.abs(p.rot - orig.rot) <= ROT_RANGE;

  const passes = [
    { pos: 0.5, size: 0.5, rot: 2 },
    { pos: 0.25, size: 0.25, rot: 1 },
    { pos: 0.1, size: 0.1, rot: 0.5 }
  ];
  for (const pass of passes) {
    for (let iter = 0; iter < 30; iter++) {
      let improved = false;
      const params: Array<[keyof RectParams, number]> = [
        ["cx", pass.pos],
        ["cy", pass.pos],
        ["hw", pass.size],
        ["hh", pass.size],
        ["rot", pass.rot]
      ];
      for (const [key, step] of params) {
        for (const dir of [1, -1]) {
          const trial = { ...cur, [key]: cur[key] + dir * step };
          if (!inLimits(trial)) continue;
          const s = score(trial);
          if (s > best) {
            best = s;
            cur[key] = trial[key];
            improved = true;
          }
        }
      }
      if (!improved) break;
    }
  }

  const round1 = (v: number) => Math.round(v * 10) / 10;
  const w = round1(cur.hw * 2);
  const h = round1(cur.hh * 2);
  const x = clamp(round1(cur.cx - cur.hw), 0, gridCols - w);
  const y = clamp(round1(cur.cy - cur.hh), 0, gridRows - h);
  const rot = Math.round(cur.rot * 2) / 2;
  const out: Bounds = { x, y, w, h };
  if (rot !== 0) out.rotation = rot;
  return { bounds: out, gain: best / initial };
}
