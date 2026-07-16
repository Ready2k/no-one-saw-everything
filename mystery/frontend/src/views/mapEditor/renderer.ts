// Pure canvas renderer for the developer map editor.
// The component assembles a Scene each frame; this module only draws it.

import {
  ALLOWED_LAYERS,
  AMBIENT_ASSET_SWATCHES,
  Bounds,
  Camera,
  LIGHT_ASSET_SWATCHES,
  LocationSource,
  PROP_EMOJIS,
  SAFETY_MARGIN_TILES,
  TILE_COLORS,
  TileLayer
} from "./editorTypes";

export interface SceneLocation {
  id: string;
  name: string;
  bounds: Bounds;
  source: LocationSource;
  alpha: number;
  selected: boolean;
  hovered: boolean;
}

export interface SceneAnchor {
  id: string;
  name: string;
  x: number;
  y: number;
  alpha: number;
  selected: boolean;
}

export interface SceneLight {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  semanticAssetId: string;
  opacity?: number;
  selected: boolean;
}

export interface SceneAmbient {
  id: string;
  assetId: string;
  x: number;
  y: number;
  width: number;
  height: number;
  opacity?: number;
  selected: boolean;
}

export interface SceneProp {
  id: string;
  assetId: string;
  x: number;
  y: number;
  w: number;
  h: number;
  layer: string;
  selected: boolean;
  kind?: "prop" | "building";
  /** Building bundle art drawn over the footprint when loaded. */
  img?: HTMLImageElement;
  /** Clockwise 90° steps for building art (footprint w/h are pre-swapped). */
  rotation?: number;
}

/** One underlay image placed at a world-tile rectangle. */
export interface UnderlayDraw {
  img: HTMLImageElement;
  x: number;
  y: number;
  w: number;
  h: number;
}

export type ToolOverlay =
  | { kind: "brush"; cells: Array<{ x: number; y: number }>; erase: boolean }
  | { kind: "rect"; x: number; y: number; w: number; h: number; erase: boolean; tileId: string }
  | {
      kind: "propGhost";
      x: number;
      y: number;
      assetId: string;
      w?: number;
      h?: number;
      front?: "south" | "west" | "north" | "east";
      img?: HTMLImageElement;
      rotation?: number;
    }
  | null;

export interface Scene {
  cssW: number;
  cssH: number;
  dpr: number;
  camera: Camera;
  cols: number;
  rows: number;
  tileLayers: Record<string, TileLayer>;
  visibleLayers: Record<string, boolean>;
  underlays: UnderlayDraw[];
  underlayOpacity: number;
  solidRender: boolean;
  showGrid: boolean;
  showSafety: boolean;
  showLabels: boolean;
  locations: SceneLocation[];
  anchors: SceneAnchor[];
  props: SceneProp[];
  lights: SceneLight[];
  ambientSprites: SceneAmbient[];
  overlay: ToolOverlay;
}

const SOURCE_COLORS: Record<LocationSource, { border: string; fill: string }> = {
  recommended: { border: "#64748b", fill: "rgba(100, 116, 139, 0.14)" },
  canonical: { border: "#38bdf8", fill: "rgba(56, 189, 248, 0.10)" },
  case_override: { border: "#fda4af", fill: "rgba(253, 164, 175, 0.13)" },
  internal: { border: "#fbbf24", fill: "rgba(251, 191, 36, 0.12)" }
};

export const HANDLE_PX = 10;
// Screen-px gap between a selected rect's top edge and its rotation handle.
export const ROTATE_HANDLE_OFFSET_PX = 22;

function roundRectPath(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

export function drawScene(canvas: HTMLCanvasElement, scene: Scene): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const { camera, cssW, cssH, dpr, cols, rows } = scene;
  const s = camera.scale;
  const X = (t: number) => (t - camera.x) * s;
  const Y = (t: number) => (t - camera.y) * s;

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  // Page background (outside the world)
  ctx.fillStyle = "#0a0a0d";
  ctx.fillRect(0, 0, cssW, cssH);

  const wx0 = X(0);
  const wy0 = Y(0);
  const worldW = cols * s;
  const worldH = rows * s;

  // World background
  ctx.fillStyle = scene.solidRender ? TILE_COLORS.tile_grass : "#141419";
  ctx.fillRect(wx0, wy0, worldW, worldH);

  // Underlay art: each source is a set of images placed at world-tile rects
  // (the HD overworld is a 3x3 mosaic; older art covers the centre third).
  if (scene.underlays.length) {
    ctx.save();
    ctx.globalAlpha = scene.underlayOpacity;
    ctx.imageSmoothingEnabled = true;
    for (const u of scene.underlays) {
      if (!u.img.complete || u.img.naturalWidth === 0) continue;
      const px = X(u.x);
      const py = Y(u.y);
      const pw = u.w * s;
      const ph = u.h * s;
      if (px + pw < 0 || px > cssW || py + ph < 0 || py > cssH) continue;
      ctx.drawImage(u.img, px, py, pw, ph);
    }
    ctx.restore();
  }

  // Visible tile range for culling
  const tx0 = Math.max(0, Math.floor(camera.x));
  const ty0 = Math.max(0, Math.floor(camera.y));
  const tx1 = Math.min(cols, Math.ceil(camera.x + cssW / s));
  const ty1 = Math.min(rows, Math.ceil(camera.y + cssH / s));

  // Painted tiles, layer order = z order
  for (const layerName of ALLOWED_LAYERS) {
    if (!scene.visibleLayers[layerName]) continue;
    const layer = scene.tileLayers[layerName];
    if (!layer || !layer.tiles.length) continue;
    for (const t of layer.tiles) {
      if (t.x < tx0 - 1 || t.x > tx1 || t.y < ty0 - 1 || t.y > ty1) continue;
      ctx.fillStyle = TILE_COLORS[t.tile_id] || "#888";
      ctx.fillRect(X(t.x), Y(t.y), s + 0.5, s + 0.5);
    }
  }

  // Grid lines
  if (scene.showGrid) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(wx0, wy0, worldW, worldH);
    ctx.clip();

    if (s >= 5) {
      ctx.strokeStyle = `rgba(255,255,255,${s >= 9 ? 0.07 : 0.035})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = tx0; i <= tx1; i++) {
        const px = Math.round(X(i)) + 0.5;
        ctx.moveTo(px, wy0);
        ctx.lineTo(px, wy0 + worldH);
      }
      for (let i = ty0; i <= ty1; i++) {
        const py = Math.round(Y(i)) + 0.5;
        ctx.moveTo(wx0, py);
        ctx.lineTo(wx0 + worldW, py);
      }
      ctx.stroke();
    }

    // Major lines every 8 tiles
    ctx.strokeStyle = "rgba(255,255,255,0.10)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = Math.ceil(tx0 / 8) * 8; i <= tx1; i += 8) {
      const px = Math.round(X(i)) + 0.5;
      ctx.moveTo(px, wy0);
      ctx.lineTo(px, wy0 + worldH);
    }
    for (let i = Math.ceil(ty0 / 8) * 8; i <= ty1; i += 8) {
      const py = Math.round(Y(i)) + 0.5;
      ctx.moveTo(wx0, py);
      ctx.lineTo(wx0 + worldW, py);
    }
    ctx.stroke();
    ctx.restore();
  }

  // World border
  ctx.strokeStyle = "#3f3f46";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(wx0, wy0, worldW, worldH);

  // Safety margin
  if (scene.showSafety) {
    const m = SAFETY_MARGIN_TILES;
    ctx.save();
    ctx.strokeStyle = "rgba(244, 63, 94, 0.35)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 5]);
    ctx.strokeRect(X(m), Y(m), (cols - 2 * m) * s, (rows - 2 * m) * s);
    ctx.setLineDash([]);
    if (s >= 3) {
      ctx.fillStyle = "rgba(244, 63, 94, 0.5)";
      ctx.font = "600 10px ui-monospace, monospace";
      ctx.textAlign = "left";
      ctx.textBaseline = "top";
      ctx.fillText("PLAYABLE BOUNDARY", X(m) + 6, Y(m) + 5);
    }
    ctx.restore();
  }

  // Lights (drawn under props/buildings, like the in-game glow sits behind
  // interactable objects)
  for (const lt of scene.lights) {
    const px = X(lt.x);
    const py = Y(lt.y);
    const pw = (lt.width / 2) * s;
    const ph = (lt.height / 2) * s;
    if (px + pw < 0 || px - pw > cssW || py + ph < 0 || py - ph > cssH) continue;

    const swatch = LIGHT_ASSET_SWATCHES[lt.semanticAssetId]?.color || "#ffe9a8";
    ctx.save();
    ctx.globalAlpha = lt.opacity ?? 0.65;
    const grad = ctx.createRadialGradient(px, py, 0, px, py, Math.max(pw, ph, 2));
    grad.addColorStop(0, swatch);
    grad.addColorStop(0.55, `${swatch}88`);
    grad.addColorStop(1, `${swatch}00`);
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.ellipse(px, py, Math.max(pw, 2), Math.max(ph, 2), 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    if (lt.selected) {
      ctx.save();
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      ctx.ellipse(px, py, Math.max(pw, 2), Math.max(ph, 2), 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
      drawHandle(ctx, px + pw, py + ph);
    }
  }

  // Ambient sprites (editor alignment boxes; runtime can animate from the
  // saved asset_id and dimensions).
  for (const amb of scene.ambientSprites) {
    const px = X(amb.x);
    const py = Y(amb.y);
    const pw = amb.width * s;
    const ph = amb.height * s;
    if (px + pw < 0 || px > cssW || py + ph < 0 || py > cssH) continue;

    const swatch = AMBIENT_ASSET_SWATCHES[amb.assetId] || { label: amb.assetId, color: "#bae6fd" };
    ctx.save();
    ctx.globalAlpha = amb.opacity ?? 0.6;
    roundRectPath(ctx, px, py, Math.max(pw, 3), Math.max(ph, 3), Math.min(8, s * 0.25));
    ctx.fillStyle = `${swatch.color}33`;
    ctx.fill();
    ctx.strokeStyle = amb.selected ? "#38bdf8" : `${swatch.color}cc`;
    ctx.lineWidth = amb.selected ? 2 : 1.25;
    if (!amb.selected) ctx.setLineDash([4, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
    if (s >= 4 && pw > 42 && ph > 16) {
      ctx.globalAlpha = 0.95;
      ctx.font = "700 10px -apple-system, 'Segoe UI', sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#f8fafc";
      ctx.shadowColor = "rgba(0,0,0,0.8)";
      ctx.shadowBlur = 3;
      ctx.fillText(swatch.label, px + pw / 2, py + ph / 2, pw - 8);
      ctx.shadowBlur = 0;
    }
    ctx.restore();

    if (amb.selected) {
      drawHandle(ctx, px + pw, py + ph);
    }
  }

  // Props
  for (const p of scene.props) {
    const px = X(p.x);
    const py = Y(p.y);
    const pw = p.w * s;
    const ph = p.h * s;
    if (px + pw < 0 || px > cssW || py + ph < 0 || py > cssH) continue;

    const isBuilding = p.kind === "building" || p.assetId.startsWith("building:");
    const artReady = isBuilding && p.img && p.img.complete && p.img.naturalWidth > 0;
    if (artReady) {
      drawBuildingArt(ctx, p.img!, px, py, pw, ph, p.rotation || 0);
      if (p.selected) {
        ctx.save();
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.strokeRect(px, py, pw, ph);
        ctx.setLineDash([]);
        ctx.restore();
      }
      continue;
    }

    ctx.save();
    roundRectPath(ctx, px, py, Math.max(pw, 3), Math.max(ph, 3), Math.min(4, s * 0.2));
    ctx.fillStyle = isBuilding
      ? p.selected ? "rgba(56, 189, 248, 0.38)" : "rgba(30, 41, 59, 0.68)"
      : p.selected ? "rgba(56, 189, 248, 0.45)" : "rgba(245, 158, 11, 0.32)";
    ctx.fill();
    ctx.strokeStyle = isBuilding ? (p.selected ? "#38bdf8" : "rgba(148, 163, 184, 0.95)") : (p.selected ? "#38bdf8" : "rgba(245, 158, 11, 0.9)");
    ctx.lineWidth = p.selected ? 2 : 1;
    ctx.stroke();
    ctx.restore();

    if (isBuilding) {
      const label = p.assetId.replace(/^building:/, "").replace(/_v\d+$/, "").replace(/_/g, " ");
      if (s >= 3) {
        ctx.font = `600 ${Math.min(15, Math.max(9, s * 0.65))}px ui-monospace, monospace`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#e2e8f0";
        ctx.fillText(label, px + pw / 2, py + ph / 2);
      }
    } else {
      const emojiSize = Math.min(pw, ph) * 0.72;
      if (emojiSize >= 9) {
        ctx.font = `${Math.min(emojiSize, 42)}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(PROP_EMOJIS[p.assetId] || "?", px + pw / 2, py + ph / 2 + 1);
      }
    }

    if (p.selected && !isBuilding) {
      drawHandle(ctx, px + pw, py + ph);
    }
  }

  // Location bounds (drawn rotated around the rect centre when the bounds
  // carry a visual rotation matching the art's camera angle)
  for (const loc of scene.locations) {
    const { x, y, w, h } = loc.bounds;
    const rot = ((loc.bounds.rotation || 0) * Math.PI) / 180;
    const pw = w * s;
    const ph = h * s;
    const cx = X(x) + pw / 2;
    const cy = Y(y) + ph / 2;
    const cullRad = Math.hypot(pw, ph) / 2 + 40;
    if (cx + cullRad < 0 || cx - cullRad > cssW || cy + cullRad < 0 || cy - cullRad > cssH) continue;

    const colors = SOURCE_COLORS[loc.source];
    ctx.save();
    ctx.globalAlpha = loc.alpha;
    ctx.translate(cx, cy);
    if (rot) ctx.rotate(rot);
    ctx.fillStyle = colors.fill;
    ctx.fillRect(-pw / 2, -ph / 2, pw, ph);
    ctx.strokeStyle = colors.border;
    ctx.lineWidth = loc.selected ? 2.5 : loc.hovered ? 2 : 1.25;
    ctx.strokeRect(-pw / 2, -ph / 2, pw, ph);
    if (loc.selected) {
      ctx.strokeStyle = "rgba(255,255,255,0.85)";
      ctx.lineWidth = 1;
      ctx.strokeRect(-pw / 2 - 2, -ph / 2 - 2, pw + 4, ph + 4);
    }
    ctx.restore();

    // Labels stay horizontal for readability regardless of rotation
    if (scene.showLabels && pw > 44 && ph > 16) {
      ctx.save();
      ctx.globalAlpha = loc.alpha;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = "700 11px -apple-system, 'Segoe UI', sans-serif";
      ctx.shadowColor = "rgba(0,0,0,0.85)";
      ctx.shadowBlur = 4;
      ctx.fillStyle = "#fff";
      ctx.fillText(loc.name, cx, s >= 5 && ph > 34 ? cy - 7 : cy, pw - 8);
      if (s >= 5 && ph > 34) {
        ctx.font = "500 9px ui-monospace, monospace";
        ctx.fillStyle = "rgba(255,255,255,0.75)";
        const rotSuffix = loc.bounds.rotation ? ` ∠${fmt(loc.bounds.rotation)}°` : "";
        ctx.fillText(`(${fmt(x)},${fmt(y)}) ${fmt(w)}×${fmt(h)}${rotSuffix}`, cx, cy + 8, pw - 8);
      }
      ctx.shadowBlur = 0;
      ctx.restore();
    }

    if (loc.selected) {
      // Resize handle at the rotated bottom-right corner
      const cos = Math.cos(rot);
      const sin = Math.sin(rot);
      const hx = cx + (pw / 2) * cos - (ph / 2) * sin;
      const hy = cy + (pw / 2) * sin + (ph / 2) * cos;
      drawHandle(ctx, hx, hy);

      // Rotation handle above the rotated top edge, tethered to the rect
      const ry = -ph / 2 - ROTATE_HANDLE_OFFSET_PX;
      const rx0 = cx - (ph / 2) * -sin;
      const ry0 = cy + (ph / 2) * -cos;
      const rhx = cx + ry * -sin;
      const rhy = cy + ry * cos;
      ctx.save();
      ctx.strokeStyle = "rgba(255,255,255,0.6)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(rx0, ry0);
      ctx.lineTo(rhx, rhy);
      ctx.stroke();
      ctx.fillStyle = "#fbbf24";
      ctx.strokeStyle = "#09090b";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(rhx, rhy, HANDLE_PX / 2 + 1, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }
  }

  // Evidence anchors
  for (const a of scene.anchors) {
    const px = X(a.x);
    const py = Y(a.y);
    if (px < -20 || px > cssW + 20 || py < -20 || py > cssH + 20) continue;
    const r = Math.max(5, Math.min(s * 0.35, 11));
    ctx.save();
    ctx.globalAlpha = a.alpha;
    if (a.selected) {
      ctx.beginPath();
      ctx.arc(px, py, r + 4, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(56, 189, 248, 0.3)";
      ctx.fill();
    }
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fillStyle = a.selected ? "#38bdf8" : "#ef4444";
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.restore();
  }

  // Tool overlay
  const ov = scene.overlay;
  if (ov) {
    if (ov.kind === "brush") {
      ctx.save();
      for (const c of ov.cells) {
        const px = X(c.x);
        const py = Y(c.y);
        ctx.fillStyle = ov.erase ? "rgba(244, 63, 94, 0.22)" : "rgba(255,255,255,0.16)";
        ctx.fillRect(px, py, s, s);
        ctx.strokeStyle = ov.erase ? "rgba(244, 63, 94, 0.8)" : "rgba(255,255,255,0.75)";
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 0.5, py + 0.5, s - 1, s - 1);
      }
      ctx.restore();
    } else if (ov.kind === "rect") {
      const px = X(ov.x);
      const py = Y(ov.y);
      ctx.save();
      ctx.fillStyle = ov.erase
        ? "rgba(244, 63, 94, 0.18)"
        : hexToRgba(TILE_COLORS[ov.tileId] || "#ffffff", 0.35);
      ctx.fillRect(px, py, ov.w * s, ov.h * s);
      ctx.strokeStyle = ov.erase ? "#f43f5e" : "#fff";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 4]);
      ctx.strokeRect(px, py, ov.w * s, ov.h * s);
      ctx.setLineDash([]);
      ctx.font = "600 10px ui-monospace, monospace";
      ctx.fillStyle = "#fff";
      ctx.textAlign = "left";
      ctx.textBaseline = "bottom";
      ctx.shadowColor = "rgba(0,0,0,0.9)";
      ctx.shadowBlur = 3;
      ctx.fillText(`${ov.w}×${ov.h}`, px + 3, py - 3);
      ctx.restore();
    } else if (ov.kind === "propGhost") {
      const px = X(ov.x);
      const py = Y(ov.y);
      const isBuilding = ov.assetId.startsWith("building:");
      const gw = (ov.w || 1) * s;
      const gh = (ov.h || 1) * s;
      const ghostArt = isBuilding && ov.img && ov.img.complete && ov.img.naturalWidth > 0;
      ctx.save();
      ctx.globalAlpha = ghostArt ? 0.7 : 0.55;
      if (ghostArt) {
        drawBuildingArt(ctx, ov.img!, px, py, gw, gh, ov.rotation || 0);
      } else {
        roundRectPath(ctx, px, py, gw, gh, Math.min(4, s * 0.2));
        ctx.fillStyle = isBuilding ? "rgba(30, 41, 59, 0.55)" : "rgba(245, 158, 11, 0.35)";
        ctx.fill();
      }
      roundRectPath(ctx, px, py, gw, gh, Math.min(4, s * 0.2));
      ctx.strokeStyle = "rgba(245, 158, 11, 0.9)";
      ctx.setLineDash([4, 3]);
      ctx.stroke();
      ctx.setLineDash([]);
      if (ov.front) {
        // Door marker on the front edge so rotation reads at a glance.
        ctx.strokeStyle = "#fbbf24";
        ctx.lineWidth = Math.max(2, s * 0.2);
        ctx.beginPath();
        if (ov.front === "south") { ctx.moveTo(px + gw * 0.3, py + gh); ctx.lineTo(px + gw * 0.7, py + gh); }
        else if (ov.front === "north") { ctx.moveTo(px + gw * 0.3, py); ctx.lineTo(px + gw * 0.7, py); }
        else if (ov.front === "west") { ctx.moveTo(px, py + gh * 0.3); ctx.lineTo(px, py + gh * 0.7); }
        else { ctx.moveTo(px + gw, py + gh * 0.3); ctx.lineTo(px + gw, py + gh * 0.7); }
        ctx.stroke();
      }
      if (s >= 10 && !ghostArt) {
        ctx.font = `${Math.min(s * 0.72, 42)}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(isBuilding ? "building" : (PROP_EMOJIS[ov.assetId] || "?"), px + gw / 2, py + gh / 2 + 1);
      }
      ctx.restore();
    }
  }
}

/** Draw bundle art over a screen-space footprint box, rotated in 90° steps.
 *  The box (pw×ph) is the already-swapped rotated footprint; the image keeps
 *  its natural aspect because footprints match the art at 32px per tile. */
function drawBuildingArt(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  px: number,
  py: number,
  pw: number,
  ph: number,
  rotation: number
): void {
  const rot = ((Math.round(rotation / 90) % 4) + 4) % 4;
  ctx.save();
  if (rot) {
    ctx.translate(px + pw / 2, py + ph / 2);
    ctx.rotate((rot * Math.PI) / 2);
    const dw = rot % 2 ? ph : pw;
    const dh = rot % 2 ? pw : ph;
    ctx.drawImage(img, -dw / 2, -dh / 2, dw, dh);
  } else {
    ctx.drawImage(img, px, py, pw, ph);
  }
  ctx.restore();
}

function drawHandle(ctx: CanvasRenderingContext2D, px: number, py: number): void {
  ctx.save();
  ctx.fillStyle = "#fff";
  ctx.strokeStyle = "#09090b";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(px, py, HANDLE_PX / 2 + 1, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

export function drawMinimap(canvas: HTMLCanvasElement, scene: Scene): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const dpr = scene.dpr;
  const cw = canvas.width / dpr;
  const ch = canvas.height / dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const pad = 4;
  const sc = Math.min((cw - pad * 2) / scene.cols, (ch - pad * 2) / scene.rows);
  const ox = (cw - scene.cols * sc) / 2;
  const oy = (ch - scene.rows * sc) / 2;

  ctx.fillStyle = "rgba(9, 9, 11, 0.92)";
  ctx.fillRect(0, 0, cw, ch);

  ctx.fillStyle = scene.solidRender ? TILE_COLORS.tile_grass : "#1b1b21";
  ctx.fillRect(ox, oy, scene.cols * sc, scene.rows * sc);

  if (scene.underlays.length) {
    ctx.save();
    ctx.globalAlpha = Math.min(scene.underlayOpacity + 0.25, 0.9);
    for (const u of scene.underlays) {
      if (!u.img.complete || u.img.naturalWidth === 0) continue;
      ctx.drawImage(u.img, ox + u.x * sc, oy + u.y * sc, u.w * sc, u.h * sc);
    }
    ctx.restore();
  }

  for (const loc of scene.locations) {
    const c = SOURCE_COLORS[loc.source];
    ctx.fillStyle = c.border;
    ctx.globalAlpha = 0.55 * loc.alpha;
    ctx.fillRect(
      ox + loc.bounds.x * sc,
      oy + loc.bounds.y * sc,
      Math.max(loc.bounds.w * sc, 1.5),
      Math.max(loc.bounds.h * sc, 1.5)
    );
  }
  ctx.globalAlpha = 1;

  // Viewport rectangle
  const vx = ox + scene.camera.x * sc;
  const vy = oy + scene.camera.y * sc;
  const vw = (scene.cssW / scene.camera.scale) * sc;
  const vh = (scene.cssH / scene.camera.scale) * sc;
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 1.25;
  ctx.strokeRect(vx, vy, vw, vh);

  ctx.strokeStyle = "#3f3f46";
  ctx.lineWidth = 1;
  ctx.strokeRect(ox, oy, scene.cols * sc, scene.rows * sc);
}

/** Convert a minimap CSS pixel position to world tile coordinates. */
export function minimapToWorld(
  canvas: HTMLCanvasElement,
  scene: Scene,
  cssX: number,
  cssY: number
): { x: number; y: number } {
  const dpr = scene.dpr;
  const cw = canvas.width / dpr;
  const ch = canvas.height / dpr;
  const pad = 4;
  const sc = Math.min((cw - pad * 2) / scene.cols, (ch - pad * 2) / scene.rows);
  const ox = (cw - scene.cols * sc) / 2;
  const oy = (ch - scene.rows * sc) / 2;
  return { x: (cssX - ox) / sc, y: (cssY - oy) / sc };
}

function fmt(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function hexToRgba(hex: string, alpha: number): string {
  if (hex.startsWith("rgba")) return hex;
  const m = hex.replace("#", "");
  const full = m.length === 3 ? m.split("").map((c) => c + c).join("") : m;
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
