// Shared types, constants and helpers for the developer map editor.
// Data schema (town_layout_editor_v2) is unchanged from the original editor —
// only the editing experience was rebuilt.

export interface Bounds {
  x: number;
  y: number;
  w: number;
  h: number;
  // Visual rotation in degrees around the rect centre, matching the art's
  // camera angle. The axis-aligned x/y/w/h remain the logical bounds for
  // containment/overlap checks; rotation only affects how the box is drawn.
  rotation?: number;
}

export interface LocationData {
  bounds: Bounds;
  // Bounds for the internal (roofless close-up) map view; absent = inherit
  // the external `bounds`.
  bounds_internal?: Bounds;
  mode: string;
  notes?: string;
}

// Which of the paired town-view artworks is being edited: the external
// (roofed overview) or the internal (roofless close-up) B2 art.
export type MapView = "external" | "internal";

export interface ObjectAnchor {
  location_id: string;
  anchor: { x: number; y: number };
  semantic_asset_id?: string;
  render_policy?: string;
  external?: boolean;
}

export interface CaseOverride {
  visible_locations: string[];
  location_bounds: Record<string, Bounds>;
  object_anchors: Record<string, ObjectAnchor>;
}

export interface TileEntry {
  x: number;
  y: number;
  tile_id: string;
}

export interface TileLayer {
  tiles: TileEntry[];
}

export interface PropInstance {
  instance_id: string;
  asset_id: string;
  location_id: string;
  x: number;
  y: number;
  w?: number;
  h?: number;
  layer?: string;
  case_id?: string;
  object_id?: string;
  render_policy?: string;
}

// A light's x/y is the CENTER of the glow (unlike PropInstance, whose x/y is
// its top-left corner) — matching the runtime contract in
// frontend/src/types.ts's MapLightOverlay / MapLightOverlay.tsx, which
// renders `left: pct(light.x - light.width / 2, ...)`. Moves translate the
// centre; resizes grow width/height symmetrically around it.
//
// Global (not nested under CaseOverride): the art itself is case-agnostic —
// case scoping happens by filtering on `location_id` against a case's
// visible_location_ids at read time (backend `resolve_town_lights`), the
// same mechanism object_anchors' containment check relies on for its own
// location_id, not by duplicating a light per case.
export interface LightDef {
  location_id: string;
  semantic_asset_id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  from: string; // "HH:MM", active window; wraps midnight when from > to
  to: string;
  opacity?: number;
  // Overrides for the internal (roofless interior) art, a different painted
  // asset than the external one — same pattern as LocationData.bounds_internal.
  x_internal?: number;
  y_internal?: number;
  width_internal?: number;
  height_internal?: number;
  semantic_asset_id_internal?: string;
  opacity_internal?: number;
}

// Global ambient sprite overlays are authored in tile-space. x/y is the
// top-left corner, matching prop placement, so they can be aligned against
// water, chimneys, lamps and paths in the map editor.
export interface AmbientSpriteDef {
  asset_id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  opacity?: number;
  from?: string;
  to?: string;
}

export interface BuildingInstance {
  instance_id: string;
  asset_id: string;
  location_id: string;
  x: number;
  y: number;
  rotation?: number;
  exterior_asset?: string;
  interior_asset?: string;
  footprint?: { w: number; h: number };
  entrances?: Array<{ x: number; y: number; facing: string }>;
  derived_tiles?: Record<string, { tiles: TileEntry[] }>;
}

// Visual-only per-cell art swaps for the HD overworld mosaic, keyed by view
// then cell id (A1..C3). Value is the /art/... URL shown instead of the
// default artwork for that cell.
export type UnderlayTileOverrides = Partial<Record<MapView, Record<string, string>>>;

// One swappable artwork file for a mosaic cell, discovered by the backend
// from frontend/public/art/town/tiles_3x3_hd/.
export interface TileArtVariant {
  url: string;
  label: string;
}

export interface TownLayout {
  version: string;
  grid: { cols: number; rows: number; tile_size: number };
  canonical_locations: Record<string, LocationData>;
  case_overrides: Record<string, CaseOverride>;
  tile_layers: Record<string, TileLayer>;
  prop_instances: Record<string, PropInstance[]>;
  building_instances: BuildingInstance[];
  underlay_tile_overrides?: UnderlayTileOverrides;
  lights: Record<string, LightDef>;
  ambient_sprites: Record<string, AmbientSpriteDef>;
}

export interface CaseLocationRef {
  location_id: string;
  name: string;
  description: string;
  legacy_bounds: { x: number; y: number; width: number; height: number } | null;
  legacy_position: { x: number; y: number } | null;
  visual_layer: string | null;
}

export interface CaseObjectRef {
  object_id: string;
  name: string;
  description: string;
  normal_location_id: string | null;
  final_location_id: string | null;
}

export interface CaseRef {
  case_id: string;
  title: string;
  locations: CaseLocationRef[];
  objects: CaseObjectRef[];
}

// --- Editor-side types ---

export type ToolId =
  | "select"
  | "pan"
  | "paint"
  | "erase"
  | "rect"
  | "fill"
  | "picker"
  | "prop"
  | "building"
  | "light"
  | "ambient";

export type PreviewMode = "debug" | "player_reveal" | "fog";

export type Selection =
  | { kind: "location"; id: string }
  | { kind: "object"; id: string }
  | { kind: "prop"; id: string }
  | { kind: "building"; id: string }
  | { kind: "light"; id: string }
  | { kind: "ambient"; id: string }
  | null;

export interface Camera {
  x: number; // world tile coord at canvas left edge
  y: number; // world tile coord at canvas top edge
  scale: number; // screen px per world tile
}

export type LocationSource = "recommended" | "canonical" | "case_override" | "internal";

// --- Constants ---

export const ALLOWED_TILES = [
  "tile_grass", "tile_mud", "tile_cobble", "tile_path", "tile_floor_wood",
  "tile_floor_stone", "tile_wall_exterior", "tile_wall_interior", "tile_water",
  "tile_water_edge", "tile_fence", "tile_hedge", "tile_flowerbed", "tile_tree",
  "tile_shadow_soft"
];

export const ALLOWED_PROPS = [
  "prop_fountain_coping", "prop_lamp", "prop_bench", "prop_cafe_counter",
  "prop_till", "prop_mop_bucket", "prop_coat_rack", "prop_crate",
  "prop_bookshop_shelf", "prop_desk", "prop_letter_opener", "prop_broken_window",
  "prop_clinic_bed", "prop_dispensary_shelf", "prop_medicine_cabinet",
  "prop_pub_bar", "prop_pub_stool", "prop_pub_ledger", "prop_lighter",
  "prop_fireplace", "prop_cocoa_mug", "prop_books", "prop_garden_plant",
  "prop_foxglove", "prop_letters", "prop_documents", "prop_phone", "prop_key",
  "prop_belt", "prop_boots", "prop_muddy_footprint"
];

export const ALLOWED_LAYERS = [
  "base", "terrain_detail", "paths", "interior_floors", "walls", "structures",
  "props", "case_overlays", "object_anchors", "evidence_markers", "fog", "debug_bounds",
  "lights", "ambient"
];

// Mirrors the semantic_asset_id union in frontend/src/types.ts's
// MapLightOverlay and the CSS classes in frontend/src/styles.css
// (.map-light-local.*).
export const ALLOWED_LIGHT_ASSETS = [
  "light_streetlamp_pool", "light_window_warm", "light_window_cool",
  "light_pub_window_glow", "light_fireplace_glow"
];

export const LIGHT_ASSET_SWATCHES: Record<string, { label: string; color: string }> = {
  light_streetlamp_pool: { label: "Streetlamp pool", color: "#ffe9a8" },
  light_window_warm: { label: "Warm window", color: "#ffb366" },
  light_window_cool: { label: "Cool window", color: "#8ec4ff" },
  light_pub_window_glow: { label: "Pub window glow", color: "#ffcf7a" },
  light_fireplace_glow: { label: "Fireplace glow", color: "#ff8a3d" }
};

export const ALLOWED_AMBIENT_ASSETS = [
  "water_shimmer", "fish_ripple_loop", "chimney_smoke", "lamp_flicker",
  "drifting_mist", "birds_crossing", "warm_motes"
];

export const AMBIENT_ASSET_SWATCHES: Record<string, { label: string; color: string; width: number; height: number; opacity: number }> = {
  water_shimmer: { label: "Water shimmer", color: "#7dd3fc", width: 5.625, height: 2.8125, opacity: 0.55 },
  fish_ripple_loop: { label: "Fish ripple loop", color: "#38bdf8", width: 3, height: 3, opacity: 0.72 },
  chimney_smoke: { label: "Chimney smoke", color: "#cbd5e1", width: 3, height: 5, opacity: 0.72 },
  lamp_flicker: { label: "Lamp flicker", color: "#fbbf24", width: 3, height: 3, opacity: 0.62 },
  drifting_mist: { label: "Drifting mist", color: "#bae6fd", width: 12, height: 6, opacity: 0.48 },
  birds_crossing: { label: "Birds crossing", color: "#111827", width: 7.5, height: 3.75, opacity: 0.68 },
  warm_motes: { label: "Warm motes", color: "#fde68a", width: 6, height: 4, opacity: 0.5 }
};

export const TILE_COLORS: Record<string, string> = {
  tile_grass: "#166534",
  tile_mud: "#451a03",
  tile_cobble: "#3f3f46",
  tile_path: "#b45309",
  tile_floor_wood: "#78350f",
  tile_floor_stone: "#52525b",
  tile_wall_exterior: "#1e293b",
  tile_wall_interior: "#71717a",
  tile_water: "#1e3a8a",
  tile_water_edge: "#0e7490",
  tile_fence: "#475569",
  tile_hedge: "#14532d",
  tile_flowerbed: "#be185d",
  tile_tree: "#064e3b",
  tile_shadow_soft: "rgba(0, 0, 0, 0.4)"
};

export const PROP_EMOJIS: Record<string, string> = {
  prop_fountain_coping: "⛲",
  prop_lamp: "💡",
  prop_bench: "🪑",
  prop_cafe_counter: "🍽️",
  prop_till: "💵",
  prop_mop_bucket: "🪣",
  prop_coat_rack: "🧥",
  prop_crate: "📦",
  prop_bookshop_shelf: "📚",
  prop_desk: "🖥️",
  prop_letter_opener: "🔪",
  prop_broken_window: "💥",
  prop_clinic_bed: "🛏️",
  prop_dispensary_shelf: "🧪",
  prop_medicine_cabinet: "🧰",
  prop_pub_bar: "🍻",
  prop_pub_stool: "🪑",
  prop_pub_ledger: "📓",
  prop_lighter: "🔥",
  prop_fireplace: "🪵",
  prop_cocoa_mug: "☕",
  prop_books: "📖",
  prop_garden_plant: "🪴",
  prop_foxglove: "🌸",
  prop_letters: "✉️",
  prop_documents: "📄",
  prop_phone: "📞",
  prop_key: "🔑",
  prop_belt: "🎗️",
  prop_boots: "👢",
  prop_muddy_footprint: "👣"
};

export const ALLOWED_NESTING = [
  ["loc_village_square", "loc_fountain"],
  ["loc_hobbs_cafe", "loc_cafe_kitchen"],
  ["loc_hobbs_cafe", "loc_cafe_storage"],
  ["loc_bookshop", "loc_bookshop_back"],
  ["loc_clinic", "loc_clinic_dispensary"],
  ["loc_marcus_house", "loc_marcus_study"],
  ["loc_village_square", "loc_elias_bench"]
];

export function isNestingAllowed(idA: string, idB: string): boolean {
  return ALLOWED_NESTING.some(
    ([parent, child]) => (idA === parent && idB === child) || (idB === parent && idA === child)
  );
}

// An underlay source is a set of images placed at world-tile rectangles.
// The HD overworld ships as a 3x3 mosaic: rows A-C top->bottom, cols 1-3
// left->right (B2 = town centre); each 2048x1536 cell covers 64x48 tiles.
export interface UnderlayTilePlacement {
  url: string;
  x: number;
  y: number;
  w: number;
  h: number;
  // Mosaic cell id (A1..C3) when the placement is one cell of the HD 3x3
  // overworld; cells are the unit of per-view art overrides.
  cell?: string;
}

export interface UnderlaySourceDef {
  id: string;
  label: string;
  tiles: UnderlayTilePlacement[];
}

// B2 (town centre) ships as a pair, mirroring the runtime contract in
// town_map.py: the external roofed overview and the roofless interior the
// game swaps to past the zoom threshold.
export const LIVING_TOWN_REMASTER_V5_PREFIX = "/art/town/tiles_3x3_hd/living_town_v2/remastered_master_v5";
export const HD_B2_EXTERNAL_URL = `${LIVING_TOWN_REMASTER_V5_PREFIX}/town_overworld_B2_living_town_remaster_v5_clean_generated.png`;
export const HD_B2_INTERNAL_URL = `${LIVING_TOWN_REMASTER_V5_PREFIX}/zoom_interior_v8_hobbs_cafe/town_overworld_B2_zoom_interior_v8_hobbs_cafe_edge_locked.png`;
export const LIVING_TOWN_V2_TILE_URLS: Partial<Record<string, string>> = {
  A1: `${LIVING_TOWN_REMASTER_V5_PREFIX}/town_overworld_A1_living_town_remaster_v5_clean_generated.png`,
  A2: `${LIVING_TOWN_REMASTER_V5_PREFIX}/town_overworld_A2_living_town_remaster_v5_clean_generated.png`,
  A3: `${LIVING_TOWN_REMASTER_V5_PREFIX}/town_overworld_A3_living_town_remaster_v5_clean_generated.png`,
  B1: `${LIVING_TOWN_REMASTER_V5_PREFIX}/town_overworld_B1_living_town_remaster_v5_clean_generated.png`,
  B2: HD_B2_EXTERNAL_URL,
  B3: `${LIVING_TOWN_REMASTER_V5_PREFIX}/town_overworld_B3_living_town_remaster_v5_clean_generated.png`,
  C1: `${LIVING_TOWN_REMASTER_V5_PREFIX}/town_overworld_C1_living_town_remaster_v5_clean_generated.png`,
  C2: `${LIVING_TOWN_REMASTER_V5_PREFIX}/town_overworld_C2_living_town_remaster_v5_clean_generated.png`,
  C3: `${LIVING_TOWN_REMASTER_V5_PREFIX}/town_overworld_C3_living_town_remaster_v5_clean_generated.png`,
};

export const HD_TILE_CELLS = (["A", "B", "C"] as const).flatMap((row) =>
  ([1, 2, 3] as const).map((col) => `${row}${col}`)
);

/** The artwork a mosaic cell shows by default in the given view. */
export function hdDefaultTileUrl(cell: string, view: MapView): string {
  if (cell === "B2") return view === "internal" ? HD_B2_INTERNAL_URL : HD_B2_EXTERNAL_URL;
  const livingTownUrl = LIVING_TOWN_V2_TILE_URLS[cell];
  if (livingTownUrl) return livingTownUrl;
  return `/art/town/tiles_3x3_hd/town_overworld_${cell}_hd.png`;
}

/** The artwork a mosaic cell shows in the given view, honouring layout overrides. */
export function resolveHdTileUrl(
  cell: string,
  view: MapView,
  overrides: UnderlayTileOverrides | undefined
): string {
  return overrides?.[view]?.[cell] || hdDefaultTileUrl(cell, view);
}

const HD_3X3_TILES: UnderlayTilePlacement[] = (["A", "B", "C"] as const).flatMap((row, r) =>
  ([1, 2, 3] as const).map((col, c) => ({
    url: hdDefaultTileUrl(`${row}${col}`, "external"),
    cell: `${row}${col}`,
    x: c * 64,
    y: r * 48,
    w: 64,
    h: 48
  }))
);

const CENTRE_THIRD = { x: 64, y: 48, w: 64, h: 48 };

export const UNDERLAY_SOURCES: UnderlaySourceDef[] = [
  { id: "town_tiles_hd", label: "Town overworld HD (3×3 tiles)", tiles: HD_3X3_TILES },
  {
    id: "town_overworld",
    label: "Town overworld v2 (single image)",
    tiles: [{ url: "/art/town/town_canonical_v2_overworld_day.png", x: 0, y: 0, w: 192, h: 144 }]
  },
  {
    id: "town_day",
    label: "Town canonical v1 (day, centre)",
    tiles: [{ url: "/art/town/town_canonical_v1_day.png", ...CENTRE_THIRD }]
  },
  {
    id: "case4_day",
    label: "Case 004 fountain (day, centre)",
    tiles: [{ url: "/art/case_004/fountain_daylight_map.png", ...CENTRE_THIRD }]
  },
  {
    id: "case4_night",
    label: "Case 004 fountain (midnight, centre)",
    tiles: [{ url: "/art/case_004/fountain_midnight_map.png", ...CENTRE_THIRD }]
  }
];

export type UnderlaySourceId =
  | "town_tiles_hd"
  | "town_overworld"
  | "town_day"
  | "case4_day"
  | "case4_night"
  | "none";

export const MIN_SCALE = 1.5;
export const MAX_SCALE = 64;
export const SAFETY_MARGIN_TILES = 4;
export const HISTORY_LIMIT = 100;
export const FLOOD_FILL_LIMIT = 8000;

export const RENDER_POLICIES = [
  { value: "always_visible", label: "Always Visible" },
  { value: "case_visible", label: "Case Visible" },
  { value: "discovery_gated", label: "Discovery Gated" },
  { value: "hidden_until_revealed", label: "Hidden Until Revealed" },
  { value: "debug_only", label: "Debug Only" }
];

export const TOOL_DEFS: Array<{ id: ToolId; label: string; icon: string; key: string; hint: string }> = [
  { id: "select", label: "Select / Move", icon: "⬚", key: "V", hint: "Click to select · drag to move · corner handle resizes · amber handle rotates · arrows nudge" },
  { id: "pan", label: "Pan", icon: "✋", key: "H", hint: "Drag to pan · scroll wheel pans · ⌘/Ctrl+scroll or pinch zooms" },
  { id: "paint", label: "Paint tiles", icon: "🖌", key: "B", hint: "Click / drag to paint · Alt-click samples a tile · [ ] adjusts brush size" },
  { id: "erase", label: "Erase tiles", icon: "◻", key: "E", hint: "Click / drag to erase tiles on the target layer · [ ] adjusts brush size" },
  { id: "rect", label: "Rectangle fill", icon: "▭", key: "R", hint: "Drag a rectangle to fill with the selected tile · hold Alt to erase the area" },
  { id: "fill", label: "Flood fill", icon: "🪣", key: "G", hint: "Click to flood-fill a contiguous region on the target layer" },
  { id: "picker", label: "Eyedropper", icon: "💉", key: "I", hint: "Click a painted tile to pick its tile type and layer" },
  { id: "prop", label: "Place props", icon: "🌳", key: "P", hint: "Click to place the selected prop · drag to fine-position before release" },
  { id: "building", label: "Place buildings", icon: "🏠", key: "U", hint: "Click to drop the selected place bundle · R rotates 90° · dressing and entrance path follow the door" },
  { id: "light", label: "Place lights", icon: "✨", key: "L", hint: "Click to place a light · drag to fine-position · corner handle resizes the glow radius" },
  { id: "ambient", label: "Place ambience", icon: "◌", key: "A", hint: "Click to place an ambient effect · drag to align · corner handle resizes the sprite" }
];

export function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

export function tileKey(x: number, y: number): string {
  return `${x},${y}`;
}

export function emptyOverride(): CaseOverride {
  return { visible_locations: [], location_bounds: {}, object_anchors: {} };
}

// --- Building rotation & dressing (mirrors backend place_library.dress_building) ---

// Buildings rotate clockwise in 90° steps. Art is authored with the door on
// the south edge, so the "front" edge walks south → west → north → east.
export const BUILDING_EDGES = ["south", "west", "north", "east"] as const;
export type BuildingEdge = (typeof BUILDING_EDGES)[number];

const rotationSteps = (rotation: number) => ((Math.round(rotation / 90) % 4) + 4) % 4;

export function rotatedFootprint(fp: { w: number; h: number }, rotation: number): { w: number; h: number } {
  return rotationSteps(rotation) % 2 ? { w: fp.h, h: fp.w } : { w: fp.w, h: fp.h };
}

export function buildingFrontEdge(rotation: number): BuildingEdge {
  return BUILDING_EDGES[rotationSteps(rotation)];
}

/** Cells of a strip hugging one edge of the w×h box at (x, y). */
export function edgeStripCells(x: number, y: number, w: number, h: number, edge: BuildingEdge, depth: number): Array<{ x: number; y: number }> {
  const rect = (rx: number, ry: number, rw: number, rh: number) =>
    Array.from({ length: rw }, (_, dx) => Array.from({ length: rh }, (_, dy) => ({ x: rx + dx, y: ry + dy }))).flat();
  if (edge === "south") return rect(x, y + h, w, depth);
  if (edge === "north") return rect(x, y - depth, w, depth);
  if (edge === "west") return rect(x - depth, y, depth, h);
  return rect(x + w, y, depth, h);
}

/** Deterministic dressing for a building placement, honouring rotation. */
export function dressBuilding(
  asset: { footprint: { w: number; h: number }; surrounding_rules?: { front?: string; sides?: string; rear?: string } },
  x: number,
  y: number,
  rotation: number
): Record<string, TileLayer> {
  const { w, h } = rotatedFootprint(asset.footprint, rotation);
  const steps = rotationSteps(rotation);
  const front = BUILDING_EDGES[steps];
  const rear = BUILDING_EDGES[(steps + 2) % 4];
  const sideEdges = [BUILDING_EDGES[(steps + 1) % 4], BUILDING_EDGES[(steps + 3) % 4]];
  const strip = (edge: BuildingEdge, depth: number, tile_id: string): TileEntry[] =>
    edgeStripCells(x, y, w, h, edge, depth).map((c) => ({ ...c, tile_id }));

  const rules = asset.surrounding_rules || {};
  const footprintTiles: TileEntry[] = [];
  for (let dx = 0; dx < w; dx++) for (let dy = 0; dy < h; dy++) footprintTiles.push({ x: x + dx, y: y + dy, tile_id: "tile_wall_exterior" });
  const derived: Record<string, TileLayer> = {
    structures: { tiles: footprintTiles },
    paths: { tiles: rules.front === "path" ? strip(front, 2, "tile_path") : [] },
    terrain_detail: { tiles: [] }
  };
  if (["fence", "hedge", "flowerbed"].includes(rules.sides || "")) {
    for (const edge of sideEdges) derived.terrain_detail.tiles.push(...strip(edge, 1, `tile_${rules.sides}`));
  }
  if (rules.rear === "service_path") derived.paths.tiles.push(...strip(rear, 1, "tile_path"));
  else if (["fence", "hedge", "garden"].includes(rules.rear || "")) {
    derived.terrain_detail.tiles.push(...strip(rear, 1, rules.rear === "garden" ? "tile_flowerbed" : `tile_${rules.rear}`));
  }
  return derived;
}
