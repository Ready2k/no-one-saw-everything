import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import { useToast } from "../../components/Toast";
import {
  ALLOWED_LAYERS,
  ALLOWED_AMBIENT_ASSETS,
  ALLOWED_LIGHT_ASSETS,
  ALLOWED_PROPS,
  ALLOWED_TILES,
  AMBIENT_ASSET_SWATCHES,
  AmbientSpriteDef,
  Bounds,
  BuildingInstance,
  Camera,
  CaseClueRef,
  CaseObjectRef,
  CaseLocationRef,
  CaseRef,
  FLOOD_FILL_LIMIT,
  HISTORY_LIMIT,
  HD_B2_INTERNAL_URL,
  HD_TILE_CELLS,
  LIGHT_ASSET_SWATCHES,
  LightDef,
  LocationSource,
  MapView,
  MAX_SCALE,
  MIN_SCALE,
  PROP_EMOJIS,
  PreviewMode,
  PropInstance,
  RENDER_POLICIES,
  Selection,
  TILE_COLORS,
  TOOL_DEFS,
  TileArtVariant,
  TileLayer,
  ToolId,
  TownLayout,
  UNDERLAY_SOURCES,
  UnderlaySourceId,
  buildingFrontEdge,
  clamp,
  deepClone,
  dressBuilding,
  emptyOverride,
  hdDefaultTileUrl,
  isNestingAllowed,
  resolveHdTileUrl,
  rotatedFootprint,
  tileKey
} from "./editorTypes";
import { SnapUnderlayTile, snapBoundsToStructure } from "./snapFit";
import { connectAllBuildings, connectBuildingToPaths } from "./pathConnect";
import {
  HANDLE_PX,
  ROTATE_HANDLE_OFFSET_PX,
  Scene,
  SceneAnchor,
  SceneAmbient,
  SceneClue,
  SceneLight,
  SceneLocation,
  SceneProp,
  ToolOverlay,
  drawMinimap,
  drawScene,
  minimapToWorld
} from "./renderer";

// ---------------------------------------------------------------------------
// Pure layout resolvers / mutators (shared between canvas gestures and panels)
// ---------------------------------------------------------------------------

type CanonicalRecs = Record<string, { bounds: Bounds; mode: string }>;

interface EffectiveLocation {
  bounds: Bounds;
  mode: string;
  source: LocationSource;
  isOverridden: boolean;
}

function resolveLocation(
  layout: TownLayout,
  recs: CanonicalRecs,
  caseId: string,
  locId: string
): EffectiveLocation {
  let bounds = recs[locId]?.bounds || { x: 4, y: 4, w: 6, h: 6 };
  let mode = recs[locId]?.mode || "exterior";
  let source: LocationSource = "recommended";
  let isOverridden = false;

  if (layout.canonical_locations[locId]) {
    bounds = layout.canonical_locations[locId].bounds;
    mode = layout.canonical_locations[locId].mode;
    source = "canonical";
  }
  if (caseId !== "canonical" && layout.case_overrides[caseId]?.location_bounds[locId]) {
    bounds = layout.case_overrides[caseId].location_bounds[locId];
    source = "case_override";
    isOverridden = true;
  }
  return { bounds, mode, source, isOverridden };
}

function resolveAnchor(
  layout: TownLayout,
  recs: CanonicalRecs,
  caseId: string,
  obj: CaseObjectRef
) {
  const a = layout.case_overrides[caseId]?.object_anchors[obj.object_id];
  if (a) {
    return {
      location_id: a.location_id,
      anchor: a.anchor,
      semantic_asset_id: a.semantic_asset_id,
      render_policy: a.render_policy,
      external: a.external
    };
  }
  const locId = obj.normal_location_id || obj.final_location_id || "loc_village_square";
  const lb = resolveLocation(layout, recs, caseId, locId).bounds;
  return {
    location_id: locId,
    anchor: { x: Math.floor(lb.x + lb.w / 2), y: Math.floor(lb.y + lb.h / 2) },
    semantic_asset_id: "",
    render_policy: "discovery_gated",
    external: false
  };
}

function resolveClueWorldPosition(
  layout: TownLayout,
  recs: CanonicalRecs,
  caseId: string,
  clue: CaseClueRef,
  view: MapView,
  sceneScreen = false
): { x: number; y: number; bounds: Bounds } | null {
  if (!clue.location_id) return null;
  if (sceneScreen) {
    return {
      x: clue.x ?? 50,
      y: clue.y ?? 50,
      bounds: { x: 0, y: 0, w: 100, h: 100 }
    };
  }
  const bounds = resolveLocationView(layout, recs, caseId, clue.location_id, view).bounds;
  return {
    x: bounds.x + ((clue.x ?? 50) / 100) * bounds.w,
    y: bounds.y + ((clue.y ?? 50) / 100) * bounds.h,
    bounds
  };
}

function worldToCluePercent(bounds: Bounds, x: number, y: number): { x: number; y: number } {
  return {
    x: clamp(((x - bounds.x) / bounds.w) * 100, 0, 100),
    y: clamp(((y - bounds.y) / bounds.h) * 100, 0, 100)
  };
}

/**
 * Resolve bounds for the requested map view. External behaves exactly like
 * resolveLocation; internal uses canonical bounds_internal when authored and
 * inherits the external effective bounds otherwise.
 */
function resolveLocationView(
  layout: TownLayout,
  recs: CanonicalRecs,
  caseId: string,
  locId: string,
  view: MapView
): EffectiveLocation & { hasInternal: boolean } {
  const ext = resolveLocation(layout, recs, caseId, locId);
  const internal = layout.canonical_locations[locId]?.bounds_internal;
  if (view === "external") return { ...ext, hasInternal: !!internal };
  if (internal) {
    return { bounds: internal, mode: ext.mode, source: "internal", isOverridden: false, hasInternal: true };
  }
  return { ...ext, hasInternal: false };
}

function rotateVec(dx: number, dy: number, deg: number): { x: number; y: number } {
  const r = (deg * Math.PI) / 180;
  const cos = Math.cos(r);
  const sin = Math.sin(r);
  return { x: dx * cos - dy * sin, y: dx * sin + dy * cos };
}

/** Point-in-bounds test honouring the visual rotation around the centre. */
function boundsContainsPoint(b: Bounds, wx: number, wy: number): boolean {
  const cx = b.x + b.w / 2;
  const cy = b.y + b.h / 2;
  const local = rotateVec(wx - cx, wy - cy, -(b.rotation || 0));
  return Math.abs(local.x) <= b.w / 2 && Math.abs(local.y) <= b.h / 2;
}

/** Normalize degrees to (-180, 180]; 0 is returned as undefined so unrotated
 * bounds stay clean in the saved JSON. */
function normalizeRotation(deg: number): number | undefined {
  const norm = ((((deg + 180) % 360) + 360) % 360) - 180;
  return norm === 0 ? undefined : norm;
}

function rectCorners(b: Bounds): Array<{ x: number; y: number }> {
  const cx = b.x + b.w / 2;
  const cy = b.y + b.h / 2;
  return [
    { x: -b.w / 2, y: -b.h / 2 },
    { x: b.w / 2, y: -b.h / 2 },
    { x: b.w / 2, y: b.h / 2 },
    { x: -b.w / 2, y: b.h / 2 }
  ].map((p) => {
    const r = rotateVec(p.x, p.y, b.rotation || 0);
    return { x: cx + r.x, y: cy + r.y };
  });
}

/** Separating-axis overlap for possibly-rotated bounds (touching edges do
 * not count as overlap, matching the server validator). */
function orientedOverlap(a: Bounds, b: Bounds): boolean {
  const ca = rectCorners(a);
  const cb = rectCorners(b);
  for (const corners of [ca, cb]) {
    for (let i = 0; i < 4; i++) {
      const p1 = corners[i];
      const p2 = corners[(i + 1) % 4];
      const axisX = p2.y - p1.y;
      const axisY = p1.x - p2.x;
      const pa = ca.map((p) => axisX * p.x + axisY * p.y);
      const pb = cb.map((p) => axisX * p.x + axisY * p.y);
      if (Math.max(...pa) <= Math.min(...pb) + 1e-9 || Math.max(...pb) <= Math.min(...pa) + 1e-9) {
        return false;
      }
    }
  }
  return true;
}

function isLocationVisibleIn(layout: TownLayout, caseId: string, locId: string): boolean {
  if (caseId === "canonical") return true;
  const ov = layout.case_overrides[caseId];
  if (!ov) return false;
  return ov.visible_locations.includes(locId);
}

function applyLocationBounds(
  layout: TownLayout,
  recs: CanonicalRecs,
  caseId: string,
  locId: string,
  updates: Partial<Bounds>
): void {
  if (caseId === "canonical") {
    if (!layout.canonical_locations[locId]) {
      const eff = resolveLocation(layout, recs, "canonical", locId);
      layout.canonical_locations[locId] = { bounds: { ...eff.bounds }, mode: eff.mode };
    }
    Object.assign(layout.canonical_locations[locId].bounds, updates);
  } else {
    if (!layout.case_overrides[caseId]) layout.case_overrides[caseId] = emptyOverride();
    const eff = resolveLocation(layout, recs, caseId, locId);
    layout.case_overrides[caseId].location_bounds[locId] = { ...eff.bounds, ...updates };
  }
}

/**
 * Write bounds for the given view. Internal-view bounds live only at the
 * canonical level (the interior art is shared by all cases); the first
 * internal edit seeds bounds_internal from the current effective bounds.
 */
function applyLocationBoundsView(
  layout: TownLayout,
  recs: CanonicalRecs,
  caseId: string,
  locId: string,
  updates: Partial<Bounds>,
  view: MapView
): void {
  if (view === "external") {
    applyLocationBounds(layout, recs, caseId, locId, updates);
    return;
  }
  if (!layout.canonical_locations[locId]) {
    const eff = resolveLocation(layout, recs, "canonical", locId);
    layout.canonical_locations[locId] = { bounds: { ...eff.bounds }, mode: eff.mode };
  }
  const rec = layout.canonical_locations[locId];
  if (!rec.bounds_internal) {
    rec.bounds_internal = { ...resolveLocation(layout, recs, caseId, locId).bounds };
  }
  Object.assign(rec.bounds_internal, updates);
}

interface EffectiveLight {
  x: number;
  y: number;
  width: number;
  height: number;
  semantic_asset_id: string;
  opacity?: number;
}

function findLight(layout: TownLayout, id: string): LightDef | undefined {
  return (layout.lights || {})[id];
}

/**
 * Resolve a light's geometry/asset for the requested map view. Internal-view
 * fields are optional overrides on the same record (not a separate
 * collection) — same relationship as LocationData.bounds/bounds_internal,
 * just flattened since a light has no nested Bounds object. Falls back to
 * the external values field-by-field when an internal override is absent.
 */
function resolveLightView(light: LightDef, view: MapView): EffectiveLight & { hasInternal: boolean } {
  const hasInternal = light.x_internal != null && light.y_internal != null;
  if (view === "external" || !hasInternal) {
    return {
      x: light.x,
      y: light.y,
      width: light.width,
      height: light.height,
      semantic_asset_id: light.semantic_asset_id,
      opacity: light.opacity,
      hasInternal
    };
  }
  return {
    x: light.x_internal!,
    y: light.y_internal!,
    width: light.width_internal ?? light.width,
    height: light.height_internal ?? light.height,
    semantic_asset_id: light.semantic_asset_id_internal ?? light.semantic_asset_id,
    opacity: light.opacity_internal ?? light.opacity,
    hasInternal
  };
}

/**
 * Write geometry/asset updates for the given view. Internal-view edits seed
 * the *_internal fields from the current external values on first touch
 * (mirrors applyLocationBoundsView seeding bounds_internal from bounds), so
 * an author who only nudges the internal position doesn't lose the rest of
 * the external-derived defaults.
 */
function applyLightView(light: LightDef, updates: Partial<EffectiveLight>, view: MapView): void {
  if (view === "external") {
    Object.assign(light, updates);
    return;
  }
  if (light.x_internal == null) light.x_internal = light.x;
  if (light.y_internal == null) light.y_internal = light.y;
  if (light.width_internal == null) light.width_internal = light.width;
  if (light.height_internal == null) light.height_internal = light.height;
  if (updates.x !== undefined) light.x_internal = updates.x;
  if (updates.y !== undefined) light.y_internal = updates.y;
  if (updates.width !== undefined) light.width_internal = updates.width;
  if (updates.height !== undefined) light.height_internal = updates.height;
  if (updates.semantic_asset_id !== undefined) light.semantic_asset_id_internal = updates.semantic_asset_id;
  if (updates.opacity !== undefined) light.opacity_internal = updates.opacity;
}

function applyLightUpdate(layout: TownLayout, id: string, fn: (light: LightDef) => void): boolean {
  const light = findLight(layout, id);
  if (!light) return false;
  fn(light);
  return true;
}

function findAmbient(layout: TownLayout, id: string): AmbientSpriteDef | undefined {
  return (layout.ambient_sprites || {})[id];
}

function applyAmbientUpdate(layout: TownLayout, id: string, fn: (sprite: AmbientSpriteDef) => void): boolean {
  const sprite = findAmbient(layout, id);
  if (!sprite) return false;
  fn(sprite);
  return true;
}

function applyAnchor(
  layout: TownLayout,
  recs: CanonicalRecs,
  caseId: string,
  obj: CaseObjectRef,
  updates: Partial<{ x: number; y: number }>
): void {
  if (caseId === "canonical") return;
  if (!layout.case_overrides[caseId]) layout.case_overrides[caseId] = emptyOverride();
  const eff = resolveAnchor(layout, recs, caseId, obj);
  layout.case_overrides[caseId].object_anchors[obj.object_id] = {
    location_id: eff.location_id,
    anchor: { ...eff.anchor, ...updates },
    semantic_asset_id: eff.semantic_asset_id || "",
    render_policy: eff.render_policy || "discovery_gated",
    external: eff.external || false
  };
}

function applyPropUpdate(
  layout: TownLayout,
  instanceId: string,
  fn: (p: PropInstance) => void
): boolean {
  for (const scope of Object.keys(layout.prop_instances || {})) {
    const p = layout.prop_instances[scope].find((q) => q.instance_id === instanceId);
    if (p) {
      fn(p);
      return true;
    }
  }
  return false;
}

function findProp(layout: TownLayout, instanceId: string): { prop: PropInstance; scope: string } | null {
  for (const scope of Object.keys(layout.prop_instances || {})) {
    const p = layout.prop_instances[scope].find((q) => q.instance_id === instanceId);
    if (p) return { prop: p, scope };
  }
  return null;
}

function mergedProps(layout: TownLayout, caseId: string): PropInstance[] {
  const canonical = layout.prop_instances?.["canonical"] || [];
  const caseProps = caseId !== "canonical" ? layout.prop_instances?.[caseId] || [] : [];
  return [...canonical, ...caseProps];
}

function ensureLayer(layout: TownLayout, layerName: string): TileLayer {
  if (!layout.tile_layers) layout.tile_layers = {};
  if (!layout.tile_layers[layerName]) layout.tile_layers[layerName] = { tiles: [] };
  return layout.tile_layers[layerName];
}

// --- Location contents (anchors + props) follow the location when it moves ---

type AttachedItem =
  | { kind: "anchor"; caseId: string; objId: string; ox: number; oy: number }
  | { kind: "prop"; scope: string; id: string; ox: number; oy: number };

/**
 * Everything positioned inside a location's current bounds that should move
 * with it: evidence anchors (only in cases whose effective bounds are the ones
 * being edited) and prop instances assigned to the location.
 */
function collectAttached(
  l: TownLayout,
  scopeCaseId: string,
  locId: string,
  b: Bounds
): AttachedItem[] {
  const inside = (x: number, y: number) =>
    x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h;
  const out: AttachedItem[] = [];
  for (const [caseId, ov] of Object.entries(l.case_overrides || {})) {
    // Editing canonical bounds doesn't affect a case that pins its own bounds
    if (scopeCaseId === "canonical" ? !!ov.location_bounds?.[locId] : caseId !== scopeCaseId) continue;
    for (const [objId, a] of Object.entries(ov.object_anchors || {})) {
      if (a.location_id === locId && inside(a.anchor.x, a.anchor.y)) {
        out.push({ kind: "anchor", caseId, objId, ox: a.anchor.x, oy: a.anchor.y });
      }
    }
  }
  for (const [scope, list] of Object.entries(l.prop_instances || {})) {
    for (const p of list) {
      if (p.location_id === locId && inside(p.x, p.y)) {
        out.push({ kind: "prop", scope, id: p.instance_id, ox: p.x, oy: p.y });
      }
    }
  }
  return out;
}

/** Reposition collected items at their original offset plus the location's delta. */
function applyAttached(
  l: TownLayout,
  items: AttachedItem[],
  dx: number,
  dy: number,
  cols: number,
  rows: number
): void {
  if (dx === 0 && dy === 0) return;
  for (const it of items) {
    const nx = clamp(it.ox + dx, 0, cols - 1);
    const ny = clamp(it.oy + dy, 0, rows - 1);
    if (it.kind === "anchor") {
      const a = l.case_overrides?.[it.caseId]?.object_anchors?.[it.objId];
      if (a) {
        a.anchor.x = nx;
        a.anchor.y = ny;
      }
    } else {
      const p = l.prop_instances?.[it.scope]?.find((q) => q.instance_id === it.id);
      if (p) {
        p.x = nx;
        p.y = ny;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Gestures
// ---------------------------------------------------------------------------

type Gesture =
  | { kind: "pan"; lastX: number; lastY: number }
  | { kind: "paint"; before: TownLayout; erase: boolean; last: { x: number; y: number }; painted: Set<string> }
  | { kind: "rect"; before: TownLayout; start: { x: number; y: number }; current: { x: number; y: number }; erase: boolean }
  | { kind: "moveLoc"; before: TownLayout; id: string; startW: { wx: number; wy: number }; orig: Bounds; mutated: boolean; attached: AttachedItem[] }
  | { kind: "resizeLoc"; before: TownLayout; id: string; startW: { wx: number; wy: number }; orig: Bounds; mutated: boolean }
  | { kind: "rotateLoc"; before: TownLayout; id: string; center: { x: number; y: number }; startAngle: number; origRot: number; mutated: boolean }
  | { kind: "moveAnchor"; before: TownLayout; id: string; startW: { wx: number; wy: number }; orig: { x: number; y: number }; mutated: boolean }
  | { kind: "moveClue"; before: TownLayout; id: string; startW: { wx: number; wy: number }; orig: { x: number; y: number }; bounds: Bounds; mutated: boolean }
  | { kind: "moveProp"; before: TownLayout; id: string; startW: { wx: number; wy: number }; orig: { x: number; y: number }; mutated: boolean }
  | { kind: "resizeProp"; before: TownLayout; id: string; startW: { wx: number; wy: number }; orig: { w: number; h: number }; mutated: boolean }
  | { kind: "moveBuilding"; before: TownLayout; id: string; startW: { wx: number; wy: number }; orig: { x: number; y: number }; mutated: boolean }
  | { kind: "moveLight"; before: TownLayout; id: string; startW: { wx: number; wy: number }; orig: { x: number; y: number }; mutated: boolean }
  | { kind: "resizeLight"; before: TownLayout; id: string; startW: { wx: number; wy: number }; orig: { width: number; height: number }; mutated: boolean }
  | { kind: "moveAmbient"; before: TownLayout; id: string; startW: { wx: number; wy: number }; orig: { x: number; y: number }; mutated: boolean }
  | { kind: "resizeAmbient"; before: TownLayout; id: string; startW: { wx: number; wy: number }; orig: { width: number; height: number }; mutated: boolean };

interface MirrorState {
  selectedCaseId: string;
  activeTool: ToolId;
  selection: Selection;
  mapView: MapView;
  interiorSceneLocationId: string | null;
  previewMode: PreviewMode;
  showEvidenceAnchors: boolean;
  underlaySource: UnderlaySourceId;
  underlayOpacity: number;
  solidRenderView: boolean;
  showGrid: boolean;
  showLabels: boolean;
  showSafety: boolean;
  showMinimap: boolean;
  visibleLayers: Record<string, boolean>;
  selectedTileId: string;
  selectedPropId: string;
  selectedBuildingId: string;
  selectedLightAssetId: string;
  selectedAmbientAssetId: string;
  buildingRotation: number;
  paintLayer: string;
  propLayer: string;
  brushSize: number;
  fineAdjustment: boolean;
  activeLocations: CaseLocationRef[];
  activeObjects: CaseObjectRef[];
  activeClues: CaseClueRef[];
  canonicalRecs: CanonicalRecs;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DevMapEditor() {
  const { showToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [layout, setLayout] = useState<TownLayout | null>(null);
  const [cases, setCases] = useState<CaseRef[]>([]);
  const [canonicalRecs, setCanonicalRecs] = useState<CanonicalRecs>({});

  const [history, setHistory] = useState<TownLayout[]>([]);
  const [redoStack, setRedoStack] = useState<TownLayout[]>([]);
  const [isDirty, setIsDirty] = useState(false);
  // The layout_version this session last loaded/saved at. Sent with every
  // save so the server can reject (409) a save based on stale data instead
  // of silently overwriting a more recent save from another tab/session.
  const [layoutVersion, setLayoutVersion] = useState<string | null>(null);
  const [serverErrors, setServerErrors] = useState<string[]>([]);

  const [activeTool, setActiveTool] = useState<ToolId>("select");
  const [selectedTileId, setSelectedTileId] = useState("tile_grass");
  const [selectedPropId, setSelectedPropId] = useState("prop_bench");
  const [selectedLightAssetId, setSelectedLightAssetId] = useState(ALLOWED_LIGHT_ASSETS[0]);
  const [selectedAmbientAssetId, setSelectedAmbientAssetId] = useState(ALLOWED_AMBIENT_ASSETS[0]);
  const [selectedBuildingId, setSelectedBuildingId] = useState("cafe_small_v1");
  const [buildingRotation, setBuildingRotation] = useState(0);
  const [buildingLibrary, setBuildingLibrary] = useState<Record<string, any>>({});
  const buildingLibraryRef = useRef<Record<string, any>>({});
  const [paintLayer, setPaintLayer] = useState("base");
  const [propLayer, setPropLayer] = useState("props");
  const [brushSize, setBrushSize] = useState(1);

  const [selectedCaseId, setSelectedCaseId] = useState("canonical");
  const [selection, setSelection] = useState<Selection>(null);
  const [mapView, setMapView] = useState<MapView>("external");
  const [interiorSceneLocationId, setInteriorSceneLocationId] = useState<string | null>(null);

  const [previewMode, setPreviewMode] = useState<PreviewMode>("debug");
  const [fineAdjustment, setFineAdjustment] = useState(false);
  const [showEvidenceAnchors, setShowEvidenceAnchors] = useState(true);
  const [underlaySource, setUnderlaySource] = useState<UnderlaySourceId>("town_tiles_hd");
  const [tileArtVariants, setTileArtVariants] = useState<Record<string, TileArtVariant[]>>({});
  const [underlayOpacity, setUnderlayOpacity] = useState(0.5);
  const [solidRenderView, setSolidRenderView] = useState(false);
  const [showGrid, setShowGrid] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showSafety, setShowSafety] = useState(true);
  const [showMinimap, setShowMinimap] = useState(true);
  const [visibleLayers, setVisibleLayers] = useState<Record<string, boolean>>(() => {
    const d: Record<string, boolean> = {};
    ALLOWED_LAYERS.forEach((l) => (d[l] = true));
    return d;
  });

  const [locationSearch, setLocationSearch] = useState("");
  const [clueSearch, setClueSearch] = useState("");
  const [showExportModal, setShowExportModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [importText, setImportText] = useState("");

  // --- Refs (canvas world, not React world) ---
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const minimapRef = useRef<HTMLCanvasElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const layoutRef = useRef<TownLayout | null>(null);
  const casesRef = useRef<CaseRef[]>([]);
  const cameraRef = useRef<Camera>({ x: 0, y: 0, scale: 6 });
  // w/h start at 0 so the initial fit waits for a real ResizeObserver measurement
  const sizeRef = useRef({ w: 0, h: 0, dpr: 1 });
  const gestureRef = useRef<Gesture | null>(null);
  const hoverRef = useRef<{ x: number; y: number } | null>(null);
  const hoverLocRef = useRef<string | null>(null);
  const spaceRef = useRef(false);
  const rafPending = useRef(false);
  const didFitRef = useRef(false);
  const underlayImgs = useRef<Record<string, HTMLImageElement>>({});
  const lastSceneRef = useRef<Scene | null>(null);
  const minimapDragRef = useRef(false);
  const stateRef = useRef<MirrorState | null>(null);
  const keyDownRef = useRef<(e: KeyboardEvent) => void>(() => {});
  const keyUpRef = useRef<(e: KeyboardEvent) => void>(() => {});

  const statusCoordsRef = useRef<HTMLSpanElement>(null);
  const statusHoverLocRef = useRef<HTMLSpanElement>(null);
  const zoomLabelRef = useRef<HTMLSpanElement>(null);
  const statusZoomRef = useRef<HTMLSpanElement>(null);

  const cols = layout?.grid?.cols || 192;
  const rows = layout?.grid?.rows || 144;

  const selectedArtLocationId = (
    lay: TownLayout,
    st: MirrorState
  ): string | null => {
    if (st.selection?.kind === "clue") {
      return st.activeClues.find((c) => c.clue_id === st.selection?.id)?.location_id || null;
    }
    if (st.selection?.kind === "location") return st.selection.id;
    if (st.selection?.kind === "object") {
      const obj = st.activeObjects.find((o) => o.object_id === st.selection?.id);
      return obj ? resolveAnchor(lay, st.canonicalRecs, st.selectedCaseId, obj).location_id : null;
    }
    if (st.underlaySource === "selected_location_art" && st.interiorSceneLocationId) return st.interiorSceneLocationId;
    return hoverLocRef.current;
  };

  const isInteriorSceneScreen = (st: MirrorState): boolean => st.underlaySource === "selected_location_art";

  const selectedArtUnderlays = (lay: TownLayout, st: MirrorState) => {
    const locId = selectedArtLocationId(lay, st);
    const loc = locId ? st.activeLocations.find((l) => l.location_id === locId) : null;
    const url = loc?.search_illustration;
    if (!locId || !url) return [];
    if (isInteriorSceneScreen(st)) {
      return [{ img: underlayImgs.current[url], x: 0, y: 0, w: 100, h: 100 }].filter((u) => !!u.img);
    }
    const bounds = resolveLocationView(lay, st.canonicalRecs, st.selectedCaseId, locId, st.mapView).bounds;
    return [{ img: underlayImgs.current[url], x: bounds.x, y: bounds.y, w: bounds.w, h: bounds.h }].filter((u) => !!u.img);
  };

  // --- Derived collections ---
  const activeLocations = useMemo<CaseLocationRef[]>(() => {
    if (selectedCaseId === "canonical") {
      const all = new Map<string, CaseLocationRef>();
      cases.forEach((c) => c.locations.forEach((l) => all.set(l.location_id, l)));
      return Array.from(all.values());
    }
    return cases.find((c) => c.case_id === selectedCaseId)?.locations || [];
  }, [cases, selectedCaseId]);

  const activeObjects = useMemo<CaseObjectRef[]>(() => {
    if (selectedCaseId === "canonical") return [];
    return cases.find((c) => c.case_id === selectedCaseId)?.objects || [];
  }, [cases, selectedCaseId]);

  const activeClues = useMemo<CaseClueRef[]>(() => {
    if (selectedCaseId === "canonical") return [];
    return (cases.find((c) => c.case_id === selectedCaseId)?.clues || []).filter(
      (c) => c.method === "inspect" && !(c.reveal_on || []).includes("examine_body")
    );
  }, [cases, selectedCaseId]);

  const activeBodyClues = useMemo<CaseClueRef[]>(() => {
    if (selectedCaseId === "canonical") return [];
    return (cases.find((c) => c.case_id === selectedCaseId)?.clues || []).filter(
      (c) => c.method === "inspect" && (c.reveal_on || []).includes("examine_body")
    );
  }, [cases, selectedCaseId]);

  const activeProps = useMemo<PropInstance[]>(() => {
    if (!layout) return [];
    return mergedProps(layout, selectedCaseId);
  }, [layout, selectedCaseId]);

  // Mirrors backend validate_town_layout_payload (town_map.py) across ALL scopes,
  // so anything that would 400 on save is flagged here first.
  const validationWarnings = useMemo<string[]>(() => {
    const w: string[] = [];
    if (!layout) return w;
    const contract = new Set(Object.keys(canonicalRecs));
    const gCols = layout.grid?.cols || 192;
    const gRows = layout.grid?.rows || 144;
    const inGrid = (b: Bounds) => b.x >= 0 && b.y >= 0 && b.x + b.w <= gCols && b.y + b.h <= gRows;

    // Canonical location entries (external + internal view sets)
    const canonicalBounds: Record<string, Bounds> = {};
    const internalBounds: Record<string, Bounds> = {};
    for (const [locId, data] of Object.entries(layout.canonical_locations || {})) {
      if (!contract.has(locId)) {
        w.push(`Canonical location "${locId}" is not in the canonical contract.`);
      }
      const b = data?.bounds;
      if (!b) continue;
      canonicalBounds[locId] = b;
      // Internal-view overlaps only compare authored internal bounds;
      // inherited external rectangles aren't internal-art footprints.
      if (data.bounds_internal) internalBounds[locId] = data.bounds_internal;
      if (b.w <= 0 || b.h <= 0) {
        w.push(`Bounds for "${locId}" must have positive width and height.`);
      } else if (!inGrid(b)) {
        w.push(`Bounds for "${locId}" extend outside the ${gCols}×${gRows} grid.`);
      }
      const bi = data.bounds_internal;
      if (bi) {
        if (bi.w <= 0 || bi.h <= 0) {
          w.push(`Internal bounds for "${locId}" must have positive width and height.`);
        } else if (!inGrid(bi)) {
          w.push(`Internal bounds for "${locId}" extend outside the ${gCols}×${gRows} grid.`);
        }
      }
      if (data.mode !== "interior" && data.mode !== "exterior") {
        w.push(`Location "${locId}" has invalid mode "${data.mode}".`);
      }
    }
    const checkSetOverlaps = (set: Record<string, Bounds>, label: string) => {
      const ids = Object.keys(set);
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          if (isNestingAllowed(ids[i], ids[j])) continue;
          if (orientedOverlap(set[ids[i]], set[ids[j]])) {
            w.push(`Overlap between "${ids[i]}" and "${ids[j]}"${label} without parent-child allowance.`);
          }
        }
      }
    };
    checkSetOverlaps(canonicalBounds, "");
    checkSetOverlaps(internalBounds, " in the internal view");

    // Per-case overrides (every case, not just the selected scope)
    for (const c of cases) {
      const ov = layout.case_overrides?.[c.case_id];
      if (!ov) continue;
      const tag = c.case_id.toUpperCase();
      const caseLocIds = new Set(c.locations.map((l) => l.location_id));

      for (const [locId, b] of Object.entries(ov.location_bounds || {})) {
        if (!caseLocIds.has(locId) && !contract.has(locId)) {
          w.push(`[${tag}] Override references unknown location "${locId}".`);
        }
        if (b.w <= 0 || b.h <= 0) {
          w.push(`[${tag}] Override bounds for "${locId}" must have positive width and height.`);
        } else if (!inGrid(b)) {
          w.push(`[${tag}] Override bounds for "${locId}" extend outside the grid.`);
        }
      }

      const visible = ov.visible_locations || [];
      const eff: Record<string, Bounds> = {};
      for (const locId of visible) {
        eff[locId] = resolveLocation(layout, canonicalRecs, c.case_id, locId).bounds;
      }
      const vIds = Object.keys(eff);
      for (let i = 0; i < vIds.length; i++) {
        for (let j = i + 1; j < vIds.length; j++) {
          if (isNestingAllowed(vIds[i], vIds[j])) continue;
          if (orientedOverlap(eff[vIds[i]], eff[vIds[j]])) {
            w.push(`[${tag}] Visible locations "${vIds[i]}" and "${vIds[j]}" overlap without parent-child allowance.`);
          }
        }
      }

      for (const obj of c.objects) {
        const a = ov.object_anchors?.[obj.object_id];
        if (!a) continue;
        const policy = a.render_policy || "discovery_gated";
        if (policy !== "debug_only" && !visible.includes(a.location_id)) {
          w.push(
            `[${tag}] Anchor "${obj.object_id}" sits in hidden location "${a.location_id}" — mark that location visible in this case, or set the anchor's policy to Debug Only.`
          );
        }
        if (a.anchor.x < 0 || a.anchor.y < 0 || a.anchor.x >= gCols || a.anchor.y >= gRows) {
          w.push(`[${tag}] Anchor "${obj.object_id}" lies outside the grid.`);
        } else if (!a.external) {
          // Anchors are placed against the art, which may be aligned in
          // either view: containment in the external bounds OR the authored
          // internal-view bounds counts, honouring rotation.
          const ext = resolveLocation(layout, canonicalRecs, c.case_id, a.location_id).bounds;
          const internal = layout.canonical_locations[a.location_id]?.bounds_internal;
          const inside =
            boundsContainsPoint(ext, a.anchor.x, a.anchor.y) ||
            (!!internal && boundsContainsPoint(internal, a.anchor.x, a.anchor.y));
          if (!inside) {
            w.push(
              `[${tag}] Anchor "${obj.object_id}" is outside both the external and internal bounds of "${a.location_id}".`
            );
          }
        }
      }
    }

    // Prop instances across all scopes
    for (const [scope, list] of Object.entries(layout.prop_instances || {})) {
      for (const p of list) {
        if (!contract.has(p.location_id)) {
          w.push(`Prop "${p.instance_id}" (${scope}) is assigned to unknown location "${p.location_id}".`);
        }
        if (p.x < 0 || p.y < 0 || p.x >= gCols || p.y >= gRows) {
          w.push(`Prop "${p.instance_id}" (${scope}) sits outside the grid.`);
        }
        if (p.render_policy === "discovery_gated" && !p.object_id) {
          w.push(`Prop "${p.instance_id}" (${scope}) is discovery-gated but lacks a linked object_id.`);
        }
      }
    }

    // Lights (global collection; case scoping happens at read time via
    // location_id, not by duplicating entries per case)
    const checkLightGeometry = (x: number, y: number, width: number, height: number, label: string) => {
      if (width <= 0 || height <= 0) w.push(`${label} width and height must be positive.`);
      if (x < 0 || y < 0 || x > gCols || y > gRows) w.push(`${label} centre lies outside the ${gCols}×${gRows} grid.`);
    };
    for (const [id, light] of Object.entries(layout.lights || {})) {
      if (!contract.has(light.location_id)) {
        w.push(`Light "${id}" is assigned to unknown location "${light.location_id}".`);
      }
      if (!ALLOWED_LIGHT_ASSETS.includes(light.semantic_asset_id)) {
        w.push(`Light "${id}" has unknown semantic_asset_id "${light.semantic_asset_id}".`);
      }
      checkLightGeometry(light.x, light.y, light.width, light.height, `Light "${id}"`);
      if (light.x_internal != null && light.y_internal != null) {
        checkLightGeometry(
          light.x_internal,
          light.y_internal,
          light.width_internal ?? light.width,
          light.height_internal ?? light.height,
          `Light "${id}" internal-view`
        );
        if (light.semantic_asset_id_internal && !ALLOWED_LIGHT_ASSETS.includes(light.semantic_asset_id_internal)) {
          w.push(`Light "${id}" has unknown semantic_asset_id_internal "${light.semantic_asset_id_internal}".`);
        }
      }
    }

    return w;
  }, [layout, cases, canonicalRecs]);

  // --- Rendering ---
  const requestRender = () => {
    if (rafPending.current) return;
    rafPending.current = true;
    requestAnimationFrame(() => {
      rafPending.current = false;
      draw();
    });
  };

  const draw = () => {
    const canvas = canvasRef.current;
    const lay = layoutRef.current;
    const st = stateRef.current;
    if (!canvas || !lay || !st) return;

    const gCols = lay.grid?.cols || 192;
    const gRows = lay.grid?.rows || 144;
    const { w, h, dpr } = sizeRef.current;
    const g = gestureRef.current;
    const interiorScreen = isInteriorSceneScreen(st);

    // Locations
    const locations: SceneLocation[] = [];
    if (!interiorScreen && st.visibleLayers["debug_bounds"]) {
      for (const l of st.activeLocations) {
        const eff = resolveLocationView(lay, st.canonicalRecs, st.selectedCaseId, l.location_id, st.mapView);
        const visible = isLocationVisibleIn(lay, st.selectedCaseId, l.location_id);
        if (!visible && st.previewMode === "player_reveal") continue;
        locations.push({
          id: l.location_id,
          name: l.name,
          bounds: eff.bounds,
          source: eff.source,
          alpha: st.previewMode === "fog" && !visible ? 0.15 : 1,
          selected: st.selection?.kind === "location" && st.selection.id === l.location_id,
          hovered: hoverLocRef.current === l.location_id && st.activeTool === "select"
        });
      }
    }

    // Anchors
    const anchors: SceneAnchor[] = [];
    if (!interiorScreen && st.visibleLayers["object_anchors"] && st.showEvidenceAnchors && st.selectedCaseId !== "canonical") {
      for (const o of st.activeObjects) {
        const eff = resolveAnchor(lay, st.canonicalRecs, st.selectedCaseId, o);
        const locVisible = isLocationVisibleIn(lay, st.selectedCaseId, eff.location_id);
        if (st.previewMode === "player_reveal" && !locVisible) continue;
        anchors.push({
          id: o.object_id,
          name: o.name,
          x: eff.anchor.x,
          y: eff.anchor.y,
          alpha: st.previewMode === "fog" && !locVisible ? 0.3 : 1,
          selected: st.selection?.kind === "object" && st.selection.id === o.object_id
        });
      }
    }

    // Clue hotspots
    const clues: SceneClue[] = [];
    if (st.visibleLayers["evidence_markers"] && st.selectedCaseId !== "canonical") {
      const selectedLocId = interiorScreen ? selectedArtLocationId(lay, st) : null;
      for (const c of st.activeClues) {
        if (selectedLocId && c.location_id !== selectedLocId) continue;
        const pos = resolveClueWorldPosition(lay, st.canonicalRecs, st.selectedCaseId, c, st.mapView, interiorScreen);
        if (!pos) continue;
        const locVisible = isLocationVisibleIn(lay, st.selectedCaseId, c.location_id || "");
        if (st.previewMode === "player_reveal" && !locVisible) continue;
        clues.push({
          id: c.clue_id,
          title: c.title,
          x: pos.x,
          y: pos.y,
          radius: c.radius || 8,
          alpha: st.previewMode === "fog" && !locVisible ? 0.3 : 1,
          selected: st.selection?.kind === "clue" && st.selection.id === c.clue_id
        });
      }
    }

    // Lights
    const lights: SceneLight[] = [];
    if (!interiorScreen && st.visibleLayers["lights"]) {
      for (const [id, light] of Object.entries(lay.lights || {})) {
        const eff = resolveLightView(light, st.mapView);
        lights.push({
          id,
          x: eff.x,
          y: eff.y,
          width: eff.width,
          height: eff.height,
          semanticAssetId: eff.semantic_asset_id,
          opacity: eff.opacity,
          selected: st.selection?.kind === "light" && st.selection.id === id
        });
      }
    }

    // Ambient sprites
    const ambientSprites: SceneAmbient[] = [];
    if (!interiorScreen && st.visibleLayers["ambient"]) {
      for (const [id, sprite] of Object.entries(lay.ambient_sprites || {})) {
        ambientSprites.push({
          id,
          assetId: sprite.asset_id,
          x: sprite.x,
          y: sprite.y,
          width: sprite.width,
          height: sprite.height,
          opacity: sprite.opacity,
          selected: st.selection?.kind === "ambient" && st.selection.id === id
        });
      }
    }

    // Props
    const props: SceneProp[] = [];
    if (!interiorScreen) for (const p of mergedProps(lay, st.selectedCaseId)) {
      const layerName = p.layer || "props";
      if (!st.visibleLayers[layerName]) continue;
      props.push({
        id: p.instance_id,
        assetId: p.asset_id,
        x: p.x,
        y: p.y,
        w: p.w || 1,
        h: p.h || 1,
        layer: layerName,
        selected: st.selection?.kind === "prop" && st.selection.id === p.instance_id
      });
    }
    if (!interiorScreen) for (const b of lay.building_instances || []) {
      const footprint = rotatedFootprint(b.footprint || { w: 1, h: 1 }, b.rotation || 0);
      if (st.visibleLayers["structures"]) {
        const artUrl = (st.mapView === "internal" ? b.interior_asset : b.exterior_asset) || b.exterior_asset;
        props.push({
          id: `building:${b.instance_id}`,
          assetId: `building:${b.asset_id}`,
          x: b.x,
          y: b.y,
          w: footprint.w,
          h: footprint.h,
          layer: "structures",
          selected: st.selection?.kind === "building" && st.selection.id === b.instance_id,
          kind: "building",
          img: artUrl ? underlayImgs.current[artUrl] : undefined,
          rotation: b.rotation || 0
        });
      }
    }

    // Tool overlay
    let overlay: ToolOverlay = null;
    const hov = hoverRef.current;
    if (g?.kind === "rect") {
      const r = normRect(g.start, g.current);
      overlay = { kind: "rect", ...r, erase: g.erase, tileId: st.selectedTileId };
    } else if (hov) {
      if (st.activeTool === "paint" || st.activeTool === "erase") {
        overlay = { kind: "brush", cells: brushCells(hov.x, hov.y, st.brushSize, gCols, gRows), erase: st.activeTool === "erase" };
      } else if (st.activeTool === "rect" || st.activeTool === "fill" || st.activeTool === "picker") {
        overlay = { kind: "brush", cells: [{ x: hov.x, y: hov.y }], erase: false };
      } else if (st.activeTool === "prop") {
        overlay = { kind: "propGhost", x: hov.x, y: hov.y, assetId: st.selectedPropId };
      } else if (st.activeTool === "building") {
        const asset = buildingLibraryRef.current[st.selectedBuildingId];
        const fp = asset ? rotatedFootprint(asset.footprint, st.buildingRotation) : { w: 1, h: 1 };
        const ghostUrl = (st.mapView === "internal" ? asset?.interior_asset : asset?.exterior_asset) || asset?.exterior_asset;
        overlay = {
          kind: "propGhost",
          x: hov.x,
          y: hov.y,
          assetId: `building:${st.selectedBuildingId}`,
          w: fp.w,
          h: fp.h,
          front: buildingFrontEdge(st.buildingRotation),
          img: ghostUrl ? underlayImgs.current[ghostUrl] : undefined,
          rotation: st.buildingRotation
        };
      }
    }

    const scene: Scene = {
      cssW: w,
      cssH: h,
      dpr,
      camera: cameraRef.current,
      cols: interiorScreen ? 100 : gCols,
      rows: interiorScreen ? 100 : gRows,
      tileLayers: interiorScreen ? {} : lay.tile_layers || {},
      visibleLayers: st.visibleLayers,
      underlays:
        st.underlaySource === "none"
          ? []
          : st.underlaySource === "selected_location_art"
          ? selectedArtUnderlays(lay, st)
          : (UNDERLAY_SOURCES.find((u) => u.id === st.underlaySource)?.tiles || [])
              .map((t) => {
                // Mosaic cells resolve per view (B2 pairs external/interior
                // art, matching the game's zoom_image_tiles behaviour) and
                // honour the layout's per-cell art overrides.
                const url = t.cell
                  ? resolveHdTileUrl(t.cell, st.mapView, lay.underlay_tile_overrides)
                  : t.url;
                return { img: underlayImgs.current[url], x: t.x, y: t.y, w: t.w, h: t.h };
              })
              .filter((u) => !!u.img),
      underlayOpacity: interiorScreen ? 1 : st.underlayOpacity,
      solidRender: st.solidRenderView,
      showGrid: st.showGrid,
      showSafety: !interiorScreen && st.showSafety,
      showLabels: st.showLabels,
      locations,
      anchors,
      clues,
      props,
      lights,
      ambientSprites,
      overlay
    };
    lastSceneRef.current = scene;
    drawScene(canvas, scene);
    if (st.showMinimap && minimapRef.current) {
      drawMinimap(minimapRef.current, scene);
    }
  };

  // Mirror render-relevant state into a ref, then redraw. Runs every render.
  useEffect(() => {
    stateRef.current = {
      selectedCaseId,
      activeTool,
      selection,
      mapView,
      interiorSceneLocationId,
      previewMode,
      showEvidenceAnchors,
      underlaySource,
      underlayOpacity,
      solidRenderView,
      showGrid,
      showLabels,
      showSafety,
      showMinimap,
      visibleLayers,
      selectedTileId,
      selectedPropId,
      selectedLightAssetId,
      selectedAmbientAssetId,
      selectedBuildingId,
      buildingRotation,
      paintLayer,
      propLayer,
      brushSize,
      fineAdjustment,
      activeLocations,
      activeObjects,
      activeClues,
      canonicalRecs
    };
    requestRender();
  });

  useEffect(() => {
    layoutRef.current = layout;
    requestRender();
  }, [layout]);

  useEffect(() => {
    casesRef.current = cases;
    for (const c of cases) {
      for (const loc of c.locations || []) {
        const url = loc.search_illustration;
        if (!url || underlayImgs.current[url]) continue;
        const img = new Image();
        img.src = url;
        img.onload = () => requestRender();
        underlayImgs.current[url] = img;
      }
    }
  }, [cases]);

  // --- Boot: preload underlays (keyed by URL) + fetch layout ---
  useEffect(() => {
    const urls = UNDERLAY_SOURCES.flatMap((src) => src.tiles.map((t) => t.url));
    urls.push(HD_B2_INTERNAL_URL);
    for (const url of urls) {
      if (underlayImgs.current[url]) continue;
      const img = new Image();
      img.src = url;
      img.onload = () => requestRender();
      underlayImgs.current[url] = img;
    }
    api
      .getDevMapLayout()
      .then((data) => {
        const cleanLayout = {
          ...data.layout,
          tile_layers: data.layout.tile_layers || {},
          prop_instances: data.layout.prop_instances || {},
          building_instances: data.layout.building_instances || [],
          lights: data.layout.lights || {},
          ambient_sprites: data.layout.ambient_sprites || {}
        } as TownLayout;
        setLayout(cleanLayout);
        setLayoutVersion(data.layout_version ?? null);
        setCases((data.cases || []).map((c: CaseRef) => ({ ...c, clues: c.clues || [] })));
        setCanonicalRecs(data.canonical_recommended_locations);
        buildingLibraryRef.current = data.building_library?.buildings || {};
        setBuildingLibrary(buildingLibraryRef.current);
        setTileArtVariants(data.tile_art_variants || {});
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load layout. Enable dev flags.");
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Preload swappable tile art (discovered variants + any saved overrides)
  // so switching a cell's artwork renders without a blank frame.
  useEffect(() => {
    const urls = Object.values(tileArtVariants).flat().map((v) => v.url);
    const overrides = layout?.underlay_tile_overrides;
    if (overrides) {
      for (const cells of Object.values(overrides)) {
        urls.push(...Object.values(cells || {}));
      }
    }
    for (const url of urls) {
      if (!url || underlayImgs.current[url]) continue;
      const img = new Image();
      img.src = url;
      img.onload = () => requestRender();
      underlayImgs.current[url] = img;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tileArtVariants, layout?.underlay_tile_overrides]);

  // Preload building bundle art so placed buildings and the placement ghost
  // render as real artwork instead of placeholder boxes.
  useEffect(() => {
    for (const b of Object.values(buildingLibrary)) {
      for (const url of [b.exterior_asset, b.interior_asset]) {
        if (!url || underlayImgs.current[url]) continue;
        const img = new Image();
        img.src = url;
        img.onload = () => requestRender();
        underlayImgs.current[url] = img;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildingLibrary]);

  // Unsaved-changes guard
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "You have unsaved changes in the map editor. Are you sure you want to leave?";
        return e.returnValue;
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  // --- Canvas sizing ---
  useEffect(() => {
    if (loading) return;
    const el = workspaceRef.current;
    const canvas = canvasRef.current;
    if (!el || !canvas) return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.round(r.width * dpr));
      canvas.height = Math.max(1, Math.round(r.height * dpr));
      canvas.style.width = `${r.width}px`;
      canvas.style.height = `${r.height}px`;
      sizeRef.current = { w: r.width, h: r.height, dpr };
      tryInitialFit();
      requestRender();
    });
    ro.observe(el);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  const tryInitialFit = () => {
    if (didFitRef.current || !layoutRef.current || sizeRef.current.w < 60) return;
    didFitRef.current = true;
    fitView();
  };

  useEffect(() => {
    if (layout) tryInitialFit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layout]);

  // Minimap needs its own backing-store sizing
  useEffect(() => {
    const mm = minimapRef.current;
    if (!mm || !showMinimap) return;
    const dpr = window.devicePixelRatio || 1;
    mm.width = Math.round(220 * dpr);
    mm.height = Math.round(165 * dpr);
    mm.style.width = "220px";
    mm.style.height = "165px";
    requestRender();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showMinimap, loading]);

  // --- Camera ---
  const clampCamera = () => {
    const lay = layoutRef.current;
    if (!lay) return;
    const screen = stateRef.current ? isInteriorSceneScreen(stateRef.current) : false;
    const cam = cameraRef.current;
    const { w, h } = sizeRef.current;
    const vw = w / cam.scale;
    const vh = h / cam.scale;
    const worldCols = screen ? 100 : lay.grid.cols;
    const worldRows = screen ? 100 : lay.grid.rows;
    cam.x = clamp(cam.x, -vw * 0.85, worldCols - vw * 0.15);
    cam.y = clamp(cam.y, -vh * 0.85, worldRows - vh * 0.15);
  };

  const updateZoomLabel = () => {
    const text = `${Math.round((cameraRef.current.scale / 32) * 100)}%`;
    if (zoomLabelRef.current) zoomLabelRef.current.textContent = text;
    if (statusZoomRef.current) statusZoomRef.current.textContent = text;
  };

  const zoomAt = (cssX: number, cssY: number, factor: number) => {
    const cam = cameraRef.current;
    const newScale = clamp(cam.scale * factor, MIN_SCALE, MAX_SCALE);
    const wx = cam.x + cssX / cam.scale;
    const wy = cam.y + cssY / cam.scale;
    cam.scale = newScale;
    cam.x = wx - cssX / newScale;
    cam.y = wy - cssY / newScale;
    clampCamera();
    updateZoomLabel();
    requestRender();
  };

  const zoomCentered = (factor: number) => {
    zoomAt(sizeRef.current.w / 2, sizeRef.current.h / 2, factor);
  };

  const fitView = () => {
    const lay = layoutRef.current;
    if (!lay) return;
    const { w, h } = sizeRef.current;
    const screen = stateRef.current ? isInteriorSceneScreen(stateRef.current) : false;
    const gCols = screen ? 100 : lay.grid.cols;
    const gRows = screen ? 100 : lay.grid.rows;
    const scale = clamp(Math.min((w - 40) / gCols, (h - 40) / gRows), MIN_SCALE, MAX_SCALE);
    cameraRef.current = {
      scale,
      x: gCols / 2 - w / (2 * scale),
      y: gRows / 2 - h / (2 * scale)
    };
    updateZoomLabel();
    requestRender();
  };

  const zoomToBounds = (b: Bounds) => {
    const { w, h } = sizeRef.current;
    const scale = clamp(Math.min(w / (b.w + 10), h / (b.h + 10)), MIN_SCALE, MAX_SCALE);
    cameraRef.current = {
      scale,
      x: b.x + b.w / 2 - w / (2 * scale),
      y: b.y + b.h / 2 - h / (2 * scale)
    };
    updateZoomLabel();
    requestRender();
  };

  // Wheel: plain scroll pans, ⌘/Ctrl (incl. trackpad pinch) or Alt zooms
  useEffect(() => {
    if (loading) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      if (e.ctrlKey || e.metaKey || e.altKey) {
        zoomAt(e.clientX - rect.left, e.clientY - rect.top, Math.exp(-e.deltaY * 0.0024));
      } else {
        const cam = cameraRef.current;
        cam.x += e.deltaX / cam.scale;
        cam.y += e.deltaY / cam.scale;
        clampCamera();
        requestRender();
      }
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  // --- History / commits ---
  const pushHistory = (snap: TownLayout) => {
    setHistory((h) => [...h.slice(-(HISTORY_LIMIT - 1)), snap]);
    setRedoStack([]);
  };

  const commitLayout = (next: TownLayout, before: TownLayout | null) => {
    layoutRef.current = next;
    setLayout(next);
    setIsDirty(true);
    if (before) pushHistory(before);
  };

  const mutateLayout = (fn: (l: TownLayout) => void, opts: { undoable?: boolean } = {}) => {
    const cur = layoutRef.current;
    if (!cur) return;
    const copy = deepClone(cur);
    fn(copy);
    commitLayout(copy, opts.undoable ? cur : null);
  };

  const handleUndo = () => {
    if (!history.length || !layoutRef.current) return;
    const prev = history[history.length - 1];
    setRedoStack((r) => [...r, layoutRef.current!]);
    setHistory((h) => h.slice(0, -1));
    layoutRef.current = prev;
    setLayout(prev);
    setIsDirty(true);
  };

  const handleRedo = () => {
    if (!redoStack.length || !layoutRef.current) return;
    const next = redoStack[redoStack.length - 1];
    setHistory((h) => [...h, layoutRef.current!]);
    setRedoStack((r) => r.slice(0, -1));
    layoutRef.current = next;
    setLayout(next);
    setIsDirty(true);
  };

  // --- Coordinate helpers ---
  const eventToWorld = (e: { clientX: number; clientY: number }) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const cam = cameraRef.current;
    return {
      wx: cam.x + (e.clientX - rect.left) / cam.scale,
      wy: cam.y + (e.clientY - rect.top) / cam.scale
    };
  };

  const eventToTile = (e: { clientX: number; clientY: number }) => {
    const { wx, wy } = eventToWorld(e);
    const lay = layoutRef.current!;
    const screen = stateRef.current ? isInteriorSceneScreen(stateRef.current) : false;
    const gCols = screen ? 100 : lay.grid.cols;
    const gRows = screen ? 100 : lay.grid.rows;
    return {
      x: clamp(Math.floor(wx), 0, gCols - 1),
      y: clamp(Math.floor(wy), 0, gRows - 1)
    };
  };

  const snappedDelta = (world: { wx: number; wy: number }, start: { wx: number; wy: number }) => {
    const fine = stateRef.current?.fineAdjustment;
    const snap = (v: number) => (fine ? Math.round(v * 2) / 2 : Math.round(v));
    return { dx: snap(world.wx - start.wx), dy: snap(world.wy - start.wy) };
  };

  // --- Tile tools ---
  const stampBrush = (cx: number, cy: number, g: Extract<Gesture, { kind: "paint" }>) => {
    const st = stateRef.current!;
    const lay = layoutRef.current!;
    const size = st.brushSize;
    const half = Math.floor((size - 1) / 2);
    const layer = ensureLayer(lay, st.paintLayer);
    for (let dx = 0; dx < size; dx++) {
      for (let dy = 0; dy < size; dy++) {
        const x = cx - half + dx;
        const y = cy - half + dy;
        if (x < 0 || y < 0 || x >= lay.grid.cols || y >= lay.grid.rows) continue;
        const key = tileKey(x, y);
        if (g.painted.has(key)) continue;
        g.painted.add(key);
        layer.tiles = layer.tiles.filter((t) => !(t.x === x && t.y === y));
        if (!g.erase) layer.tiles.push({ x, y, tile_id: st.selectedTileId });
      }
    }
  };

  const paintLine = (from: { x: number; y: number }, to: { x: number; y: number }, g: Extract<Gesture, { kind: "paint" }>) => {
    let x0 = from.x;
    let y0 = from.y;
    const x1 = to.x;
    const y1 = to.y;
    const dx = Math.abs(x1 - x0);
    const dy = -Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1;
    const sy = y0 < y1 ? 1 : -1;
    let err = dx + dy;
    for (;;) {
      stampBrush(x0, y0, g);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 >= dy) {
        err += dy;
        x0 += sx;
      }
      if (e2 <= dx) {
        err += dx;
        y0 += sy;
      }
    }
  };

  const floodFill = (tile: { x: number; y: number }) => {
    const st = stateRef.current!;
    const before = layoutRef.current!;
    const copy = deepClone(before);
    const layer = ensureLayer(copy, st.paintLayer);
    const map = new Map<string, string>();
    layer.tiles.forEach((t) => map.set(tileKey(t.x, t.y), t.tile_id));
    const target = map.get(tileKey(tile.x, tile.y));
    if (target === st.selectedTileId) return;

    const gCols = copy.grid.cols;
    const gRows = copy.grid.rows;
    const queue = [tile];
    const seen = new Set([tileKey(tile.x, tile.y)]);
    const cells: Array<{ x: number; y: number }> = [];
    while (queue.length) {
      const c = queue.pop()!;
      cells.push(c);
      if (cells.length > FLOOD_FILL_LIMIT) {
        showToast(`Flood fill region exceeds ${FLOOD_FILL_LIMIT} tiles — aborted. Use the rectangle tool for large fills.`, "error");
        return;
      }
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]] as const) {
        const nx = c.x + dx;
        const ny = c.y + dy;
        if (nx < 0 || ny < 0 || nx >= gCols || ny >= gRows) continue;
        const k = tileKey(nx, ny);
        if (seen.has(k) || map.get(k) !== target) continue;
        seen.add(k);
        queue.push({ x: nx, y: ny });
      }
    }
    for (const c of cells) map.set(tileKey(c.x, c.y), st.selectedTileId);
    layer.tiles = Array.from(map.entries()).map(([k, tid]) => {
      const [x, y] = k.split(",").map(Number);
      return { x, y, tile_id: tid };
    });
    commitLayout(copy, before);
    showToast(`Filled ${cells.length} tiles with ${st.selectedTileId.replace("tile_", "")}.`, "success");
  };

  const samplePicker = (tile: { x: number; y: number }) => {
    const st = stateRef.current!;
    const lay = layoutRef.current!;
    for (let i = ALLOWED_LAYERS.length - 1; i >= 0; i--) {
      const layerName = ALLOWED_LAYERS[i];
      if (!st.visibleLayers[layerName]) continue;
      const layer = lay.tile_layers?.[layerName];
      if (!layer) continue;
      const found = layer.tiles.find((t) => t.x === tile.x && t.y === tile.y);
      if (found) {
        setSelectedTileId(found.tile_id);
        setPaintLayer(layerName);
        showToast(`Picked ${found.tile_id.replace("tile_", "")} on layer "${layerName}".`, "info");
        return;
      }
    }
    showToast("No painted tile at that cell.", "info");
  };

  const applyRectGesture = (g: Extract<Gesture, { kind: "rect" }>) => {
    const st = stateRef.current!;
    const next = deepClone(g.before);
    const layer = ensureLayer(next, st.paintLayer);
    const r = normRect(g.start, g.current);
    layer.tiles = layer.tiles.filter(
      (t) => !(t.x >= r.x && t.x < r.x + r.w && t.y >= r.y && t.y < r.y + r.h)
    );
    if (!g.erase) {
      for (let x = r.x; x < r.x + r.w; x++) {
        for (let y = r.y; y < r.y + r.h; y++) {
          layer.tiles.push({ x, y, tile_id: st.selectedTileId });
        }
      }
    }
    commitLayout(next, g.before);
  };

  // --- Props ---
  const findLocationIdAtWorld = (wx: number, wy: number): string | null => {
    const st = stateRef.current;
    const lay = layoutRef.current;
    if (!st || !lay) return null;
    let best: { id: string; area: number } | null = null;
    for (const l of st.activeLocations) {
      const b = resolveLocationView(lay, st.canonicalRecs, st.selectedCaseId, l.location_id, st.mapView).bounds;
      if (boundsContainsPoint(b, wx, wy)) {
        const area = b.w * b.h;
        if (!best || area < best.area) best = { id: l.location_id, area };
      }
    }
    return best ? best.id : null;
  };

  const placeProp = (tile: { x: number; y: number }, world: { wx: number; wy: number }) => {
    const st = stateRef.current!;
    const before = layoutRef.current!;
    const copy = deepClone(before);
    // The save validator only accepts canonical-contract location ids on props
    const hit = findLocationIdAtWorld(tile.x + 0.5, tile.y + 0.5);
    const locId = hit && st.canonicalRecs[hit] ? hit : "loc_village_square";
    const inst: PropInstance = {
      instance_id: `prop_${st.selectedPropId.replace(/^prop_/, "")}_${Date.now().toString().slice(-6)}`,
      asset_id: st.selectedPropId,
      location_id: locId,
      x: tile.x,
      y: tile.y,
      layer: st.propLayer,
      render_policy: "always_visible"
    };
    if (!copy.prop_instances) copy.prop_instances = {};
    if (!copy.prop_instances[st.selectedCaseId]) copy.prop_instances[st.selectedCaseId] = [];
    copy.prop_instances[st.selectedCaseId].push(inst);
    layoutRef.current = copy;
    setSelection({ kind: "prop", id: inst.instance_id });
    gestureRef.current = {
      kind: "moveProp",
      before,
      id: inst.instance_id,
      startW: world,
      orig: { x: inst.x, y: inst.y },
      mutated: true
    };
    requestRender();
  };

  // --- Lights ---
  const placeLight = (world: { wx: number; wy: number }) => {
    const st = stateRef.current!;
    const before = layoutRef.current!;
    const copy = deepClone(before);
    const hit = findLocationIdAtWorld(world.wx, world.wy);
    const locId = hit && st.canonicalRecs[hit] ? hit : "loc_village_square";
    const id = `light_${st.selectedLightAssetId.replace(/^light_/, "")}_${Date.now().toString().slice(-6)}`;
    const light: LightDef = {
      location_id: locId,
      semantic_asset_id: st.selectedLightAssetId,
      x: world.wx,
      y: world.wy,
      width: 2,
      height: 2,
      from: "19:00",
      to: "07:00",
      opacity: 0.65
    };
    if (!copy.lights) copy.lights = {};
    copy.lights[id] = light;
    layoutRef.current = copy;
    setSelection({ kind: "light", id });
    gestureRef.current = {
      kind: "moveLight",
      before,
      id,
      startW: world,
      orig: { x: light.x, y: light.y },
      mutated: true
    };
    requestRender();
  };

  const deleteLight = (id: string) => {
    mutateLayout(
      (l) => {
        if (l.lights) delete l.lights[id];
      },
      { undoable: true }
    );
    setSelection(null);
    showToast("Light deleted.", "success");
  };

  const duplicateLight = (id: string) => {
    const lay = layoutRef.current;
    if (!lay) return;
    const src = findLight(lay, id);
    if (!src) return;
    const copyId = `light_${src.semantic_asset_id.replace(/^light_/, "")}_${Date.now().toString().slice(-6)}`;
    mutateLayout(
      (l) => {
        const s = findLight(l, id);
        if (!s) return;
        if (!l.lights) l.lights = {};
        l.lights[copyId] = { ...deepClone(s), x: s.x + 1, y: s.y + 1 };
      },
      { undoable: true }
    );
    setSelection({ kind: "light", id: copyId });
    showToast("Light duplicated.", "success");
  };

  // --- Ambient sprites ---
  const placeAmbient = (world: { wx: number; wy: number }) => {
    const st = stateRef.current!;
    const before = layoutRef.current!;
    const copy = deepClone(before);
    const asset = AMBIENT_ASSET_SWATCHES[st.selectedAmbientAssetId];
    const id = `ambient_${st.selectedAmbientAssetId}_${Date.now().toString().slice(-6)}`;
    const sprite: AmbientSpriteDef = {
      asset_id: st.selectedAmbientAssetId,
      x: world.wx,
      y: world.wy,
      width: asset?.width || 3,
      height: asset?.height || 3,
      opacity: asset?.opacity ?? 0.6,
      from: "00:00",
      to: "23:59"
    };
    if (!copy.ambient_sprites) copy.ambient_sprites = {};
    copy.ambient_sprites[id] = sprite;
    layoutRef.current = copy;
    setSelection({ kind: "ambient", id });
    gestureRef.current = {
      kind: "moveAmbient",
      before,
      id,
      startW: world,
      orig: { x: sprite.x, y: sprite.y },
      mutated: true
    };
    requestRender();
  };

  const deleteAmbient = (id: string) => {
    mutateLayout(
      (l) => {
        if (l.ambient_sprites) delete l.ambient_sprites[id];
      },
      { undoable: true }
    );
    setSelection(null);
    showToast("Ambient effect deleted.", "success");
  };

  const duplicateAmbient = (id: string) => {
    const lay = layoutRef.current;
    if (!lay) return;
    const src = findAmbient(lay, id);
    if (!src) return;
    const copyId = `ambient_${src.asset_id}_${Date.now().toString().slice(-6)}`;
    mutateLayout(
      (l) => {
        const s = findAmbient(l, id);
        if (!s) return;
        if (!l.ambient_sprites) l.ambient_sprites = {};
        l.ambient_sprites[copyId] = { ...deepClone(s), x: s.x + 1, y: s.y + 1 };
      },
      { undoable: true }
    );
    setSelection({ kind: "ambient", id: copyId });
    showToast("Ambient effect duplicated.", "success");
  };

  // --- Buildings ---
  const findBuilding = (l: TownLayout, id: string): BuildingInstance | undefined =>
    (l.building_instances || []).find((b) => b.instance_id === id);

  /** Strip a building's derived dressing tiles out of the shared layers. */
  const removeDerivedTiles = (l: TownLayout, inst: BuildingInstance) => {
    for (const [layerName, layer] of Object.entries(inst.derived_tiles || {})) {
      const target = l.tile_layers?.[layerName];
      if (!target) continue;
      const occupied = new Set(layer.tiles.map((t) => tileKey(t.x, t.y)));
      target.tiles = target.tiles.filter((t) => !occupied.has(tileKey(t.x, t.y)));
    }
  };

  const mergeDerivedTiles = (l: TownLayout, derived: Record<string, TileLayer>) => {
    for (const [layerName, layer] of Object.entries(derived)) {
      const target = ensureLayer(l, layerName);
      const occupied = new Set(layer.tiles.map((t) => tileKey(t.x, t.y)));
      target.tiles = target.tiles.filter((t) => !occupied.has(tileKey(t.x, t.y)));
      target.tiles.push(...layer.tiles);
    }
  };

  /** Move/rotate a placed building: pull its old dressing out of the shared
   *  layers, re-dress at the new position, and merge back in. */
  const applyBuildingPlacement = (l: TownLayout, id: string, x: number, y: number, rotation: number) => {
    const inst = findBuilding(l, id);
    if (!inst) return;
    removeDerivedTiles(l, inst);
    inst.x = x;
    inst.y = y;
    inst.rotation = rotation;
    const locId = findLocationIdAtWorld(x + 0.5, y + 0.5);
    if (locId) inst.location_id = locId;
    const asset = buildingLibraryRef.current[inst.asset_id] || { footprint: inst.footprint || { w: 1, h: 1 } };
    inst.derived_tiles = dressBuilding(asset, x, y, rotation);
    mergeDerivedTiles(l, inst.derived_tiles);
  };

  const clampBuildingXY = (l: TownLayout, inst: BuildingInstance, x: number, y: number, rotation: number) => {
    const fp = rotatedFootprint(inst.footprint || { w: 1, h: 1 }, rotation);
    return {
      x: clamp(x, 1, l.grid.cols - 1 - fp.w),
      y: clamp(y, 1, l.grid.rows - 1 - fp.h)
    };
  };

  const placeBuilding = (tile: { x: number; y: number }) => {
    const st = stateRef.current!;
    const before = layoutRef.current!;
    const asset = buildingLibrary[st.selectedBuildingId];
    if (!asset) {
      showToast("Choose a building bundle first.", "error");
      return;
    }
    const rotation = st.buildingRotation;
    const placed = rotatedFootprint(asset.footprint, rotation);
    if (tile.x < 1 || tile.y < 1 || tile.x + placed.w > before.grid.cols - 1 || tile.y + placed.h > before.grid.rows - 1) {
      showToast("That building would fall outside the town grid.", "error");
      return;
    }
    const instance: BuildingInstance = {
      instance_id: `building_${st.selectedBuildingId}_${Date.now().toString().slice(-6)}`,
      asset_id: st.selectedBuildingId,
      location_id: findLocationIdAtWorld(tile.x + 0.5, tile.y + 0.5) || "loc_village_square",
      x: tile.x,
      y: tile.y,
      rotation,
      footprint: asset.footprint,
      exterior_asset: asset.exterior_asset,
      interior_asset: asset.interior_asset,
      entrances: asset.entrances,
      derived_tiles: {}
    };
    const copy = deepClone(before);
    copy.building_instances = [...(copy.building_instances || []), instance];
    // The editor mirrors the backend's deterministic dressing contract.
    const derived = dressBuilding(asset, tile.x, tile.y, rotation);
    instance.derived_tiles = derived;
    mergeDerivedTiles(copy, derived);
    // Auto-connect the front-door stub to the nearest existing path network
    // tile (painted roads or another building's stub).
    const connect = connectBuildingToPaths(copy, instance);
    let toastMsg = `${asset.display_name} placed with entrance path and boundary dressing.`;
    if (connect.tiles.length) {
      ensureLayer(copy, "paths").tiles.push(...connect.tiles);
      toastMsg = `${asset.display_name} placed · path connected to the network (+${connect.tiles.length} tiles).`;
    } else if (connect.alreadyConnected) {
      toastMsg = `${asset.display_name} placed · entrance already touches the path network.`;
    } else if (connect.failure === "no_network") {
      toastMsg = `${asset.display_name} placed · nothing to connect to yet — paint a path tile on a road or drop another building, then hit Connect paths.`;
    } else if (connect.failure === "unreachable") {
      toastMsg = `${asset.display_name} placed · path network unreachable from here (blocked by walls/water).`;
    }
    commitLayout(copy, before);
    setSelection({ kind: "building", id: instance.instance_id });
    showToast(toastMsg, "success");
    requestRender();
  };

  const deleteBuilding = (instanceId: string) => {
    mutateLayout(
      (l) => {
        const inst = findBuilding(l, instanceId);
        if (!inst) return;
        removeDerivedTiles(l, inst);
        l.building_instances = (l.building_instances || []).filter((b) => b.instance_id !== instanceId);
      },
      { undoable: true }
    );
    setSelection(null);
    showToast("Building removed with its dressing. Connector paths stay — erase them or re-run Connect paths.", "success");
  };

  const duplicateBuilding = (instanceId: string) => {
    const lay = layoutRef.current;
    const src = lay ? findBuilding(lay, instanceId) : undefined;
    if (!lay || !src) return;
    const copyId = `building_${src.asset_id}_${Date.now().toString().slice(-6)}`;
    const rotation = src.rotation || 0;
    const target = clampBuildingXY(lay, src, src.x + 2, src.y + 2, rotation);
    mutateLayout(
      (l) => {
        const inst: BuildingInstance = { ...deepClone(src), instance_id: copyId, derived_tiles: {} };
        l.building_instances = [...(l.building_instances || []), inst];
        applyBuildingPlacement(l, copyId, target.x, target.y, rotation);
      },
      { undoable: true }
    );
    setSelection({ kind: "building", id: copyId });
    showToast("Building duplicated.", "success");
  };

  const rotateSelectedBuilding = (dir: 1 | -1) => {
    const st = stateRef.current;
    const lay = layoutRef.current;
    if (!st || !lay || st.selection?.kind !== "building") return;
    const sel = st.selection;
    mutateLayout(
      (l) => {
        const inst = findBuilding(l, sel.id);
        if (!inst) return;
        const rotation = ((inst.rotation || 0) + dir * 90 + 360) % 360;
        const target = clampBuildingXY(l, inst, inst.x, inst.y, rotation);
        applyBuildingPlacement(l, sel.id, target.x, target.y, rotation);
      },
      { undoable: true }
    );
  };

  const deleteProp = (instanceId: string) => {
    mutateLayout(
      (l) => {
        for (const scope of Object.keys(l.prop_instances || {})) {
          l.prop_instances[scope] = l.prop_instances[scope].filter((p) => p.instance_id !== instanceId);
        }
      },
      { undoable: true }
    );
    setSelection(null);
    showToast("Prop instance deleted.", "success");
  };

  const duplicateProp = (instanceId: string) => {
    const lay = layoutRef.current;
    if (!lay) return;
    const found = findProp(lay, instanceId);
    if (!found) return;
    const copyId = `prop_${found.prop.asset_id.replace(/^prop_/, "")}_${Date.now().toString().slice(-6)}`;
    mutateLayout(
      (l) => {
        const src = findProp(l, instanceId);
        if (!src) return;
        l.prop_instances[src.scope].push({
          ...deepClone(src.prop),
          instance_id: copyId,
          x: clamp(src.prop.x + 1, 0, l.grid.cols - 1),
          y: clamp(src.prop.y + 1, 0, l.grid.rows - 1)
        });
      },
      { undoable: true }
    );
    setSelection({ kind: "prop", id: copyId });
    showToast("Prop duplicated.", "success");
  };

  // --- Clue hotspots ---
  const updateLocalClue = (caseId: string, clueId: string, updates: Partial<CaseClueRef>) => {
    const applyUpdates = (prev: CaseRef[]) =>
      prev.map((c) =>
        c.case_id === caseId
          ? { ...c, clues: (c.clues || []).map((clue) => (clue.clue_id === clueId ? { ...clue, ...updates } : clue)) }
          : c
      );
    casesRef.current = applyUpdates(casesRef.current);
    if (stateRef.current?.selectedCaseId === caseId) {
      stateRef.current = {
        ...stateRef.current,
        activeClues: (stateRef.current.activeClues || []).map((clue) =>
          clue.clue_id === clueId ? { ...clue, ...updates } : clue
        )
      };
    }
    setCases((prev) => applyUpdates(prev));
  };

  const saveClueLocation = (clue: CaseClueRef, updates: { x: number; y: number; radius?: number }, quiet = false) => {
    if (selectedCaseId === "canonical") return;
    const caseId = selectedCaseId;
    updateLocalClue(caseId, clue.clue_id, {
      x: updates.x,
      y: updates.y,
      radius: updates.radius ?? clue.radius
    });
    api
      .saveDevMapClueLocation({
        case_id: caseId,
        clue_id: clue.clue_id,
        x: updates.x,
        y: updates.y,
        radius: updates.radius ?? clue.radius
      })
      .then((res) => {
        updateLocalClue(caseId, clue.clue_id, { x: res.x, y: res.y, radius: res.radius });
        if (!quiet) showToast("Clue hotspot saved to clues.json.", "success");
      })
      .catch((err: Error) => {
        showToast(`Clue hotspot save failed: ${err.message}`, "error");
      });
  };

  const placeClueAtWorld = (clue: CaseClueRef, wx: number, wy: number, quiet = false) => {
    const lay = layoutRef.current;
    if (!lay || !clue.location_id) return;
    const bounds = resolveLocationView(lay, canonicalRecs, selectedCaseId, clue.location_id, mapView).bounds;
    const pct = worldToCluePercent(bounds, wx, wy);
    saveClueLocation(clue, pct, quiet);
  };

  // --- Select tool hit testing ---
  const selectionHandleWorld = (): { x: number; y: number } | null => {
    const st = stateRef.current;
    const lay = layoutRef.current;
    if (!st || !lay || !st.selection) return null;
    if (st.selection.kind === "location") {
      const b = resolveLocationView(lay, st.canonicalRecs, st.selectedCaseId, st.selection.id, st.mapView).bounds;
      const v = rotateVec(b.w / 2, b.h / 2, b.rotation || 0);
      return { x: b.x + b.w / 2 + v.x, y: b.y + b.h / 2 + v.y };
    }
    if (st.selection.kind === "prop") {
      const found = findProp(lay, st.selection.id);
      if (!found) return null;
      return { x: found.prop.x + (found.prop.w || 1), y: found.prop.y + (found.prop.h || 1) };
    }
    if (st.selection.kind === "light") {
      const found = findLight(lay, st.selection.id);
      if (!found) return null;
      const eff = resolveLightView(found, st.mapView);
      return { x: eff.x + eff.width / 2, y: eff.y + eff.height / 2 };
    }
    if (st.selection.kind === "ambient") {
      const found = findAmbient(lay, st.selection.id);
      if (!found) return null;
      return { x: found.x + found.width, y: found.y + found.height };
    }
    return null;
  };

  /** World position of the rotation handle for the selected location. */
  const rotationHandleWorld = (): { x: number; y: number; bounds: Bounds } | null => {
    const st = stateRef.current;
    const lay = layoutRef.current;
    if (!st || !lay || st.selection?.kind !== "location") return null;
    const b = resolveLocationView(lay, st.canonicalRecs, st.selectedCaseId, st.selection.id, st.mapView).bounds;
    const offWorld = b.h / 2 + ROTATE_HANDLE_OFFSET_PX / cameraRef.current.scale;
    const v = rotateVec(0, -offWorld, b.rotation || 0);
    return { x: b.x + b.w / 2 + v.x, y: b.y + b.h / 2 + v.y, bounds: b };
  };

  const beginSelectGesture = (e: React.PointerEvent, world: { wx: number; wy: number }) => {
    const st = stateRef.current!;
    const lay = layoutRef.current!;
    const cam = cameraRef.current;
    const tolWorld = (HANDLE_PX + 4) / cam.scale;

    // 0. Rotation handle of the selected location
    const rotH = rotationHandleWorld();
    if (rotH && st.selection?.kind === "location" && Math.hypot(world.wx - rotH.x, world.wy - rotH.y) <= tolWorld) {
      const before = lay;
      layoutRef.current = deepClone(lay);
      const b = rotH.bounds;
      const cx = b.x + b.w / 2;
      const cy = b.y + b.h / 2;
      gestureRef.current = {
        kind: "rotateLoc",
        before,
        id: st.selection.id,
        center: { x: cx, y: cy },
        startAngle: Math.atan2(world.wy - cy, world.wx - cx),
        origRot: b.rotation || 0,
        mutated: false
      };
      return;
    }

    // 1. Resize handle of the current selection
    const corner = selectionHandleWorld();
    if (corner && st.selection && Math.hypot(world.wx - corner.x, world.wy - corner.y) <= tolWorld) {
      const before = lay;
      layoutRef.current = deepClone(lay);
      if (st.selection.kind === "location") {
        const orig = resolveLocationView(before, st.canonicalRecs, st.selectedCaseId, st.selection.id, st.mapView).bounds;
        gestureRef.current = { kind: "resizeLoc", before, id: st.selection.id, startW: world, orig: { ...orig }, mutated: false };
      } else if (st.selection.kind === "prop") {
        const found = findProp(before, st.selection.id)!;
        gestureRef.current = {
          kind: "resizeProp",
          before,
          id: st.selection.id,
          startW: world,
          orig: { w: found.prop.w || 1, h: found.prop.h || 1 },
          mutated: false
        };
      } else if (st.selection.kind === "light") {
        const eff = resolveLightView(findLight(before, st.selection.id)!, st.mapView);
        gestureRef.current = {
          kind: "resizeLight",
          before,
          id: st.selection.id,
          startW: world,
          orig: { width: eff.width, height: eff.height },
          mutated: false
        };
      } else if (st.selection.kind === "ambient") {
        const found = findAmbient(before, st.selection.id)!;
        gestureRef.current = {
          kind: "resizeAmbient",
          before,
          id: st.selection.id,
          startW: world,
          orig: { width: found.width, height: found.height },
          mutated: false
        };
      }
      return;
    }

    // 2. Evidence anchors
    if (st.selectedCaseId !== "canonical" && st.showEvidenceAnchors && st.visibleLayers["object_anchors"]) {
      for (const o of st.activeObjects) {
        const eff = resolveAnchor(lay, st.canonicalRecs, st.selectedCaseId, o);
        if (Math.hypot(world.wx - eff.anchor.x, world.wy - eff.anchor.y) <= 12 / cam.scale) {
          setSelection({ kind: "object", id: o.object_id });
          const before = lay;
          layoutRef.current = deepClone(lay);
          gestureRef.current = { kind: "moveAnchor", before, id: o.object_id, startW: world, orig: { ...eff.anchor }, mutated: false };
          return;
        }
      }
    }

    // 2.25 Clue hotspots
    if (st.selectedCaseId !== "canonical" && st.visibleLayers["evidence_markers"]) {
      const interiorScreen = isInteriorSceneScreen(st);
      const selectedLocId = interiorScreen ? selectedArtLocationId(lay, st) : null;
      for (const c of st.activeClues) {
        if (selectedLocId && c.location_id !== selectedLocId) continue;
        const pos = resolveClueWorldPosition(lay, st.canonicalRecs, st.selectedCaseId, c, st.mapView, interiorScreen);
        if (!pos) continue;
        if (Math.hypot(world.wx - pos.x, world.wy - pos.y) <= 12 / cam.scale) {
          setSelection({ kind: "clue", id: c.clue_id });
          const before = lay;
          layoutRef.current = deepClone(lay);
          gestureRef.current = {
            kind: "moveClue",
            before,
            id: c.clue_id,
            startW: world,
            orig: { x: pos.x, y: pos.y },
            bounds: pos.bounds,
            mutated: false
          };
          return;
        }
      }
    }

    // 2.5 Lights (radius hit-test against the glow's own extent)
    if (st.visibleLayers["lights"]) {
      const lightIds = Object.keys(lay.lights || {});
      for (let i = lightIds.length - 1; i >= 0; i--) {
        const id = lightIds[i];
        const eff = resolveLightView(lay.lights[id], st.mapView);
        const r = Math.max(eff.width, eff.height) / 2;
        if (Math.hypot(world.wx - eff.x, world.wy - eff.y) <= r) {
          setSelection({ kind: "light", id });
          const before = lay;
          layoutRef.current = deepClone(lay);
          gestureRef.current = { kind: "moveLight", before, id, startW: world, orig: { x: eff.x, y: eff.y }, mutated: false };
          return;
        }
      }
    }

    // 2.6 Ambient sprites (rect hit-test; topmost wins)
    if (st.visibleLayers["ambient"]) {
      const ambientIds = Object.keys(lay.ambient_sprites || {});
      for (let i = ambientIds.length - 1; i >= 0; i--) {
        const id = ambientIds[i];
        const sprite = lay.ambient_sprites[id];
        if (
          world.wx >= sprite.x &&
          world.wx < sprite.x + sprite.width &&
          world.wy >= sprite.y &&
          world.wy < sprite.y + sprite.height
        ) {
          setSelection({ kind: "ambient", id });
          const before = lay;
          layoutRef.current = deepClone(lay);
          gestureRef.current = {
            kind: "moveAmbient",
            before,
            id,
            startW: world,
            orig: { x: sprite.x, y: sprite.y },
            mutated: false
          };
          return;
        }
      }
    }

    // 3. Props (topmost wins)
    const props = mergedProps(lay, st.selectedCaseId);
    for (let i = props.length - 1; i >= 0; i--) {
      const p = props[i];
      if (!st.visibleLayers[p.layer || "props"]) continue;
      if (world.wx >= p.x && world.wx < p.x + (p.w || 1) && world.wy >= p.y && world.wy < p.y + (p.h || 1)) {
        setSelection({ kind: "prop", id: p.instance_id });
        const before = lay;
        layoutRef.current = deepClone(lay);
        gestureRef.current = { kind: "moveProp", before, id: p.instance_id, startW: world, orig: { x: p.x, y: p.y }, mutated: false };
        return;
      }
    }

    // 3.5 Buildings (after props so small props on a footprint stay clickable)
    if (st.visibleLayers["structures"]) {
      const buildings = lay.building_instances || [];
      for (let i = buildings.length - 1; i >= 0; i--) {
        const b = buildings[i];
        const fp = rotatedFootprint(b.footprint || { w: 1, h: 1 }, b.rotation || 0);
        if (world.wx >= b.x && world.wx < b.x + fp.w && world.wy >= b.y && world.wy < b.y + fp.h) {
          setSelection({ kind: "building", id: b.instance_id });
          const before = lay;
          layoutRef.current = deepClone(lay);
          gestureRef.current = { kind: "moveBuilding", before, id: b.instance_id, startW: world, orig: { x: b.x, y: b.y }, mutated: false };
          return;
        }
      }
    }

    // 4. Locations (smallest area wins so nested rooms stay selectable)
    if (st.visibleLayers["debug_bounds"]) {
      let best: { id: string; bounds: Bounds; area: number } | null = null;
      for (const l of st.activeLocations) {
        const b = resolveLocationView(lay, st.canonicalRecs, st.selectedCaseId, l.location_id, st.mapView).bounds;
        if (boundsContainsPoint(b, world.wx, world.wy)) {
          const area = b.w * b.h;
          if (!best || area < best.area) best = { id: l.location_id, bounds: b, area };
        }
      }
      if (best) {
        setSelection({ kind: "location", id: best.id });
        const before = lay;
        layoutRef.current = deepClone(lay);
        gestureRef.current = {
          kind: "moveLoc",
          before,
          id: best.id,
          startW: world,
          orig: { ...best.bounds },
          mutated: false,
          // Internal-view moves are art alignment only; anchors stay put
          // (they are validated against the external bounds).
          attached:
            st.mapView === "external"
              ? collectAttached(before, st.selectedCaseId, best.id, best.bounds)
              : []
        };
        return;
      }
    }

    // 5. Empty space: clear selection and pan
    setSelection(null);
    gestureRef.current = { kind: "pan", lastX: e.clientX, lastY: e.clientY };
  };

  // --- In-gesture mutators (layoutRef.current is a private clone here) ---
  const setLocBoundsInRef = (locId: string, updates: Partial<Bounds>) => {
    const st = stateRef.current!;
    applyLocationBoundsView(layoutRef.current!, st.canonicalRecs, st.selectedCaseId, locId, updates, st.mapView);
  };

  const setAnchorInRef = (objId: string, updates: Partial<{ x: number; y: number }>) => {
    const st = stateRef.current!;
    const obj = st.activeObjects.find((o) => o.object_id === objId);
    if (!obj) return;
    applyAnchor(layoutRef.current!, st.canonicalRecs, st.selectedCaseId, obj, updates);
  };

  // --- Pointer events ---
  const onCanvasPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const lay = layoutRef.current;
    const st = stateRef.current;
    if (!lay || !st || e.button === 2) return;
    e.preventDefault();
    canvasRef.current?.setPointerCapture(e.pointerId);

    const world = eventToWorld(e);
    const tile = eventToTile(e);

    if (e.button === 1 || spaceRef.current || st.activeTool === "pan") {
      gestureRef.current = { kind: "pan", lastX: e.clientX, lastY: e.clientY };
      setCanvasCursor("grabbing");
      return;
    }

    switch (st.activeTool) {
      case "paint":
      case "erase": {
        if (e.altKey) {
          samplePicker(tile);
          return;
        }
        const before = lay;
        layoutRef.current = deepClone(lay);
        const g: Extract<Gesture, { kind: "paint" }> = {
          kind: "paint",
          before,
          erase: st.activeTool === "erase",
          last: tile,
          painted: new Set()
        };
        gestureRef.current = g;
        stampBrush(tile.x, tile.y, g);
        requestRender();
        break;
      }
      case "rect":
        gestureRef.current = { kind: "rect", before: lay, start: tile, current: tile, erase: e.altKey };
        requestRender();
        break;
      case "fill":
        floodFill(tile);
        break;
      case "picker":
        samplePicker(tile);
        break;
      case "prop":
        placeProp(tile, world);
        break;
      case "building":
        placeBuilding(tile);
        break;
      case "light":
        placeLight(world);
        break;
      case "ambient":
        placeAmbient(world);
        break;
      default:
        beginSelectGesture(e, world);
    }
  };

  const onCanvasPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const lay = layoutRef.current;
    const st = stateRef.current;
    if (!lay || !st) return;
    const world = eventToWorld(e);
    const tile = eventToTile(e);

    if (statusCoordsRef.current) statusCoordsRef.current.textContent = `${tile.x}, ${tile.y}`;
    const hovLoc = findLocationIdAtWorld(world.wx, world.wy);
    hoverLocRef.current = hovLoc;
    if (statusHoverLocRef.current) statusHoverLocRef.current.textContent = hovLoc || "—";

    const g = gestureRef.current;
    if (!g) {
      const prev = hoverRef.current;
      hoverRef.current = tile;
      updateCursor(world);
      if (!prev || prev.x !== tile.x || prev.y !== tile.y) requestRender();
      return;
    }

    const gCols = lay.grid.cols;
    const gRows = lay.grid.rows;

    switch (g.kind) {
      case "pan": {
        const cam = cameraRef.current;
        cam.x -= (e.clientX - g.lastX) / cam.scale;
        cam.y -= (e.clientY - g.lastY) / cam.scale;
        g.lastX = e.clientX;
        g.lastY = e.clientY;
        clampCamera();
        requestRender();
        break;
      }
      case "paint":
        paintLine(g.last, tile, g);
        g.last = tile;
        hoverRef.current = tile;
        requestRender();
        break;
      case "rect":
        g.current = tile;
        requestRender();
        break;
      case "moveLoc": {
        const { dx, dy } = snappedDelta(world, g.startW);
        if (dx !== 0 || dy !== 0) g.mutated = true;
        const nx = clamp(g.orig.x + dx, 0, Math.max(0, gCols - g.orig.w));
        const ny = clamp(g.orig.y + dy, 0, Math.max(0, gRows - g.orig.h));
        setLocBoundsInRef(g.id, { x: nx, y: ny });
        applyAttached(layoutRef.current!, g.attached, nx - g.orig.x, ny - g.orig.y, gCols, gRows);
        requestRender();
        break;
      }
      case "resizeLoc": {
        // Measure the drag along the rect's own (possibly rotated) axes so
        // the corner follows the pointer on rotated bounds.
        const local = rotateVec(world.wx - g.startW.wx, world.wy - g.startW.wy, -(g.orig.rotation || 0));
        const fine = stateRef.current?.fineAdjustment;
        const snap = (v: number) => (fine ? Math.round(v * 2) / 2 : Math.round(v));
        const dx = snap(local.x);
        const dy = snap(local.y);
        if (dx !== 0 || dy !== 0) g.mutated = true;
        setLocBoundsInRef(g.id, {
          w: clamp(g.orig.w + dx, 1, gCols - g.orig.x),
          h: clamp(g.orig.h + dy, 1, gRows - g.orig.y)
        });
        requestRender();
        break;
      }
      case "rotateLoc": {
        const angle = Math.atan2(world.wy - g.center.y, world.wx - g.center.x);
        let deg = g.origRot + ((angle - g.startAngle) * 180) / Math.PI;
        const snap = e.shiftKey ? 15 : 1;
        deg = Math.round(deg / snap) * snap;
        const norm = normalizeRotation(deg);
        if ((norm ?? 0) !== g.origRot) g.mutated = true;
        setLocBoundsInRef(g.id, { rotation: norm });
        requestRender();
        break;
      }
      case "moveAnchor": {
        const { dx, dy } = snappedDelta(world, g.startW);
        if (dx !== 0 || dy !== 0) g.mutated = true;
        setAnchorInRef(g.id, {
          x: clamp(g.orig.x + dx, 0, gCols - 1),
          y: clamp(g.orig.y + dy, 0, gRows - 1)
        });
        requestRender();
        break;
      }
      case "moveClue": {
        const st = stateRef.current!;
        const fine = st.fineAdjustment;
        const snap = (v: number) => (fine ? Math.round(v * 2) / 2 : Math.round(v));
        const dx = snap(world.wx - g.startW.wx);
        const dy = snap(world.wy - g.startW.wy);
        if (dx !== 0 || dy !== 0) g.mutated = true;
        const pct = worldToCluePercent(g.bounds, g.orig.x + dx, g.orig.y + dy);
        updateLocalClue(st.selectedCaseId, g.id, pct);
        requestRender();
        break;
      }
      case "moveProp": {
        const dx = Math.round(world.wx - g.startW.wx);
        const dy = Math.round(world.wy - g.startW.wy);
        if (dx !== 0 || dy !== 0) g.mutated = true;
        applyPropUpdate(layoutRef.current!, g.id, (p) => {
          p.x = clamp(g.orig.x + dx, 0, gCols - 1);
          p.y = clamp(g.orig.y + dy, 0, gRows - 1);
        });
        requestRender();
        break;
      }
      case "resizeProp": {
        const dx = Math.round(world.wx - g.startW.wx);
        const dy = Math.round(world.wy - g.startW.wy);
        if (dx !== 0 || dy !== 0) g.mutated = true;
        applyPropUpdate(layoutRef.current!, g.id, (p) => {
          p.w = Math.max(1, g.orig.w + dx);
          p.h = Math.max(1, g.orig.h + dy);
        });
        requestRender();
        break;
      }
      case "moveBuilding": {
        const dx = Math.round(world.wx - g.startW.wx);
        const dy = Math.round(world.wy - g.startW.wy);
        if (dx !== 0 || dy !== 0) g.mutated = true;
        const l = layoutRef.current!;
        const inst = findBuilding(l, g.id);
        if (inst) {
          const rotation = inst.rotation || 0;
          const target = clampBuildingXY(l, inst, g.orig.x + dx, g.orig.y + dy, rotation);
          applyBuildingPlacement(l, g.id, target.x, target.y, rotation);
        }
        requestRender();
        break;
      }
      case "moveLight": {
        const st = stateRef.current!;
        const fine = st.fineAdjustment;
        const snap = (v: number) => (fine ? Math.round(v * 2) / 2 : Math.round(v));
        const dx = snap(world.wx - g.startW.wx);
        const dy = snap(world.wy - g.startW.wy);
        if (dx !== 0 || dy !== 0) g.mutated = true;
        applyLightUpdate(layoutRef.current!, g.id, (light) => {
          applyLightView(
            light,
            { x: clamp(g.orig.x + dx, 0, gCols), y: clamp(g.orig.y + dy, 0, gRows) },
            st.mapView
          );
        });
        requestRender();
        break;
      }
      case "resizeLight": {
        const st = stateRef.current!;
        const fine = st.fineAdjustment;
        const snap = (v: number) => (fine ? Math.round(v * 2) / 2 : Math.round(v));
        const dx = snap(world.wx - g.startW.wx);
        const dy = snap(world.wy - g.startW.wy);
        if (dx !== 0 || dy !== 0) g.mutated = true;
        applyLightUpdate(layoutRef.current!, g.id, (light) => {
          applyLightView(
            light,
            { width: Math.max(0.5, g.orig.width + 2 * dx), height: Math.max(0.5, g.orig.height + 2 * dy) },
            st.mapView
          );
        });
        requestRender();
        break;
      }
      case "moveAmbient": {
        const st = stateRef.current!;
        const fine = st.fineAdjustment;
        const snap = (v: number) => (fine ? Math.round(v * 2) / 2 : Math.round(v));
        const dx = snap(world.wx - g.startW.wx);
        const dy = snap(world.wy - g.startW.wy);
        if (dx !== 0 || dy !== 0) g.mutated = true;
        applyAmbientUpdate(layoutRef.current!, g.id, (sprite) => {
          sprite.x = clamp(g.orig.x + dx, 0, gCols);
          sprite.y = clamp(g.orig.y + dy, 0, gRows);
        });
        requestRender();
        break;
      }
      case "resizeAmbient": {
        const st = stateRef.current!;
        const fine = st.fineAdjustment;
        const snap = (v: number) => (fine ? Math.round(v * 2) / 2 : Math.round(v));
        const dx = snap(world.wx - g.startW.wx);
        const dy = snap(world.wy - g.startW.wy);
        if (dx !== 0 || dy !== 0) g.mutated = true;
        applyAmbientUpdate(layoutRef.current!, g.id, (sprite) => {
          sprite.width = Math.max(0.5, g.orig.width + dx);
          sprite.height = Math.max(0.5, g.orig.height + dy);
        });
        requestRender();
        break;
      }
    }
  };

  const onCanvasPointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const g = gestureRef.current;
    if (!g) return;
    gestureRef.current = null;
    try {
      canvasRef.current?.releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }

    if (g.kind === "pan") {
      updateCursor(eventToWorld(e));
      return;
    }
    if (g.kind === "rect") {
      applyRectGesture(g);
      requestRender();
      return;
    }
    if (g.kind === "paint") {
      if (g.painted.size > 0) {
        setLayout(layoutRef.current!);
        setIsDirty(true);
        pushHistory(g.before);
      } else {
        layoutRef.current = g.before;
        requestRender();
      }
      return;
    }
    if (g.kind === "moveClue") {
      layoutRef.current = g.before;
      const caseId = stateRef.current?.selectedCaseId || selectedCaseId;
      const clue = casesRef.current.find((c) => c.case_id === caseId)?.clues?.find((c) => c.clue_id === g.id);
      if (g.mutated && clue && clue.x != null && clue.y != null) {
        api
          .saveDevMapClueLocation({
            case_id: caseId,
            clue_id: clue.clue_id,
            x: clue.x,
            y: clue.y,
            radius: clue.radius
          })
          .then((res) => {
            updateLocalClue(caseId, clue.clue_id, { x: res.x, y: res.y, radius: res.radius });
            showToast("Clue hotspot saved to clues.json.", "success");
          })
          .catch((err: Error) => showToast(`Clue hotspot save failed: ${err.message}`, "error"));
      }
      requestRender();
      return;
    }
    // Move / resize gestures
    if (g.mutated) {
      setLayout(layoutRef.current!);
      setIsDirty(true);
      pushHistory(g.before);
    } else {
      layoutRef.current = g.before;
      requestRender();
    }
  };

  const cancelGesture = (): boolean => {
    const g = gestureRef.current;
    if (!g) return false;
    gestureRef.current = null;
    if (g.kind !== "pan") {
      layoutRef.current = g.before;
      requestRender();
    }
    return true;
  };

  const setCanvasCursor = (cursor: string) => {
    if (canvasRef.current) canvasRef.current.style.cursor = cursor;
  };

  const updateCursor = (world: { wx: number; wy: number }) => {
    const st = stateRef.current;
    if (!st) return;
    if (spaceRef.current || st.activeTool === "pan") {
      setCanvasCursor(gestureRef.current?.kind === "pan" ? "grabbing" : "grab");
      return;
    }
    switch (st.activeTool) {
      case "paint":
      case "erase":
      case "rect":
      case "fill":
      case "picker":
        setCanvasCursor("crosshair");
        return;
      case "prop":
      case "ambient":
        setCanvasCursor("copy");
        return;
      default: {
        const cam = cameraRef.current;
        const rotH = rotationHandleWorld();
        if (rotH && Math.hypot(world.wx - rotH.x, world.wy - rotH.y) <= (HANDLE_PX + 4) / cam.scale) {
          setCanvasCursor("grab");
          return;
        }
        const corner = selectionHandleWorld();
        if (corner && Math.hypot(world.wx - corner.x, world.wy - corner.y) <= (HANDLE_PX + 4) / cam.scale) {
          setCanvasCursor("nwse-resize");
          return;
        }
        setCanvasCursor(hoverLocRef.current ? "move" : "default");
      }
    }
  };

  // --- Minimap interaction ---
  const minimapJump = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const mm = minimapRef.current;
    const scene = lastSceneRef.current;
    if (!mm || !scene) return;
    const rect = mm.getBoundingClientRect();
    const p = minimapToWorld(mm, scene, e.clientX - rect.left, e.clientY - rect.top);
    const cam = cameraRef.current;
    const { w, h } = sizeRef.current;
    cam.x = p.x - w / (2 * cam.scale);
    cam.y = p.y - h / (2 * cam.scale);
    clampCamera();
    requestRender();
  };

  // --- Keyboard ---
  const nudgeSelection = (dx: number, dy: number, big: boolean, micro = false) => {
    const st = stateRef.current;
    const lay = layoutRef.current;
    if (!st || !lay || !st.selection) return;
    const step = big ? 5 : micro ? 0.1 : st.fineAdjustment ? 0.5 : 1;
    const mx = dx * step;
    const my = dy * step;
    const gCols = lay.grid.cols;
    const gRows = lay.grid.rows;
    const sel = st.selection;
    if (sel.kind === "location") {
      mutateLayout(
        (l) => {
          const b = resolveLocationView(l, st.canonicalRecs, st.selectedCaseId, sel.id, st.mapView).bounds;
          const nx = clamp(b.x + mx, 0, Math.max(0, gCols - b.w));
          const ny = clamp(b.y + my, 0, Math.max(0, gRows - b.h));
          const attached = st.mapView === "external" ? collectAttached(l, st.selectedCaseId, sel.id, b) : [];
          applyLocationBoundsView(l, st.canonicalRecs, st.selectedCaseId, sel.id, { x: nx, y: ny }, st.mapView);
          applyAttached(l, attached, nx - b.x, ny - b.y, gCols, gRows);
        },
        { undoable: true }
      );
    } else if (sel.kind === "object") {
      const obj = st.activeObjects.find((o) => o.object_id === sel.id);
      if (!obj) return;
      const a = resolveAnchor(lay, st.canonicalRecs, st.selectedCaseId, obj).anchor;
      mutateLayout(
        (l) =>
          applyAnchor(l, st.canonicalRecs, st.selectedCaseId, obj, {
            x: clamp(a.x + mx, 0, gCols - 1),
            y: clamp(a.y + my, 0, gRows - 1)
          }),
        { undoable: true }
      );
    } else if (sel.kind === "clue") {
      const clue = st.activeClues.find((c) => c.clue_id === sel.id);
      const pos = clue ? resolveClueWorldPosition(lay, st.canonicalRecs, st.selectedCaseId, clue, st.mapView, isInteriorSceneScreen(st)) : null;
      if (!clue || !pos) return;
      const pct = worldToCluePercent(pos.bounds, pos.x + mx, pos.y + my);
      saveClueLocation(clue, pct, true);
    } else if (sel.kind === "prop") {
      mutateLayout(
        (l) => {
          applyPropUpdate(l, sel.id, (p) => {
            p.x = clamp(p.x + Math.round(mx), 0, gCols - 1);
            p.y = clamp(p.y + Math.round(my), 0, gRows - 1);
          });
        },
        { undoable: true }
      );
    } else if (sel.kind === "building") {
      mutateLayout(
        (l) => {
          const inst = findBuilding(l, sel.id);
          if (!inst) return;
          const rotation = inst.rotation || 0;
          const target = clampBuildingXY(l, inst, inst.x + Math.round(mx), inst.y + Math.round(my), rotation);
          applyBuildingPlacement(l, sel.id, target.x, target.y, rotation);
        },
        { undoable: true }
      );
    } else if (sel.kind === "light") {
      mutateLayout(
        (l) => {
          const light = findLight(l, sel.id);
          if (!light) return;
          const eff = resolveLightView(light, st.mapView);
          applyLightView(
            light,
            { x: clamp(eff.x + mx, 0, gCols), y: clamp(eff.y + my, 0, gRows) },
            st.mapView
          );
        },
        { undoable: true }
      );
    } else if (sel.kind === "ambient") {
      mutateLayout(
        (l) => {
          applyAmbientUpdate(l, sel.id, (sprite) => {
            sprite.x = clamp(sprite.x + mx, 0, gCols);
            sprite.y = clamp(sprite.y + my, 0, gRows);
          });
        },
        { undoable: true }
      );
    }
  };

  /** The active underlay art as placed world-rect images (cells resolved per view + overrides). */
  const currentUnderlayTiles = (): SnapUnderlayTile[] => {
    const st = stateRef.current;
    if (!st || st.underlaySource === "none") return [];
    if (layoutRef.current && st.underlaySource === "selected_location_art") {
      return selectedArtUnderlays(layoutRef.current, st);
    }
    const def = UNDERLAY_SOURCES.find((u) => u.id === st.underlaySource);
    return (def?.tiles || [])
      .map((t) => {
        const url = t.cell
          ? resolveHdTileUrl(t.cell, st.mapView, layoutRef.current?.underlay_tile_overrides)
          : t.url;
        return { img: underlayImgs.current[url], x: t.x, y: t.y, w: t.w, h: t.h };
      })
      .filter((t) => !!t.img);
  };

  /** Swap a mosaic cell's artwork. Only B2 has paired per-view art, so other
   * cells apply to both views; an empty url restores the default artwork. */
  const setTileArtOverride = (cell: string, url: string) => {
    const st = stateRef.current;
    if (!st) return;
    const views: MapView[] = cell === "B2" ? [st.mapView] : ["external", "internal"];
    mutateLayout(
      (l) => {
        const overrides = l.underlay_tile_overrides || (l.underlay_tile_overrides = {});
        for (const view of views) {
          const cells = overrides[view] || (overrides[view] = {});
          if (url && url !== hdDefaultTileUrl(cell, view)) cells[cell] = url;
          else delete cells[cell];
          if (!Object.keys(cells).length) delete overrides[view];
        }
        if (!Object.keys(overrides).length) delete l.underlay_tile_overrides;
      },
      { undoable: true }
    );
  };

  /** Refine the selected location's rough box to hug the structure in the art. */
  const snapSelectionToStructure = () => {
    const st = stateRef.current;
    const lay = layoutRef.current;
    if (!st || !lay || st.selection?.kind !== "location") return;
    const tiles = currentUnderlayTiles();
    if (!tiles.length) {
      showToast("No underlay art to snap to — pick an underlay source first.", "error");
      return;
    }
    const sel = st.selection;
    const rough = resolveLocationView(lay, st.canonicalRecs, st.selectedCaseId, sel.id, st.mapView).bounds;
    const result = snapBoundsToStructure(rough, tiles, lay.grid.cols, lay.grid.rows);
    if (!result) {
      showToast("Snap failed: art not loaded for that area yet.", "error");
      return;
    }
    mutateLayout(
      (l) =>
        applyLocationBoundsView(
          l,
          st.canonicalRecs,
          st.selectedCaseId,
          sel.id,
          { ...result.bounds, rotation: result.bounds.rotation },
          st.mapView
        ),
      { undoable: true }
    );
    const b = result.bounds;
    showToast(
      `Snapped to structure: (${b.x},${b.y}) ${b.w}×${b.h}${b.rotation ? ` ∠${b.rotation}°` : ""} · edge fit ×${result.gain.toFixed(2)} — undo with ⌘Z if it grabbed the wrong outline.`,
      "success"
    );
  };

  const rotateSelection = (delta: number) => {
    const st = stateRef.current;
    const lay = layoutRef.current;
    if (!st || !lay || st.selection?.kind !== "location") return;
    const sel = st.selection;
    mutateLayout(
      (l) => {
        const b = resolveLocationView(l, st.canonicalRecs, st.selectedCaseId, sel.id, st.mapView).bounds;
        applyLocationBoundsView(
          l,
          st.canonicalRecs,
          st.selectedCaseId,
          sel.id,
          { rotation: normalizeRotation((b.rotation || 0) + delta) },
          st.mapView
        );
      },
      { undoable: true }
    );
  };

  keyDownRef.current = (e: KeyboardEvent) => {
    const tag = (document.activeElement?.tagName || "").toUpperCase();
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (showExportModal || showImportModal || showShortcuts) {
      if (e.key === "Escape") {
        setShowExportModal(false);
        setShowImportModal(false);
        setShowShortcuts(false);
      }
      return;
    }
    const meta = e.ctrlKey || e.metaKey;
    const key = e.key.toLowerCase();

    if (meta && key === "z") {
      e.preventDefault();
      if (e.shiftKey) handleRedo();
      else handleUndo();
      return;
    }
    if (meta && key === "y") {
      e.preventDefault();
      handleRedo();
      return;
    }
    if (meta && key === "s") {
      e.preventDefault();
      handleSave();
      return;
    }
    if (meta && key === "d") {
      if (selection?.kind === "prop") {
        e.preventDefault();
        duplicateProp(selection.id);
      } else if (selection?.kind === "building") {
        e.preventDefault();
        duplicateBuilding(selection.id);
      } else if (selection?.kind === "light") {
        e.preventDefault();
        duplicateLight(selection.id);
      } else if (selection?.kind === "ambient") {
        e.preventDefault();
        duplicateAmbient(selection.id);
      }
      return;
    }
    if (meta) return;

    switch (e.key) {
      case " ":
        if (!spaceRef.current) {
          spaceRef.current = true;
          setCanvasCursor("grab");
        }
        e.preventDefault();
        return;
      case "Escape":
        if (!cancelGesture()) setSelection(null);
        return;
      case "Delete":
      case "Backspace":
        if (selection?.kind === "prop") deleteProp(selection.id);
        else if (selection?.kind === "building") deleteBuilding(selection.id);
        else if (selection?.kind === "light") deleteLight(selection.id);
        else if (selection?.kind === "ambient") deleteAmbient(selection.id);
        return;
      case "[":
        setBrushSize((s) => Math.max(1, s - 1));
        return;
      case "]":
        setBrushSize((s) => Math.min(8, s + 1));
        return;
      case "+":
      case "=":
        zoomCentered(1.25);
        return;
      case "-":
        zoomCentered(0.8);
        return;
      case "0":
        fitView();
        return;
      case "?":
        setShowShortcuts(true);
        return;
      case "ArrowLeft":
        e.preventDefault();
        nudgeSelection(-1, 0, e.shiftKey, e.altKey);
        return;
      case "ArrowRight":
        e.preventDefault();
        nudgeSelection(1, 0, e.shiftKey, e.altKey);
        return;
      case "ArrowUp":
        e.preventDefault();
        nudgeSelection(0, -1, e.shiftKey, e.altKey);
        return;
      case "ArrowDown":
        e.preventDefault();
        nudgeSelection(0, 1, e.shiftKey, e.altKey);
        return;
      case ",":
        if (activeTool === "building") setBuildingRotation((r) => (r + 270) % 360);
        else if (selection?.kind === "building") rotateSelectedBuilding(-1);
        else rotateSelection(-1);
        return;
      case "<":
        rotateSelection(-15);
        return;
      case ".":
        if (activeTool === "building") setBuildingRotation((r) => (r + 90) % 360);
        else if (selection?.kind === "building") rotateSelectedBuilding(1);
        else rotateSelection(1);
        return;
      case ">":
        rotateSelection(15);
        return;
    }

    // R rotates the building ghost (placement) or the selected placed
    // building instead of switching to the rect tool.
    if (key === "r" && activeTool === "building") {
      setBuildingRotation((r) => (r + 90) % 360);
      return;
    }
    if (key === "r" && selection?.kind === "building") {
      rotateSelectedBuilding(1);
      return;
    }

    const tool = TOOL_DEFS.find((t) => t.key.toLowerCase() === key);
    if (tool) {
      setActiveTool(tool.id);
      return;
    }
    if (key === "m") setShowMinimap((v) => !v);
    if (key === "t") setMapView((v) => (v === "external" ? "internal" : "external"));
    if (key === "s") snapSelectionToStructure();
  };

  keyUpRef.current = (e: KeyboardEvent) => {
    if (e.key === " ") {
      spaceRef.current = false;
      setCanvasCursor("default");
    }
  };

  useEffect(() => {
    const down = (e: KeyboardEvent) => keyDownRef.current(e);
    const up = (e: KeyboardEvent) => keyUpRef.current(e);
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, []);

  // --- Panel operations ---
  const toggleLocationVisibility = (locId: string) => {
    if (selectedCaseId === "canonical") return;
    mutateLayout(
      (l) => {
        if (!l.case_overrides[selectedCaseId]) l.case_overrides[selectedCaseId] = emptyOverride();
        const list = l.case_overrides[selectedCaseId].visible_locations;
        l.case_overrides[selectedCaseId].visible_locations = list.includes(locId)
          ? list.filter((id) => id !== locId)
          : [...list, locId];
      },
      { undoable: true }
    );
  };

  const promoteToCanonical = () => {
    if (!layout || selectedCaseId === "canonical" || selection?.kind !== "location") return;
    const locId = selection.id;
    const eff = resolveLocation(layout, canonicalRecs, selectedCaseId, locId);
    mutateLayout(
      (l) => {
        if (!l.canonical_locations[locId]) {
          l.canonical_locations[locId] = { bounds: { ...eff.bounds }, mode: eff.mode };
        } else {
          l.canonical_locations[locId].bounds = { ...eff.bounds };
        }
        if (l.case_overrides[selectedCaseId]?.location_bounds[locId]) {
          delete l.case_overrides[selectedCaseId].location_bounds[locId];
        }
      },
      { undoable: true }
    );
    showToast(`Promoted bounds of '${locId}' to canonical town template.`, "success");
  };

  const resetToCanonicalRec = () => {
    if (selection?.kind !== "location") return;
    const rec = canonicalRecs[selection.id];
    if (!rec) return;
    const locId = selection.id;
    mutateLayout((l) => applyLocationBounds(l, canonicalRecs, selectedCaseId, locId, rec.bounds), { undoable: true });
    showToast("Reset to recommended layout bounds.", "info");
  };

  const resetToLegacyFallback = () => {
    if (selection?.kind !== "location") return;
    const loc = activeLocations.find((l) => l.location_id === selection.id);
    if (!loc?.legacy_bounds) return;
    const locId = selection.id;
    const lb = loc.legacy_bounds;
    mutateLayout(
      (l) =>
        applyLocationBounds(l, canonicalRecs, selectedCaseId, locId, {
          x: lb.x / 32,
          y: lb.y / 32,
          w: lb.width / 32,
          h: lb.height / 32
        }),
      { undoable: true }
    );
    showToast("Reset to legacy contract bounds.", "info");
  };

  const handleSave = () => {
    const lay = layoutRef.current;
    if (!lay) return;
    if (validationWarnings.length > 0) {
      showToast(`Cannot save: ${validationWarnings.length} validation warning(s) — see the Validations panel.`, "error");
      return;
    }
    api
      .saveDevMapLayout(lay, layoutVersion ?? undefined)
      .then((res) => {
        setIsDirty(false);
        setServerErrors([]);
        setLayoutVersion(res.layout_version ?? null);
        showToast("Layout saved atomically with backup created.", "success");
      })
      .catch((err: Error) => {
        if ((err as any).conflict) {
          // Another tab/session saved since this one loaded — refuse to save
          // over it rather than silently discarding those changes. There's
          // no merge here; the safest recovery is to reload and redo any
          // edits made in this tab against the newer version.
          showToast(
            "Not saved: someone else saved this layout more recently (another tab/session). " +
              "Reload the editor to see their changes before re-applying yours, or you'll overwrite them.",
            "error"
          );
          return;
        }
        const msgs = String(err.message || "").split("\n").filter(Boolean);
        setServerErrors(msgs);
        showToast(
          msgs.length > 1
            ? `Save rejected: ${msgs.length} server validation errors — see the Validations panel.`
            : `Save failed: ${msgs[0] || "unknown error"}`,
          "error"
        );
      });
  };

  const handleImportTextSubmit = () => {
    try {
      const parsed = JSON.parse(importText) as TownLayout;
      if (parsed.version !== "town_layout_editor_v2") {
        showToast("Import failed: version must be town_layout_editor_v2.", "error");
        return;
      }
      if (!parsed.grid || parsed.grid.cols !== cols || parsed.grid.rows !== rows) {
        showToast(`Import failed: grid size must be ${cols}×${rows}.`, "error");
        return;
      }
      mutateLayout(
        (l) => {
          Object.assign(l, {
            ...parsed,
            tile_layers: parsed.tile_layers || {},
            prop_instances: parsed.prop_instances || {},
            lights: parsed.lights || {},
            ambient_sprites: parsed.ambient_sprites || {}
          });
        },
        { undoable: true }
      );
      setShowImportModal(false);
      showToast("JSON layout imported. Review changes and click Save.", "success");
    } catch (err: any) {
      showToast(`JSON syntax error: ${err.message}`, "error");
    }
  };

  const handleDownload = () => {
    const blob = new Blob([JSON.stringify(layout, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "town_layout.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExit = () => {
    if (isDirty && !window.confirm("You have unsaved layout modifications. Exit anyway?")) return;
    window.location.hash = "#/";
  };

  const selectLocationFromList = (locId: string) => {
    setSelection({ kind: "location", id: locId });
    if (underlaySource === "selected_location_art") setInteriorSceneLocationId(locId);
    if (activeTool !== "select") setActiveTool("select");
  };

  const zoomToLocation = (locId: string) => {
    if (!layout) return;
    zoomToBounds(resolveLocationView(layout, canonicalRecs, selectedCaseId, locId, mapView).bounds);
  };

  const paintedTileCount = useMemo(() => {
    if (!layout?.tile_layers) return 0;
    return Object.values(layout.tile_layers).reduce((acc, l) => acc + (l.tiles?.length || 0), 0);
  }, [layout]);

  const filteredLocations = useMemo(() => {
    const q = locationSearch.trim().toLowerCase();
    const sorted = [...activeLocations].sort((a, b) => a.name.localeCompare(b.name));
    if (!q) return sorted;
    return sorted.filter(
      (l) => l.name.toLowerCase().includes(q) || l.location_id.toLowerCase().includes(q)
    );
  }, [activeLocations, locationSearch]);

  const filteredClues = useMemo(() => {
    const q = clueSearch.trim().toLowerCase();
    const sorted = [...activeClues].sort((a, b) => a.title.localeCompare(b.title));
    if (!q) return sorted;
    return sorted.filter(
      (c) =>
        c.title.toLowerCase().includes(q) ||
        c.clue_id.toLowerCase().includes(q) ||
        (c.location_id || "").toLowerCase().includes(q)
    );
  }, [activeClues, clueSearch]);

  const activeToolDef = TOOL_DEFS.find((t) => t.id === activeTool)!;

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="dev-map-loading">
        <style>{BASE_SCREEN_CSS}</style>
        <div className="spinner" />
        Loading Map Studio…
      </div>
    );
  }

  if (error || !layout) {
    return (
      <div className="dev-map-error">
        <style>{BASE_SCREEN_CSS}</style>
        <h3>Developer Environment Error</h3>
        <p>{error || "Layout configuration not parsed."}</p>
        <button className="retry-btn" onClick={() => window.location.reload()}>
          Retry Connection
        </button>
      </div>
    );
  }

  const selectedLocation =
    selection?.kind === "location" ? activeLocations.find((l) => l.location_id === selection.id) : null;
  const selectedLocationEff = selectedLocation
    ? resolveLocationView(layout, canonicalRecs, selectedCaseId, selectedLocation.location_id, mapView)
    : null;
  const selectedObject =
    selection?.kind === "object" ? activeObjects.find((o) => o.object_id === selection.id) : null;
  const selectedObjectEff = selectedObject
    ? resolveAnchor(layout, canonicalRecs, selectedCaseId, selectedObject)
    : null;
  const selectedClue =
    selection?.kind === "clue" ? activeClues.find((c) => c.clue_id === selection.id) : null;
  const selectedCluePos = selectedClue
    ? resolveClueWorldPosition(layout, canonicalRecs, selectedCaseId, selectedClue, mapView, underlaySource === "selected_location_art")
    : null;
  const selectedProp =
    selection?.kind === "prop" ? activeProps.find((p) => p.instance_id === selection.id) : null;
  const selectedBuilding =
    selection?.kind === "building" ? (layout.building_instances || []).find((b) => b.instance_id === selection.id) : null;
  const selectedLight = selection?.kind === "light" ? (layout.lights || {})[selection.id] : null;
  const selectedLightEff = selectedLight ? resolveLightView(selectedLight, mapView) : null;
  const selectedAmbient = selection?.kind === "ambient" ? (layout.ambient_sprites || {})[selection.id] : null;

  return (
    <div className="dev-map-root">
      <style>{EDITOR_CSS}</style>

      {/* ---------------- Header ---------------- */}
      <header className="dev-map-header">
        <div className="header-title-section">
          <h2>🗺 Map Studio</h2>
          <span className="grid-chip">
            {cols}×{rows} · {layout.grid.tile_size}px tiles
          </span>
          {isDirty && <span className="dirty-badge">● Unsaved changes</span>}
        </div>
        <div className="actions-group">
          <button
            className="mse-btn mse-btn-secondary"
            onClick={handleUndo}
            disabled={history.length === 0}
            title="Undo (⌘Z)"
          >
            ↩ Undo{history.length > 0 ? ` (${history.length})` : ""}
          </button>
          <button
            className="mse-btn mse-btn-secondary"
            onClick={handleRedo}
            disabled={redoStack.length === 0}
            title="Redo (⇧⌘Z)"
          >
            ↪ Redo
          </button>
          <div className="header-divider" />
          <button className="mse-btn mse-btn-secondary" onClick={() => setShowShortcuts(true)} title="Keyboard shortcuts (?)">
            ⌨
          </button>
          <button className="mse-btn mse-btn-secondary" onClick={() => setShowImportModal(true)}>
            📥 Import
          </button>
          <button className="mse-btn mse-btn-secondary" onClick={() => setShowExportModal(true)}>
            📤 Export
          </button>
          <button
            className={`mse-btn mse-btn-primary ${validationWarnings.length ? "mse-btn-warn" : ""}`}
            onClick={handleSave}
            title="Save (⌘S)"
          >
            {validationWarnings.length ? `⚠ Fix ${validationWarnings.length} to save` : "💾 Save Layout"}
          </button>
          <button className="mse-btn mse-btn-danger" onClick={handleExit}>
            Exit
          </button>
        </div>
      </header>

      <div className="main-editor-layout">
        {/* ---------------- Left sidebar ---------------- */}
        <aside className="left-sidebar">
          <div className="control-group">
            <label className="section-title">Target Scope</label>
            <select
              value={selectedCaseId}
              onChange={(e) => {
                setSelectedCaseId(e.target.value);
                setSelection(null);
                setInteriorSceneLocationId(null);
              }}
            >
              <option value="canonical">Canonical Town Template</option>
              {cases.map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {c.case_id.toUpperCase()} — {c.title}
                </option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <label className="section-title">Map View (T)</label>
            <div className="view-toggle">
              <button
                className={`view-toggle-btn ${mapView === "external" ? "active" : ""}`}
                onClick={() => setMapView("external")}
                title="Roofed overview art — the bounds the game uses when zoomed out"
              >
                🏠 External
              </button>
              <button
                className={`view-toggle-btn internal ${mapView === "internal" ? "active" : ""}`}
                onClick={() => setMapView("internal")}
                title="Roofless close-up art — the bounds the game swaps to past the zoom threshold"
              >
                🪑 Internal
              </button>
            </div>
            {mapView === "internal" && (
              <div className="view-note">
                Editing internal-view bounds (canonical level, shared by all cases). Locations without
                their own internal bounds inherit the external ones.
              </div>
            )}
          </div>

          <div className="control-group">
            <label className="section-title">Tools</label>
            <div className="tool-grid">
              {TOOL_DEFS.map((t) => (
                <button
                  key={t.id}
                  className={`mse-tool-btn ${activeTool === t.id ? "active" : ""}`}
                  onClick={() => setActiveTool(t.id)}
                  title={`${t.label} (${t.key})`}
                >
                  <span className="tool-icon">{t.icon}</span>
                  <span className="tool-name">{t.label.split(" ")[0]}</span>
                  <span className="tool-key">{t.key}</span>
                </button>
              ))}
            </div>
          </div>

          {(activeTool === "paint" || activeTool === "erase" || activeTool === "rect" || activeTool === "fill" || activeTool === "picker") && (
            <div className="control-group">
              <label className="section-title">Tile Brush</label>
              <div className="inline-row">
                <label className="mini-label">Layer</label>
                <select value={paintLayer} onChange={(e) => setPaintLayer(e.target.value)}>
                  {ALLOWED_LAYERS.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              {(activeTool === "paint" || activeTool === "erase") && (
                <div className="inline-row">
                  <label className="mini-label">Size {brushSize}×{brushSize}</label>
                  <input
                    type="range"
                    min={1}
                    max={8}
                    step={1}
                    value={brushSize}
                    onChange={(e) => setBrushSize(parseInt(e.target.value, 10))}
                  />
                </div>
              )}
              {activeTool !== "erase" && (
                <div className="palette-grid">
                  {ALLOWED_TILES.map((tId) => (
                    <div
                      key={tId}
                      className={`palette-item ${selectedTileId === tId ? "active" : ""}`}
                      style={{ backgroundColor: TILE_COLORS[tId] || "#ccc" }}
                      onClick={() => setSelectedTileId(tId)}
                      title={tId}
                    >
                      <span className="palette-item-text">{tId.replace("tile_", "")}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTool === "prop" && (
            <div className="control-group">
              <label className="section-title">Prop Palette</label>
              <div className="inline-row">
                <label className="mini-label">Layer</label>
                <select value={propLayer} onChange={(e) => setPropLayer(e.target.value)}>
                  {ALLOWED_LAYERS.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              <div className="palette-grid">
                {ALLOWED_PROPS.map((pId) => (
                  <div
                    key={pId}
                    className={`palette-item prop ${selectedPropId === pId ? "active" : ""}`}
                    onClick={() => setSelectedPropId(pId)}
                    title={pId}
                  >
                    <span className="palette-emoji">{PROP_EMOJIS[pId] || "📦"}</span>
                    <span className="palette-item-text">{pId.replace("prop_", "")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTool === "light" && (
            <div className="control-group">
              <label className="section-title">Light Palette</label>
              <div className="view-note">
                {mapView === "internal"
                  ? "Placing sets the internal-view position/asset — the interior art is a different painted asset than the exterior one."
                  : "Placing sets the external (day/roofed) position/asset."}
              </div>
              <div className="palette-grid">
                {ALLOWED_LIGHT_ASSETS.map((aId) => (
                  <div
                    key={aId}
                    className={`palette-item prop ${selectedLightAssetId === aId ? "active" : ""}`}
                    onClick={() => setSelectedLightAssetId(aId)}
                    title={aId}
                  >
                    <span
                      className="palette-emoji"
                      style={{
                        display: "inline-block",
                        width: "1.1em",
                        height: "1.1em",
                        borderRadius: "50%",
                        background: LIGHT_ASSET_SWATCHES[aId]?.color || "#ffe9a8"
                      }}
                    />
                    <span className="palette-item-text">{LIGHT_ASSET_SWATCHES[aId]?.label || aId.replace("light_", "")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTool === "ambient" && (
            <div className="control-group">
              <label className="section-title">Ambient Palette</label>
              <div className="view-note">
                Place water shimmer, smoke, mist, birds and motes against the current map art; saved effects can be reused by the replay/runtime.
              </div>
              <div className="palette-grid">
                {ALLOWED_AMBIENT_ASSETS.map((aId) => (
                  <div
                    key={aId}
                    className={`palette-item prop ${selectedAmbientAssetId === aId ? "active" : ""}`}
                    onClick={() => setSelectedAmbientAssetId(aId)}
                    title={aId}
                  >
                    <span
                      className="palette-emoji"
                      style={{
                        display: "inline-block",
                        width: "1.1em",
                        height: "1.1em",
                        borderRadius: "50%",
                        background: AMBIENT_ASSET_SWATCHES[aId]?.color || "#bae6fd"
                      }}
                    />
                    <span className="palette-item-text">{AMBIENT_ASSET_SWATCHES[aId]?.label || aId.replace(/_/g, " ")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTool === "building" && (
            <div className="control-group">
              <label className="section-title">Building Library</label>
              <div className="view-note">Each bundle includes exterior and interior art references, rooms, an entrance, and automatic surrounding tiles.</div>
              <div className="palette-grid buildings">
                {Object.entries(buildingLibrary).map(([id, building]) => (
                  <div
                    key={id}
                    className={`palette-item prop ${selectedBuildingId === id ? "active" : ""}`}
                    onClick={() => setSelectedBuildingId(id)}
                    title={`${building.display_name} · ${building.footprint.w}×${building.footprint.h}`}
                  >
                    {building.exterior_asset ? (
                      <img className="palette-thumb" src={building.exterior_asset} alt={building.display_name} loading="lazy" />
                    ) : (
                      <span className="palette-emoji">🏠</span>
                    )}
                    <span className="palette-item-text">{building.display_name}</span>
                  </div>
                ))}
              </div>
              <div className="inline-row">
                <label className="mini-label">Rotation (R)</label>
                <div className="mse-rot-group">
                  {[0, 90, 180, 270].map((deg) => (
                    <button
                      key={deg}
                      className={`mse-rot-btn ${buildingRotation === deg ? "active" : ""}`}
                      title={`Door faces ${buildingFrontEdge(deg)}`}
                      onClick={() => setBuildingRotation(deg)}
                    >
                      {deg}°
                    </button>
                  ))}
                </div>
              </div>
              <div className="view-note">Door faces {buildingFrontEdge(buildingRotation)} · the entrance path and dressing rotate with it.</div>
              <button
                className="mse-btn mse-btn-secondary"
                title="Carve shortest paths from every building's entrance to the nearest path network tile"
                onClick={() => {
                  let summary: ReturnType<typeof connectAllBuildings> | null = null;
                  mutateLayout(
                    (l) => {
                      summary = connectAllBuildings(l);
                    },
                    { undoable: true }
                  );
                  if (!summary) return;
                  const s: ReturnType<typeof connectAllBuildings> = summary;
                  if (!s.connected && !s.alreadyConnected && !s.failed.length) {
                    showToast("No buildings placed yet.", "error");
                  } else if (s.failed.length) {
                    showToast(
                      `Connected ${s.connected}, already linked ${s.alreadyConnected}, unreachable ${s.failed.length} — paint a path tile near the stranded buildings.`,
                      "error"
                    );
                  } else {
                    showToast(`Paths connected · ${s.connected} routed (+${s.added.length} tiles), ${s.alreadyConnected} already linked.`, "success");
                  }
                }}
              >
                🔗 Connect paths
              </button>
            </div>
          )}

          <details open className="sidebar-section">
            <summary className="section-title">View</summary>
            <div className="control-group">
              <div className="inline-row">
                <label className="mini-label">Underlay</label>
                <select
                  value={underlaySource}
                  onChange={(e) => {
                    const next = e.target.value as UnderlaySourceId;
                    setUnderlaySource(next);
                    if (next === "selected_location_art") {
                      if (selection?.kind === "clue") {
                        setInteriorSceneLocationId(activeClues.find((c) => c.clue_id === selection.id)?.location_id || null);
                      } else if (selection?.kind === "location") {
                        setInteriorSceneLocationId(selection.id);
                      }
                    }
                  }}
                >
                  <option value="selected_location_art">Selected clue/location HD art</option>
                  {UNDERLAY_SOURCES.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.label}
                    </option>
                  ))}
                  <option value="none">None (blank grid)</option>
                </select>
              </div>
              {underlaySource !== "none" && (
                <div className="inline-row">
                  <label className="mini-label">Opacity {Math.round(underlayOpacity * 100)}%</label>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={underlayOpacity}
                    onChange={(e) => setUnderlayOpacity(parseFloat(e.target.value))}
                  />
                </div>
              )}
              {underlaySource === "selected_location_art" && (
                <div className="view-note">
                  Interior scene screen: replaces the town map with the player search image and shows only inspect clues for this location.
                </div>
              )}
              {underlaySource === "town_tiles_hd" && (
                <details className="sidebar-section">
                  <summary className="section-title">Tile artwork (3×3)</summary>
                  <div className="view-note">
                    Swap a mosaic cell's art — e.g. a blank tile to build your own
                    buildings on. Saved with the layout and used by the game map.
                    B2 applies to the current view ({mapView}); other cells apply
                    to both views. Drop new PNGs in
                    art/town/tiles_3x3_hd/ as town_overworld_&lt;cell&gt;_&lt;name&gt;_hd.png.
                  </div>
                  {HD_TILE_CELLS.map((cell) => {
                    const view = cell === "B2" ? mapView : "external";
                    const current =
                      layout?.underlay_tile_overrides?.[view]?.[cell] || "";
                    const options = tileArtVariants[cell] || [];
                    return (
                      <div className="inline-row" key={cell}>
                        <label className="mini-label">
                          {cell}
                          {cell === "B2" ? ` · ${mapView}` : ""}
                          {current ? " ●" : ""}
                        </label>
                        <select
                          value={current}
                          onChange={(e) => setTileArtOverride(cell, e.target.value)}
                        >
                          <option value="">Default</option>
                          {options
                            .filter((v) => v.url !== hdDefaultTileUrl(cell, view))
                            .map((v) => (
                              <option key={v.url} value={v.url}>
                                {v.label}
                              </option>
                            ))}
                        </select>
                      </div>
                    );
                  })}
                </details>
              )}
              <label className="check-row">
                <input type="checkbox" checked={showGrid} onChange={(e) => setShowGrid(e.target.checked)} />
                Grid lines
              </label>
              <label className="check-row">
                <input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} />
                Location labels
              </label>
              <label className="check-row">
                <input type="checkbox" checked={showSafety} onChange={(e) => setShowSafety(e.target.checked)} />
                Playable boundary
              </label>
              <label className="check-row">
                <input type="checkbox" checked={showMinimap} onChange={(e) => setShowMinimap(e.target.checked)} />
                Minimap (M)
              </label>
              <label className="check-row">
                <input type="checkbox" checked={solidRenderView} onChange={(e) => setSolidRenderView(e.target.checked)} />
                🌲 Solid grass backdrop
              </label>
            </div>
          </details>

          <details open className="sidebar-section">
            <summary className="section-title">Layers</summary>
            <div className="layer-list">
              {[...ALLOWED_LAYERS].reverse().map((l) => (
                <label key={l} className={`layer-item ${paintLayer === l ? "target" : ""}`}>
                  <span className="layer-name">
                    {paintLayer === l && <span className="target-dot" title="Active paint layer" />}
                    {l}
                  </span>
                  <input
                    type="checkbox"
                    checked={visibleLayers[l]}
                    onChange={() => setVisibleLayers((prev) => ({ ...prev, [l]: !prev[l] }))}
                  />
                </label>
              ))}
            </div>
          </details>

          <details open className="sidebar-section">
            <summary className="section-title">Locations ({filteredLocations.length})</summary>
            <input
              className="search-input"
              type="text"
              placeholder="Search locations…"
              value={locationSearch}
              onChange={(e) => setLocationSearch(e.target.value)}
            />
            <div className="location-list">
              {filteredLocations.map((l) => {
                const eff = resolveLocationView(layout, canonicalRecs, selectedCaseId, l.location_id, mapView);
                const isSel = selection?.kind === "location" && selection.id === l.location_id;
                const visible = isLocationVisibleIn(layout, selectedCaseId, l.location_id);
                return (
                  <div
                    key={l.location_id}
                    className={`location-item ${isSel ? "selected" : ""}`}
                    onClick={() => selectLocationFromList(l.location_id)}
                    onDoubleClick={() => zoomToLocation(l.location_id)}
                    title={`${l.location_id} — double-click to zoom`}
                  >
                    <span className={`source-dot ${eff.source}`} />
                    <span className="loc-name">{l.name}</span>
                    {eff.hasInternal && <span className="int-dot" title="Has internal-view bounds" />}
                    {selectedCaseId !== "canonical" && (
                      <button
                        className={`eye-btn ${visible ? "on" : ""}`}
                        title={visible ? "Visible in this case" : "Hidden in this case"}
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleLocationVisibility(l.location_id);
                        }}
                      >
                        {visible ? "👁" : "–"}
                      </button>
                    )}
                    <button
                      className="focus-btn"
                      title="Zoom to location"
                      onClick={(e) => {
                        e.stopPropagation();
                        zoomToLocation(l.location_id);
                      }}
                    >
                      ⌖
                    </button>
                  </div>
                );
              })}
            </div>
          </details>

          {selectedCaseId !== "canonical" && (
            <details open className="sidebar-section">
              <summary className="section-title">Clues ({filteredClues.length})</summary>
              <input
                className="search-input"
                type="text"
                placeholder="Search inspect clues..."
                value={clueSearch}
                onChange={(e) => setClueSearch(e.target.value)}
              />
              <div className="location-list">
                {filteredClues.map((c) => {
                  const isSel = selection?.kind === "clue" && selection.id === c.clue_id;
                  const hasPoint = c.x != null && c.y != null;
                  return (
                    <div
                      key={c.clue_id}
                      className={`location-item ${isSel ? "selected" : ""}`}
                      onClick={() => {
                        setSelection({ kind: "clue", id: c.clue_id });
                        setInteriorSceneLocationId(c.location_id || null);
                        setMapView("internal");
                        setUnderlaySource("selected_location_art");
                        setUnderlayOpacity(1);
                        if (activeTool !== "select") setActiveTool("select");
                        const pos = resolveClueWorldPosition(layout, canonicalRecs, selectedCaseId, c, "internal", true);
                        if (pos) zoomToBounds(pos.bounds);
                      }}
                      onDoubleClick={() => {
                        const pos = resolveClueWorldPosition(layout, canonicalRecs, selectedCaseId, c, mapView, underlaySource === "selected_location_art");
                        if (pos) zoomToBounds({ x: pos.x - 3, y: pos.y - 3, w: 6, h: 6 });
                      }}
                      title={`${c.clue_id} - ${c.location_id || "no location"}`}
                    >
                      <span className={`source-dot ${hasPoint ? "internal" : "recommended"}`} />
                      <span className="loc-name">{c.title}</span>
                      <span className="coord-chip">{hasPoint ? `${Math.round(c.x!)}%,${Math.round(c.y!)}%` : "50%,50%"}</span>
                    </div>
                  );
                })}
              </div>
            </details>
          )}

          {selectedCaseId !== "canonical" && activeBodyClues.length > 0 && (
            <details className="sidebar-section">
              <summary className="section-title">Body Clues ({activeBodyClues.length})</summary>
              <div className="view-note">
                Found via victim body examination, not the room search scene.
              </div>
              <div className="location-list">
                {activeBodyClues.map((c) => (
                  <div
                    key={c.clue_id}
                    className="location-item"
                    title={`${c.clue_id} - body examination at ${c.location_id || "discovery location"}`}
                  >
                    <span className="source-dot case_override" />
                    <span className="loc-name">{c.title}</span>
                    <span className="coord-chip">body</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </aside>

        {/* ---------------- Canvas workspace ---------------- */}
        <main className="editor-workspace" ref={workspaceRef}>
          <canvas
            ref={canvasRef}
            className="editor-canvas"
            onPointerDown={onCanvasPointerDown}
            onPointerMove={onCanvasPointerMove}
            onPointerUp={onCanvasPointerUp}
            onPointerLeave={() => {
              if (!gestureRef.current) {
                hoverRef.current = null;
                hoverLocRef.current = null;
                if (statusCoordsRef.current) statusCoordsRef.current.textContent = "—";
                if (statusHoverLocRef.current) statusHoverLocRef.current.textContent = "—";
                requestRender();
              }
            }}
            onContextMenu={(e) => e.preventDefault()}
          />

          <div className="mse-zoombar">
            <button onClick={() => zoomCentered(0.8)} title="Zoom out (-)">
              −
            </button>
            <span ref={zoomLabelRef} className="zoom-label">
              …
            </span>
            <button onClick={() => zoomCentered(1.25)} title="Zoom in (+)">
              +
            </button>
            <button onClick={fitView} title="Fit map (0)">
              ⤢
            </button>
          </div>

          {showMinimap && (
            <canvas
              ref={minimapRef}
              className="minimap"
              onPointerDown={(e) => {
                minimapDragRef.current = true;
                (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId);
                minimapJump(e);
              }}
              onPointerMove={(e) => {
                if (minimapDragRef.current) minimapJump(e);
              }}
              onPointerUp={() => {
                minimapDragRef.current = false;
              }}
            />
          )}
        </main>

        {/* ---------------- Right properties panel ---------------- */}
        <aside className="properties-panel">
          {selectedLocation && selectedLocationEff ? (
            <div className="panel-stack">
              <div className="section-title">Selected Location</div>
              <div className="control-group">
                <label>ID</label>
                <input type="text" value={selectedLocation.location_id} readOnly className="ro" />
              </div>
              <div className="control-group">
                <label>Name</label>
                <input type="text" value={selectedLocation.name} readOnly className="ro" />
              </div>
              <div className="control-group">
                <label>Source · {mapView === "internal" ? "Internal view" : "External view"}</label>
                <div className={`source-tag ${selectedLocationEff.source}`}>
                  {selectedLocationEff.source.replace("_", " ").toUpperCase()}
                  {selectedLocationEff.isOverridden && " (override active)"}
                  {mapView === "internal" && !selectedLocationEff.hasInternal && " (inherited from external)"}
                </div>
                {mapView === "external" && selectedLocationEff.hasInternal && (
                  <div className="view-note">Also has internal-view bounds — press T to edit them.</div>
                )}
              </div>
              <div className="num-grid">
                {(["x", "y", "w", "h"] as const).map((k) => (
                  <div key={k} className="control-group">
                    <label>{k === "x" ? "Tile X" : k === "y" ? "Tile Y" : k === "w" ? "Width" : "Height"}</label>
                    <input
                      type="number"
                      value={selectedLocationEff.bounds[k]}
                      step={fineAdjustment ? 0.5 : 1}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value);
                        if (Number.isNaN(v)) return;
                        const locId = selectedLocation.location_id;
                        mutateLayout((l) => {
                          const b = resolveLocationView(l, canonicalRecs, selectedCaseId, locId, mapView).bounds;
                          const attached =
                            mapView === "external" && (k === "x" || k === "y")
                              ? collectAttached(l, selectedCaseId, locId, b)
                              : [];
                          applyLocationBoundsView(l, canonicalRecs, selectedCaseId, locId, { [k]: v }, mapView);
                          if (attached.length) {
                            applyAttached(l, attached, k === "x" ? v - b.x : 0, k === "y" ? v - b.y : 0, cols, rows);
                          }
                        });
                      }}
                    />
                  </div>
                ))}
              </div>
              <div className="num-grid">
                <div className="control-group">
                  <label>Rotation ° (match camera angle)</label>
                  <input
                    type="number"
                    step={1}
                    value={selectedLocationEff.bounds.rotation ?? 0}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value);
                      if (Number.isNaN(v)) return;
                      const locId = selectedLocation.location_id;
                      mutateLayout((l) =>
                        applyLocationBoundsView(l, canonicalRecs, selectedCaseId, locId, { rotation: normalizeRotation(v) }, mapView)
                      );
                    }}
                  />
                </div>
                <div className="control-group">
                  <label>&nbsp;</label>
                  <button
                    className="mse-btn mse-btn-secondary"
                    disabled={!selectedLocationEff.bounds.rotation}
                    onClick={() => {
                      const locId = selectedLocation.location_id;
                      mutateLayout(
                        (l) => applyLocationBoundsView(l, canonicalRecs, selectedCaseId, locId, { rotation: undefined }, mapView),
                        { undoable: true }
                      );
                    }}
                  >
                    ↺ Reset 0°
                  </button>
                </div>
              </div>
              <div className="control-group">
                <label>Mode</label>
                <select
                  value={selectedLocationEff.mode}
                  onChange={(e) => {
                    const val = e.target.value;
                    const locId = selectedLocation.location_id;
                    const bounds = selectedLocationEff.bounds;
                    mutateLayout((l) => {
                      if (!l.canonical_locations[locId]) {
                        l.canonical_locations[locId] = { bounds: { ...bounds }, mode: val };
                      } else {
                        l.canonical_locations[locId].mode = val;
                      }
                    });
                  }}
                >
                  <option value="exterior">Exterior</option>
                  <option value="interior">Interior</option>
                </select>
              </div>
              {selectedCaseId !== "canonical" && (
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={isLocationVisibleIn(layout, selectedCaseId, selectedLocation.location_id)}
                    onChange={() => toggleLocationVisibility(selectedLocation.location_id)}
                  />
                  Visible in this case override
                </label>
              )}
              <button
                className="mse-btn mse-btn-primary"
                title="Refine the rough box so its edges hug the structure outline in the underlay art (S)"
                onClick={snapSelectionToStructure}
              >
                🧲 Snap to structure
              </button>
              {mapView === "internal" ? (
                <div className="btn-row">
                  <button className="mse-btn mse-btn-secondary" onClick={() => zoomToLocation(selectedLocation.location_id)}>
                    ⌖ Zoom to
                  </button>
                  <button
                    className="mse-btn mse-btn-secondary"
                    title="Set the internal-view bounds to a copy of the current external bounds"
                    onClick={() => {
                      const locId = selectedLocation.location_id;
                      mutateLayout(
                        (l) => {
                          const ext = resolveLocation(l, canonicalRecs, selectedCaseId, locId).bounds;
                          applyLocationBoundsView(l, canonicalRecs, selectedCaseId, locId, { ...ext }, "internal");
                        },
                        { undoable: true }
                      );
                      showToast("Internal bounds copied from external view.", "success");
                    }}
                  >
                    ⧉ Copy external
                  </button>
                  <button
                    className="mse-btn mse-btn-secondary"
                    disabled={!selectedLocationEff.hasInternal}
                    title="Remove the internal-view bounds so this location inherits the external ones"
                    onClick={() => {
                      const locId = selectedLocation.location_id;
                      mutateLayout(
                        (l) => {
                          if (l.canonical_locations[locId]) delete l.canonical_locations[locId].bounds_internal;
                        },
                        { undoable: true }
                      );
                      showToast("Internal bounds cleared — inheriting external view.", "info");
                    }}
                  >
                    ↺ Inherit external
                  </button>
                </div>
              ) : (
                <>
                  <div className="btn-row">
                    <button className="mse-btn mse-btn-secondary" onClick={() => zoomToLocation(selectedLocation.location_id)}>
                      ⌖ Zoom to
                    </button>
                    <button className="mse-btn mse-btn-secondary" onClick={resetToCanonicalRec}>
                      Recommended
                    </button>
                    <button className="mse-btn mse-btn-secondary" onClick={resetToLegacyFallback}>
                      Legacy
                    </button>
                  </div>
                  {selectedCaseId !== "canonical" && (
                    <button className="mse-btn mse-btn-secondary" onClick={promoteToCanonical}>
                      👑 Promote bounds to canonical
                    </button>
                  )}
                </>
              )}
            </div>
          ) : selectedObject && selectedObjectEff ? (
            <div className="panel-stack">
              <div className="section-title">Selected Evidence Anchor</div>
              <div className="control-group">
                <label>ID</label>
                <input type="text" value={selectedObject.object_id} readOnly className="ro" />
              </div>
              <div className="control-group">
                <label>Name</label>
                <input type="text" value={selectedObject.name} readOnly className="ro" />
              </div>
              <div className="control-group">
                <label>Anchored In</label>
                <input type="text" value={selectedObjectEff.location_id} readOnly className="ro" />
              </div>
              <div className="num-grid">
                {(["x", "y"] as const).map((k) => (
                  <div key={k} className="control-group">
                    <label>Anchor {k.toUpperCase()}</label>
                    <input
                      type="number"
                      value={selectedObjectEff.anchor[k]}
                      step={fineAdjustment ? 0.5 : 1}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value);
                        if (Number.isNaN(v)) return;
                        mutateLayout((l) => applyAnchor(l, canonicalRecs, selectedCaseId, selectedObject, { [k]: v }));
                      }}
                    />
                  </div>
                ))}
              </div>
              <div className="control-group">
                <label>Render Policy</label>
                <select
                  value={selectedObjectEff.render_policy || "discovery_gated"}
                  onChange={(e) => {
                    const val = e.target.value;
                    mutateLayout((l) => {
                      applyAnchor(l, canonicalRecs, selectedCaseId, selectedObject, {});
                      l.case_overrides[selectedCaseId].object_anchors[selectedObject.object_id].render_policy = val;
                    });
                  }}
                >
                  {RENDER_POLICIES.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ) : selectedClue ? (
            <div className="panel-stack">
              <div className="section-title">Selected Clue Hotspot</div>
              <div className="control-group">
                <label>ID</label>
                <input type="text" value={selectedClue.clue_id} readOnly className="ro" />
              </div>
              <div className="control-group">
                <label>Title</label>
                <input type="text" value={selectedClue.title} readOnly className="ro" />
              </div>
              <div className="control-group">
                <label>Search Location</label>
                <input type="text" value={selectedClue.location_id || "No inspect location"} readOnly className="ro" />
              </div>
              <div className="view-note">
                Saved to this case's clues.json as percentages within the current location art. Use Internal view for HD interiors.
              </div>
              <div className="num-grid">
                {(["x", "y"] as const).map((k) => (
                  <div key={k} className="control-group">
                    <label>{k.toUpperCase()} %</label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      step={0.1}
                      value={selectedClue[k] ?? 50}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value);
                        if (Number.isNaN(v)) return;
                        saveClueLocation(selectedClue, {
                          x: k === "x" ? clamp(v, 0, 100) : selectedClue.x ?? 50,
                          y: k === "y" ? clamp(v, 0, 100) : selectedClue.y ?? 50,
                          radius: selectedClue.radius
                        });
                      }}
                    />
                  </div>
                ))}
              </div>
              <div className="control-group">
                <label>Search Radius % ({selectedClue.radius || 8})</label>
                <input
                  type="range"
                  min={1}
                  max={25}
                  step={0.5}
                  value={selectedClue.radius || 8}
                  onChange={(e) => {
                    const radius = parseFloat(e.target.value);
                    saveClueLocation(
                      selectedClue,
                      {
                        x: selectedClue.x ?? 50,
                        y: selectedClue.y ?? 50,
                        radius
                      },
                      true
                    );
                  }}
                />
              </div>
              <div className="btn-row">
                <button
                  className="mse-btn mse-btn-secondary"
                  disabled={!selectedClue.location_id}
                  onClick={() => {
                    if (!selectedClue.location_id) return;
                    if (underlaySource === "selected_location_art") {
                      saveClueLocation(selectedClue, { x: 50, y: 50, radius: selectedClue.radius });
                      zoomToBounds({ x: 0, y: 0, w: 100, h: 100 });
                    } else {
                      const b = resolveLocationView(layout, canonicalRecs, selectedCaseId, selectedClue.location_id, mapView).bounds;
                      placeClueAtWorld(selectedClue, b.x + b.w / 2, b.y + b.h / 2);
                      zoomToBounds(b);
                    }
                  }}
                >
                  ⌖ Center in location
                </button>
                <button
                  className="mse-btn mse-btn-secondary"
                  disabled={!selectedCluePos}
                  onClick={() => selectedCluePos && zoomToBounds({ x: selectedCluePos.x - 3, y: selectedCluePos.y - 3, w: 6, h: 6 })}
                >
                  Zoom to hotspot
                </button>
              </div>
            </div>
          ) : selectedProp ? (
            <div className="panel-stack">
              <div className="section-title">Selected Prop</div>
              <div className="control-group">
                <label>Instance</label>
                <input type="text" value={selectedProp.instance_id} readOnly className="ro" />
              </div>
              <div className="control-group">
                <label>Asset</label>
                <div className="asset-tag">
                  <span>{PROP_EMOJIS[selectedProp.asset_id] || "📦"}</span> {selectedProp.asset_id}
                </div>
              </div>
              <div className="num-grid">
                {(
                  [
                    ["x", "Prop X"],
                    ["y", "Prop Y"],
                    ["w", "Width"],
                    ["h", "Height"]
                  ] as const
                ).map(([k, label]) => (
                  <div key={k} className="control-group">
                    <label>{label}</label>
                    <input
                      type="number"
                      value={k === "w" ? selectedProp.w || 1 : k === "h" ? selectedProp.h || 1 : selectedProp[k]}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value);
                        if (Number.isNaN(v)) return;
                        mutateLayout((l) => {
                          applyPropUpdate(l, selectedProp.instance_id, (p) => {
                            (p as any)[k] = k === "w" || k === "h" ? Math.max(1, v) : v;
                          });
                        });
                      }}
                    />
                  </div>
                ))}
              </div>
              <div className="control-group">
                <label>Layer</label>
                <select
                  value={selectedProp.layer || "props"}
                  onChange={(e) => {
                    const val = e.target.value;
                    mutateLayout((l) => {
                      applyPropUpdate(l, selectedProp.instance_id, (p) => (p.layer = val));
                    });
                  }}
                >
                  {ALLOWED_LAYERS.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              <div className="control-group">
                <label>Render Policy</label>
                <select
                  value={selectedProp.render_policy || "always_visible"}
                  onChange={(e) => {
                    const val = e.target.value;
                    mutateLayout((l) => {
                      applyPropUpdate(l, selectedProp.instance_id, (p) => (p.render_policy = val));
                    });
                  }}
                >
                  {RENDER_POLICIES.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="control-group">
                <label>Linked Clue Object ID (optional)</label>
                <input
                  type="text"
                  placeholder="e.g. obj_mud_bootprint"
                  value={selectedProp.object_id || ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    mutateLayout((l) => {
                      applyPropUpdate(l, selectedProp.instance_id, (p) => (p.object_id = val || undefined));
                    });
                  }}
                />
              </div>
              <div className="btn-row">
                <button className="mse-btn mse-btn-secondary" onClick={() => duplicateProp(selectedProp.instance_id)}>
                  ⧉ Duplicate
                </button>
                <button className="mse-btn mse-btn-danger" onClick={() => deleteProp(selectedProp.instance_id)}>
                  🗑 Delete
                </button>
              </div>
            </div>
          ) : selectedLight && selectedLightEff ? (
            <div className="panel-stack">
              <div className="section-title">Selected Light</div>
              <div className="control-group">
                <label>Instance</label>
                <input type="text" value={selection!.id} readOnly className="ro" />
              </div>
              {mapView === "internal" && (
                <div className="view-note">
                  Editing internal-view fields{selectedLightEff.hasInternal ? "" : " (inheriting external — first edit seeds them)"}.
                </div>
              )}
              <div className="control-group">
                <label>Asset ({mapView === "internal" ? "internal" : "external"})</label>
                <select
                  value={selectedLightEff.semantic_asset_id}
                  onChange={(e) => {
                    const val = e.target.value;
                    mutateLayout((l) => {
                      applyLightUpdate(l, selection!.id, (light) => applyLightView(light, { semantic_asset_id: val }, mapView));
                    });
                  }}
                >
                  {ALLOWED_LIGHT_ASSETS.map((aId) => (
                    <option key={aId} value={aId}>
                      {LIGHT_ASSET_SWATCHES[aId]?.label || aId}
                    </option>
                  ))}
                </select>
              </div>
              <div className="control-group">
                <label>Location (grouping/scoping)</label>
                <select
                  value={selectedLight.location_id}
                  onChange={(e) => {
                    const val = e.target.value;
                    mutateLayout((l) => {
                      applyLightUpdate(l, selection!.id, (light) => (light.location_id = val));
                    });
                  }}
                >
                  {Object.keys(canonicalRecs).map((locId) => (
                    <option key={locId} value={locId}>
                      {locId}
                    </option>
                  ))}
                </select>
              </div>
              <div className="num-grid">
                {(
                  [
                    ["x", "Centre X"],
                    ["y", "Centre Y"],
                    ["width", "Width"],
                    ["height", "Height"]
                  ] as const
                ).map(([k, label]) => (
                  <div key={k} className="control-group">
                    <label>{label}</label>
                    <input
                      type="number"
                      step={fineAdjustment ? 0.5 : 1}
                      value={selectedLightEff[k]}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value);
                        if (Number.isNaN(v)) return;
                        mutateLayout((l) => {
                          applyLightUpdate(l, selection!.id, (light) =>
                            applyLightView(light, { [k]: k === "width" || k === "height" ? Math.max(0.5, v) : v }, mapView)
                          );
                        });
                      }}
                    />
                  </div>
                ))}
              </div>
              <div className="num-grid">
                <div className="control-group">
                  <label>From</label>
                  <input
                    type="time"
                    value={selectedLight.from}
                    onChange={(e) => {
                      const val = e.target.value;
                      mutateLayout((l) => {
                        applyLightUpdate(l, selection!.id, (light) => (light.from = val));
                      });
                    }}
                  />
                </div>
                <div className="control-group">
                  <label>To</label>
                  <input
                    type="time"
                    value={selectedLight.to}
                    onChange={(e) => {
                      const val = e.target.value;
                      mutateLayout((l) => {
                        applyLightUpdate(l, selection!.id, (light) => (light.to = val));
                      });
                    }}
                  />
                </div>
              </div>
              <div className="control-group">
                <label>Opacity ({(selectedLightEff.opacity ?? 0.65).toFixed(2)})</label>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={selectedLightEff.opacity ?? 0.65}
                  onChange={(e) => {
                    const v = parseFloat(e.target.value);
                    mutateLayout((l) => {
                      applyLightUpdate(l, selection!.id, (light) => applyLightView(light, { opacity: v }, mapView));
                    });
                  }}
                />
              </div>
              <div className="btn-row">
                <button className="mse-btn mse-btn-secondary" onClick={() => duplicateLight(selection!.id)}>
                  ⧉ Duplicate
                </button>
                <button className="mse-btn mse-btn-danger" onClick={() => deleteLight(selection!.id)}>
                  🗑 Delete
                </button>
              </div>
            </div>
          ) : selectedAmbient ? (
            <div className="panel-stack">
              <div className="section-title">Selected Ambient Effect</div>
              <div className="control-group">
                <label>Instance</label>
                <input type="text" value={selection!.id} readOnly className="ro" />
              </div>
              <div className="control-group">
                <label>Asset</label>
                <select
                  value={selectedAmbient.asset_id}
                  onChange={(e) => {
                    const val = e.target.value;
                    mutateLayout((l) => {
                      applyAmbientUpdate(l, selection!.id, (sprite) => {
                        sprite.asset_id = val;
                        const asset = AMBIENT_ASSET_SWATCHES[val];
                        if (asset) sprite.opacity = asset.opacity;
                      });
                    });
                  }}
                >
                  {ALLOWED_AMBIENT_ASSETS.map((aId) => (
                    <option key={aId} value={aId}>
                      {AMBIENT_ASSET_SWATCHES[aId]?.label || aId}
                    </option>
                  ))}
                </select>
              </div>
              <div className="num-grid">
                {(
                  [
                    ["x", "X"],
                    ["y", "Y"],
                    ["width", "Width"],
                    ["height", "Height"]
                  ] as const
                ).map(([k, label]) => (
                  <div key={k} className="control-group">
                    <label>{label}</label>
                    <input
                      type="number"
                      step={fineAdjustment ? 0.5 : 1}
                      value={selectedAmbient[k]}
                      onChange={(e) => {
                        const v = parseFloat(e.target.value);
                        if (Number.isNaN(v)) return;
                        mutateLayout((l) => {
                          applyAmbientUpdate(l, selection!.id, (sprite) => {
                            sprite[k] = k === "width" || k === "height" ? Math.max(0.5, v) : v;
                          });
                        });
                      }}
                    />
                  </div>
                ))}
              </div>
              <div className="num-grid">
                <div className="control-group">
                  <label>From</label>
                  <input
                    type="time"
                    value={selectedAmbient.from || "00:00"}
                    onChange={(e) => {
                      const val = e.target.value;
                      mutateLayout((l) => {
                        applyAmbientUpdate(l, selection!.id, (sprite) => (sprite.from = val));
                      });
                    }}
                  />
                </div>
                <div className="control-group">
                  <label>To</label>
                  <input
                    type="time"
                    value={selectedAmbient.to || "23:59"}
                    onChange={(e) => {
                      const val = e.target.value;
                      mutateLayout((l) => {
                        applyAmbientUpdate(l, selection!.id, (sprite) => (sprite.to = val));
                      });
                    }}
                  />
                </div>
              </div>
              <div className="control-group">
                <label>Opacity ({(selectedAmbient.opacity ?? 0.6).toFixed(2)})</label>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={selectedAmbient.opacity ?? 0.6}
                  onChange={(e) => {
                    const v = parseFloat(e.target.value);
                    mutateLayout((l) => {
                      applyAmbientUpdate(l, selection!.id, (sprite) => (sprite.opacity = v));
                    });
                  }}
                />
              </div>
              <div className="btn-row">
                <button className="mse-btn mse-btn-secondary" onClick={() => duplicateAmbient(selection!.id)}>
                  ⧉ Duplicate
                </button>
                <button className="mse-btn mse-btn-danger" onClick={() => deleteAmbient(selection!.id)}>
                  🗑 Delete
                </button>
              </div>
            </div>
          ) : selectedBuilding ? (
            <div className="panel-stack">
              <div className="section-title">Selected Building</div>
              <div className="control-group">
                <label>Instance</label>
                <input type="text" value={selectedBuilding.instance_id} readOnly className="ro" />
              </div>
              <div className="control-group">
                <label>Bundle</label>
                <div className="asset-tag">
                  <span>🏠</span> {buildingLibrary[selectedBuilding.asset_id]?.display_name || selectedBuilding.asset_id}
                </div>
              </div>
              <div className="num-grid">
                {(
                  [
                    ["x", "Tile X"],
                    ["y", "Tile Y"]
                  ] as const
                ).map(([k, label]) => (
                  <div key={k} className="control-group">
                    <label>{label}</label>
                    <input
                      type="number"
                      value={selectedBuilding[k]}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        if (Number.isNaN(v)) return;
                        mutateLayout(
                          (l) => {
                            const inst = findBuilding(l, selectedBuilding.instance_id);
                            if (!inst) return;
                            const rotation = inst.rotation || 0;
                            const target = clampBuildingXY(l, inst, k === "x" ? v : inst.x, k === "y" ? v : inst.y, rotation);
                            applyBuildingPlacement(l, inst.instance_id, target.x, target.y, rotation);
                          },
                          { undoable: true }
                        );
                      }}
                    />
                  </div>
                ))}
              </div>
              <div className="inline-row">
                <label className="mini-label">Rotation (R)</label>
                <div className="mse-rot-group">
                  {[0, 90, 180, 270].map((deg) => (
                    <button
                      key={deg}
                      className={`mse-rot-btn ${(selectedBuilding.rotation || 0) === deg ? "active" : ""}`}
                      title={`Door faces ${buildingFrontEdge(deg)}`}
                      onClick={() => {
                        mutateLayout(
                          (l) => {
                            const inst = findBuilding(l, selectedBuilding.instance_id);
                            if (!inst) return;
                            const target = clampBuildingXY(l, inst, inst.x, inst.y, deg);
                            applyBuildingPlacement(l, inst.instance_id, target.x, target.y, deg);
                          },
                          { undoable: true }
                        );
                      }}
                    >
                      {deg}°
                    </button>
                  ))}
                </div>
              </div>
              <div className="view-note">
                Door faces {buildingFrontEdge(selectedBuilding.rotation || 0)} · dressing follows moves and rotation. Connector
                paths don't move — re-run Connect paths after repositioning.
              </div>
              <div className="btn-row">
                <button className="mse-btn mse-btn-secondary" onClick={() => duplicateBuilding(selectedBuilding.instance_id)}>
                  ⧉ Duplicate
                </button>
                <button className="mse-btn mse-btn-danger" onClick={() => deleteBuilding(selectedBuilding.instance_id)}>
                  🗑 Delete
                </button>
              </div>
            </div>
          ) : (
            <div className="panel-stack">
              <div className="section-title">Workspace</div>
              <label className="check-row">
                <input type="checkbox" checked={fineAdjustment} onChange={(e) => setFineAdjustment(e.target.checked)} />
                Fine snap (0.5-tile increments)
              </label>
              <div className="control-group">
                <label>Preview Mode</label>
                <select value={previewMode} onChange={(e) => setPreviewMode(e.target.value as PreviewMode)}>
                  <option value="debug">Canonical Debug View</option>
                  <option value="player_reveal">Player Case Reveal View</option>
                  <option value="fog">Fogged Non-case Areas</option>
                </select>
              </div>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={showEvidenceAnchors}
                  onChange={(e) => setShowEvidenceAnchors(e.target.checked)}
                />
                Show evidence anchors
              </label>
              <div className="hint-box">
                <strong>{activeToolDef.label}</strong>
                <span>{activeToolDef.hint}</span>
              </div>
            </div>
          )}

          <div className="validations-block">
            <div className="section-title">Validations ({validationWarnings.length})</div>
            {serverErrors.length > 0 && (
              <div className="warnings-panel">
                <strong>Server rejected the last save:</strong>
                {serverErrors.map((e, idx) => (
                  <div key={idx}>• {e}</div>
                ))}
              </div>
            )}
            {validationWarnings.length === 0 ? (
              serverErrors.length === 0 && <div className="ok-box">✓ No coordinate warnings.</div>
            ) : (
              <div className="warnings-panel">
                {validationWarnings.map((w, idx) => (
                  <div key={idx}>• {w}</div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* ---------------- Status bar ---------------- */}
      <footer className="status-bar">
        <span className="sb-tool">
          {activeToolDef.icon} {activeToolDef.label}
        </span>
        <span className={`sb-view ${mapView}`}>{mapView === "internal" ? "🪑 Internal view" : "🏠 External view"}</span>
        <span className="sb-hint">{activeToolDef.hint}</span>
        <span className="sb-right">
          <span>
            Tile <span ref={statusCoordsRef} className="mono">—</span>
          </span>
          <span>
            Loc <span ref={statusHoverLocRef} className="mono">—</span>
          </span>
          <span>
            Layer <span className="mono">{activeTool === "prop" ? propLayer : activeTool === "building" ? "structures + dressing" : paintLayer}</span>
          </span>
          <span>
            Tiles <span className="mono">{paintedTileCount}</span>
          </span>
          <span>
            Zoom <span ref={statusZoomRef} className="mono">…</span>
          </span>
        </span>
      </footer>

      {/* ---------------- Modals ---------------- */}
      {showExportModal && (
        <div className="mse-modal-overlay" onClick={() => setShowExportModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="section-title">Export Layout JSON</div>
            <textarea readOnly value={JSON.stringify(layout, null, 2)} onClick={(e) => (e.target as HTMLTextAreaElement).select()} />
            <div className="modal-actions">
              <button className="mse-btn mse-btn-secondary" onClick={handleDownload}>
                ⬇ Download .json
              </button>
              <button
                className="mse-btn mse-btn-secondary"
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(layout, null, 2));
                  showToast("Copied layout to clipboard!", "success");
                }}
              >
                📋 Copy
              </button>
              <button className="mse-btn mse-btn-primary" onClick={() => setShowExportModal(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {showImportModal && (
        <div className="mse-modal-overlay" onClick={() => setShowImportModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="section-title">Paste Layout JSON (schema v2)</div>
            <textarea value={importText} placeholder="Paste JSON here…" onChange={(e) => setImportText(e.target.value)} />
            <div className="modal-actions">
              <button className="mse-btn mse-btn-secondary" onClick={() => setShowImportModal(false)}>
                Cancel
              </button>
              <button className="mse-btn mse-btn-primary" onClick={handleImportTextSubmit}>
                Import Layout
              </button>
            </div>
          </div>
        </div>
      )}

      {showShortcuts && (
        <div className="mse-modal-overlay" onClick={() => setShowShortcuts(false)}>
          <div className="modal-content shortcuts" onClick={(e) => e.stopPropagation()}>
            <div className="section-title">Keyboard Shortcuts</div>
            <div className="shortcuts-grid">
              {TOOL_DEFS.map((t) => (
                <React.Fragment key={t.id}>
                  <kbd>{t.key}</kbd>
                  <span>{t.label}</span>
                </React.Fragment>
              ))}
              <kbd>⌘Z / ⇧⌘Z</kbd>
              <span>Undo / Redo</span>
              <kbd>⌘S</kbd>
              <span>Save layout</span>
              <kbd>⌘D</kbd>
              <span>Duplicate selected prop</span>
              <kbd>Space</kbd>
              <span>Hold to pan (any tool)</span>
              <kbd>Scroll</kbd>
              <span>Pan · ⌘/Ctrl+scroll or pinch to zoom</span>
              <kbd>+ / − / 0</kbd>
              <span>Zoom in / out / fit map</span>
              <kbd>[ / ]</kbd>
              <span>Brush size down / up</span>
              <kbd>Arrows</kbd>
              <span>Nudge selection (⇧ = 5 tiles · ⌥ = 0.1 micro-nudge)</span>
              <kbd>, / .</kbd>
              <span>Rotate selected location 1° (⇧ = 15°) · drag the amber handle to rotate freely</span>
              <kbd>S</kbd>
              <span>Snap selected location to the structure outline in the art</span>
              <kbd>Alt+click</kbd>
              <span>Eyedropper while painting · erase with rectangle tool</span>
              <kbd>Del</kbd>
              <span>Delete selected prop</span>
              <kbd>M</kbd>
              <span>Toggle minimap</span>
              <kbd>T</kbd>
              <span>Toggle external / internal map view</span>
              <kbd>Esc</kbd>
              <span>Cancel gesture / clear selection</span>
            </div>
            <div className="modal-actions">
              <button className="mse-btn mse-btn-primary" onClick={() => setShowShortcuts(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers & styles
// ---------------------------------------------------------------------------

function normRect(a: { x: number; y: number }, b: { x: number; y: number }) {
  const x = Math.min(a.x, b.x);
  const y = Math.min(a.y, b.y);
  return { x, y, w: Math.abs(a.x - b.x) + 1, h: Math.abs(a.y - b.y) + 1 };
}

function brushCells(cx: number, cy: number, size: number, cols: number, rows: number) {
  const half = Math.floor((size - 1) / 2);
  const cells: Array<{ x: number; y: number }> = [];
  for (let dx = 0; dx < size; dx++) {
    for (let dy = 0; dy < size; dy++) {
      const x = cx - half + dx;
      const y = cy - half + dy;
      if (x < 0 || y < 0 || x >= cols || y >= rows) continue;
      cells.push({ x, y });
    }
  }
  return cells;
}

const BASE_SCREEN_CSS = `
  .dev-map-loading, .dev-map-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 14px;
    height: 100vh;
    width: 100vw;
    background: #0a0a0d;
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  .dev-map-loading .spinner {
    width: 28px;
    height: 28px;
    border: 3px solid #27272a;
    border-top-color: #38bdf8;
    border-radius: 50%;
    animation: dev-map-spin 0.9s linear infinite;
  }
  @keyframes dev-map-spin { to { transform: rotate(360deg); } }
  .dev-map-error .retry-btn {
    padding: 8px 16px;
    border-radius: 6px;
    border: none;
    background: #0ea5e9;
    color: #fff;
    font-weight: 600;
    cursor: pointer;
  }
`;

const EDITOR_CSS = `
  ${BASE_SCREEN_CSS}
  .dev-map-root {
    display: flex;
    flex-direction: column;
    height: 100vh;
    width: 100vw;
    background: #0a0a0d;
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    overflow: hidden;
  }
  .dev-map-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    background: #131316;
    border-bottom: 1px solid #26262b;
    z-index: 10;
    gap: 12px;
    flex-wrap: wrap;
  }
  .header-title-section { display: flex; align-items: center; gap: 12px; }
  .header-title-section h2 { font-size: 1.05rem; margin: 0; font-weight: 700; color: #fff; white-space: nowrap; }
  .grid-chip {
    font-size: 0.7rem;
    font-family: ui-monospace, monospace;
    color: #94a3b8;
    background: #1c1c21;
    border: 1px solid #2c2c33;
    padding: 3px 8px;
    border-radius: 9999px;
    white-space: nowrap;
  }
  .dirty-badge {
    background: rgba(234, 179, 8, 0.15);
    color: #eab308;
    border: 1px solid rgba(234, 179, 8, 0.3);
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 0.72rem;
    font-weight: 600;
    white-space: nowrap;
  }
  .actions-group { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .header-divider { width: 1px; height: 22px; background: #2c2c33; margin: 0 4px; }
  .mse-btn {
    padding: 7px 12px;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: background 0.12s ease, border-color 0.12s ease;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
  }
  .mse-btn:disabled { opacity: 0.4; cursor: default; }
  .mse-btn-primary { background: #0ea5e9; color: #fff; }
  .mse-btn-primary:hover:not(:disabled) { background: #0284c7; }
  .mse-btn-primary.mse-btn-warn { background: #b45309; }
  .mse-btn-primary.mse-btn-warn:hover { background: #92400e; }
  .mse-btn-secondary { background: #222227; color: #e2e8f0; border: 1px solid #333339; }
  .mse-btn-secondary:hover:not(:disabled) { background: #333339; }
  .mse-btn-danger { background: #be123c; color: #fff; }
  .mse-btn-danger:hover { background: #9f1239; }

  .main-editor-layout { display: flex; flex: 1; overflow: hidden; position: relative; }

  .left-sidebar {
    width: 292px;
    min-width: 292px;
    background: #131316;
    border-right: 1px solid #26262b;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 14px;
    gap: 16px;
  }
  .properties-panel {
    width: 312px;
    min-width: 312px;
    background: #131316;
    border-left: 1px solid #26262b;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 14px;
    gap: 16px;
  }
  .panel-stack { display: flex; flex-direction: column; gap: 12px; }
  .section-title {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #38bdf8;
    font-weight: 700;
  }
  .sidebar-section > summary { cursor: pointer; user-select: none; list-style: none; display: flex; align-items: center; gap: 6px; }
  .sidebar-section > summary::before { content: "▸"; color: #52525b; transition: transform 0.12s; font-size: 0.7rem; }
  .sidebar-section[open] > summary::before { transform: rotate(90deg); }
  .sidebar-section > *:not(summary) { margin-top: 10px; }

  .control-group { display: flex; flex-direction: column; gap: 6px; }
  .control-group label { font-size: 0.72rem; color: #94a3b8; }
  .control-group select, .control-group input[type="text"], .control-group input[type="number"], .search-input {
    background: #0a0a0d;
    border: 1px solid #2c2c33;
    color: #e2e8f0;
    padding: 7px 10px;
    border-radius: 6px;
    font-size: 0.82rem;
    outline: none;
    width: 100%;
    box-sizing: border-box;
  }
  .control-group select:focus, .control-group input:focus, .search-input:focus { border-color: #38bdf8; }
  .control-group input.ro { opacity: 0.55; }
  .inline-row { display: flex; align-items: center; gap: 8px; }
  .inline-row select, .inline-row input[type="range"] { flex: 1; min-width: 0; }
  .mini-label { font-size: 0.7rem; color: #94a3b8; white-space: nowrap; min-width: 78px; }
  .check-row {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 0.78rem;
    color: #b6c2d0;
    user-select: none;
  }
  .btn-row { display: flex; gap: 8px; flex-wrap: wrap; }
  .btn-row .mse-btn { flex: 1; justify-content: center; }
  .num-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }

  .tool-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
  .mse-tool-btn {
    position: relative;
    padding: 8px 2px 6px;
    background: #0a0a0d;
    border: 1px solid #2c2c33;
    border-radius: 8px;
    color: #94a3b8;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    transition: border-color 0.12s ease, color 0.12s ease, background 0.12s ease;
  }
  .mse-tool-btn:hover { border-color: #52525b; color: #e2e8f0; }
  .mse-tool-btn.active { background: rgba(14, 165, 233, 0.12); border-color: #0ea5e9; color: #38bdf8; }
  .tool-icon { font-size: 15px; line-height: 1; }
  .tool-name { font-size: 8.5px; font-weight: 600; }
  .tool-key {
    position: absolute;
    top: 2px;
    right: 4px;
    font-size: 8px;
    color: #52525b;
    font-family: ui-monospace, monospace;
  }
  .mse-tool-btn.active .tool-key { color: #38bdf8; }

  .palette-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    max-height: 210px;
    overflow-y: auto;
    background: #0a0a0d;
    padding: 8px;
    border-radius: 8px;
    border: 1px solid #2c2c33;
    align-items: start;
  }
  .palette-item {
    aspect-ratio: 1 / 1;
    width: 100%;
    border-radius: 5px;
    border: 1px solid #2c2c33;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    transition: transform 0.1s ease, border-color 0.1s ease, box-shadow 0.1s ease;
    overflow: hidden;
    position: relative;
    min-height: 50px;
  }
  .palette-item.prop { background: #1c1c21; }
  .palette-item:hover { transform: scale(1.06); border-color: #a1a1aa; z-index: 2; }
  .palette-item.active { border-color: #38bdf8; box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.45); }
  .palette-emoji { font-size: 16px; }
  .palette-grid.buildings { grid-template-columns: repeat(3, 1fr); max-height: 320px; }
  .mse-rot-group { display: flex; gap: 4px; flex: 1; }
  .mse-rot-btn {
    flex: 1;
    padding: 3px 0;
    font-size: 11px;
    background: #1c1c21;
    border: 1px solid #2c2c33;
    border-radius: 5px;
    color: #d4d4d8;
    cursor: pointer;
  }
  .mse-rot-btn:hover { border-color: #a1a1aa; }
  .mse-rot-btn.active { border-color: #38bdf8; color: #38bdf8; box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.35); }
  .palette-thumb {
    width: 100%;
    height: 100%;
    object-fit: contain;
    padding: 3px 3px 12px;
    image-rendering: pixelated;
  }
  .palette-item-text {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(0, 0, 0, 0.7);
    font-size: 7px;
    color: #d4d4d8;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    padding: 2px 1px;
  }

  .layer-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
    background: #0a0a0d;
    padding: 6px;
    border-radius: 8px;
    border: 1px solid #2c2c33;
    max-height: 190px;
    overflow-y: auto;
  }
  .layer-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.73rem;
    color: #94a3b8;
    padding: 3px 6px;
    border-radius: 4px;
    cursor: pointer;
  }
  .layer-item:hover { background: #1c1c21; }
  .layer-item.target { color: #e2e8f0; }
  .layer-name { display: flex; align-items: center; gap: 6px; }
  .target-dot { width: 6px; height: 6px; border-radius: 50%; background: #38bdf8; }

  .location-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-height: 240px;
    overflow-y: auto;
    background: #0a0a0d;
    border: 1px solid #2c2c33;
    border-radius: 8px;
    padding: 4px;
  }
  .location-item {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 5px 7px;
    border-radius: 5px;
    font-size: 0.78rem;
    color: #cbd5e1;
    cursor: pointer;
    user-select: none;
  }
  .location-item:hover { background: #1c1c21; }
  .location-item.selected { background: rgba(14, 165, 233, 0.14); color: #7dd3fc; }
  .loc-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .source-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .source-dot.recommended { background: #64748b; }
  .source-dot.canonical { background: #38bdf8; }
  .source-dot.case_override { background: #fda4af; }
  .source-dot.internal { background: #fbbf24; }
  .eye-btn, .focus-btn {
    background: none;
    border: none;
    color: #52525b;
    cursor: pointer;
    font-size: 11px;
    padding: 1px 3px;
    border-radius: 4px;
    flex-shrink: 0;
  }
  .eye-btn.on { color: #4ade80; }
  .eye-btn:hover, .focus-btn:hover { background: #26262b; color: #e2e8f0; }

  .editor-workspace {
    flex: 1;
    position: relative;
    overflow: hidden;
    background: #0a0a0d;
    min-width: 0;
  }
  .editor-canvas {
    display: block;
    width: 100%;
    height: 100%;
    touch-action: none;
  }
  .mse-zoombar {
    position: absolute;
    left: 14px;
    bottom: 14px;
    display: flex;
    align-items: center;
    gap: 2px;
    background: rgba(19, 19, 22, 0.92);
    border: 1px solid #2c2c33;
    border-radius: 8px;
    padding: 3px;
    backdrop-filter: blur(6px);
  }
  .mse-zoombar button {
    width: 28px;
    height: 26px;
    background: none;
    border: none;
    color: #cbd5e1;
    font-size: 14px;
    cursor: pointer;
    border-radius: 5px;
  }
  .mse-zoombar button:hover { background: #26262b; }
  .zoom-label {
    min-width: 44px;
    text-align: center;
    font-size: 0.72rem;
    font-family: ui-monospace, monospace;
    color: #94a3b8;
  }
  .minimap {
    position: absolute;
    right: 14px;
    bottom: 14px;
    border: 1px solid #2c2c33;
    border-radius: 8px;
    cursor: crosshair;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  }

  .source-tag { font-size: 0.8rem; font-weight: 700; }
  .source-tag.recommended { color: #94a3b8; }
  .source-tag.canonical { color: #38bdf8; }
  .source-tag.case_override { color: #fda4af; }
  .source-tag.internal { color: #fbbf24; }

  .view-toggle { display: flex; gap: 6px; }
  .view-toggle-btn {
    flex: 1;
    padding: 8px 4px;
    background: #0a0a0d;
    border: 1px solid #2c2c33;
    border-radius: 8px;
    color: #94a3b8;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.78rem;
    transition: border-color 0.12s ease, color 0.12s ease, background 0.12s ease;
  }
  .view-toggle-btn:hover { border-color: #52525b; color: #e2e8f0; }
  .view-toggle-btn.active { background: rgba(14, 165, 233, 0.12); border-color: #0ea5e9; color: #38bdf8; }
  .view-toggle-btn.internal.active { background: rgba(251, 191, 36, 0.12); border-color: #fbbf24; color: #fbbf24; }
  .view-note {
    font-size: 0.7rem;
    color: #a1a1aa;
    background: #1c1c21;
    border: 1px solid #2c2c33;
    border-radius: 6px;
    padding: 6px 8px;
    line-height: 1.45;
  }
  .int-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #fbbf24;
    flex-shrink: 0;
  }
  .asset-tag { font-size: 0.85rem; color: #e2e8f0; display: flex; align-items: center; gap: 6px; }

  .hint-box {
    display: flex;
    flex-direction: column;
    gap: 4px;
    background: rgba(56, 189, 248, 0.06);
    border: 1px solid rgba(56, 189, 248, 0.15);
    padding: 10px;
    border-radius: 8px;
    font-size: 0.76rem;
    color: #94a3b8;
  }
  .hint-box strong { color: #7dd3fc; font-size: 0.78rem; }

  .validations-block { margin-top: auto; display: flex; flex-direction: column; gap: 8px; }
  .ok-box {
    color: #4ade80;
    font-size: 0.8rem;
    padding: 8px 10px;
    background: rgba(74, 222, 128, 0.05);
    border-radius: 6px;
    border: 1px solid rgba(74, 222, 128, 0.12);
  }
  .warnings-panel {
    max-height: 170px;
    overflow-y: auto;
    background: rgba(244, 63, 94, 0.05);
    border: 1px solid rgba(244, 63, 94, 0.18);
    color: #fda4af;
    font-size: 0.76rem;
    padding: 8px 10px;
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .status-bar {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 5px 14px;
    background: #131316;
    border-top: 1px solid #26262b;
    font-size: 0.72rem;
    color: #94a3b8;
    min-height: 26px;
    white-space: nowrap;
    overflow: hidden;
  }
  .sb-tool { color: #7dd3fc; font-weight: 600; flex-shrink: 0; }
  .sb-view { flex-shrink: 0; color: #94a3b8; font-weight: 600; }
  .sb-view.internal { color: #fbbf24; }
  .sb-hint { overflow: hidden; text-overflow: ellipsis; opacity: 0.75; flex: 1; min-width: 0; }
  .sb-right { display: flex; gap: 14px; flex-shrink: 0; }
  .mono { font-family: ui-monospace, monospace; color: #e2e8f0; }

  .mse-modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }
  .modal-content {
    background: #131316;
    border: 1px solid #2c2c33;
    padding: 22px;
    border-radius: 12px;
    width: 90%;
    max-width: 680px;
    max-height: 84vh;
    display: flex;
    flex-direction: column;
    gap: 14px;
    overflow-y: auto;
  }
  .modal-content textarea {
    width: 100%;
    height: 320px;
    background: #0a0a0d;
    border: 1px solid #2c2c33;
    color: #e2e8f0;
    font-family: ui-monospace, monospace;
    padding: 12px;
    font-size: 0.8rem;
    border-radius: 6px;
    outline: none;
    resize: none;
    box-sizing: border-box;
  }
  .modal-actions { display: flex; justify-content: flex-end; gap: 8px; }
  .modal-content.shortcuts { max-width: 520px; }
  .shortcuts-grid {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 8px 16px;
    font-size: 0.8rem;
    color: #cbd5e1;
    align-items: center;
  }
  .shortcuts-grid kbd {
    background: #1c1c21;
    border: 1px solid #333339;
    border-bottom-width: 2px;
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-family: ui-monospace, monospace;
    color: #7dd3fc;
    justify-self: start;
    white-space: nowrap;
  }
`;
