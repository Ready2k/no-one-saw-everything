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

export interface TownLayout {
  version: string;
  grid: { cols: number; rows: number; tile_size: number };
  canonical_locations: Record<string, LocationData>;
  case_overrides: Record<string, CaseOverride>;
  tile_layers: Record<string, TileLayer>;
  prop_instances: Record<string, PropInstance[]>;
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
  | "prop";

export type PreviewMode = "debug" | "player_reveal" | "fog";

export type Selection =
  | { kind: "location"; id: string }
  | { kind: "object"; id: string }
  | { kind: "prop"; id: string }
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
  "props", "case_overlays", "object_anchors", "evidence_markers", "fog", "debug_bounds"
];

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
}

export interface UnderlaySourceDef {
  id: string;
  label: string;
  tiles: UnderlayTilePlacement[];
}

// B2 (town centre) ships as a pair, mirroring the runtime contract in
// town_map.py: the external roofed overview and the roofless interior the
// game swaps to past the zoom threshold.
export const HD_B2_EXTERNAL_URL = "/art/town/tiles_3x3_hd/town_overworld_B2_all_cases_external_hd.png";
export const HD_B2_INTERNAL_URL = "/art/town/tiles_3x3_hd/town_overworld_B2_interior_hd.png";

const HD_3X3_TILES: UnderlayTilePlacement[] = (["A", "B", "C"] as const).flatMap((row, r) =>
  ([1, 2, 3] as const).map((col, c) => ({
    url:
      row === "B" && col === 2
        ? HD_B2_EXTERNAL_URL
        : `/art/town/tiles_3x3_hd/town_overworld_${row}${col}_hd.png`,
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
  { id: "prop", label: "Place props", icon: "🌳", key: "P", hint: "Click to place the selected prop · drag to fine-position before release" }
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
