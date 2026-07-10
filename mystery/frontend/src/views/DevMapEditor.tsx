import React, { useEffect, useState, useMemo, useRef } from "react";
import { api } from "../api";
import { useToast } from "../components/Toast";

// --- Version 2 Schema Interfaces ---
interface LocationData {
  bounds: { x: number; y: number; w: number; h: number };
  mode: string;
  notes?: string;
}

interface ObjectAnchor {
  location_id: string;
  anchor: { x: number; y: number };
  semantic_asset_id?: string;
  render_policy?: string;
  external?: boolean;
}

interface CaseOverride {
  visible_locations: string[];
  location_bounds: Record<string, { x: number; y: number; w: number; h: number }>;
  object_anchors: Record<string, ObjectAnchor>;
}

interface TileEntry {
  x: number;
  y: number;
  tile_id: string;
}

interface TileLayer {
  tiles: TileEntry[];
}

interface PropInstance {
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

interface TownLayout {
  version: string;
  grid: { cols: number; rows: number; tile_size: number };
  canonical_locations: Record<string, LocationData>;
  case_overrides: Record<string, CaseOverride>;
  tile_layers: Record<string, TileLayer>;
  prop_instances: Record<string, PropInstance[]>;
}

interface CaseLocationRef {
  location_id: string;
  name: string;
  description: string;
  legacy_bounds: { x: number; y: number; width: number; height: number } | null;
  legacy_position: { x: number; y: number } | null;
  visual_layer: string | null;
}

interface CaseObjectRef {
  object_id: string;
  name: string;
  description: string;
  normal_location_id: string | null;
  final_location_id: string | null;
}

interface CaseRef {
  case_id: string;
  title: string;
  locations: CaseLocationRef[];
  objects: CaseObjectRef[];
}

// --- Constants & Palettes ---
const ALLOWED_TILES = [
  "tile_grass", "tile_mud", "tile_cobble", "tile_path", "tile_floor_wood",
  "tile_floor_stone", "tile_wall_exterior", "tile_wall_interior", "tile_water",
  "tile_water_edge", "tile_fence", "tile_hedge", "tile_flowerbed", "tile_tree",
  "tile_shadow_soft"
];

const ALLOWED_PROPS = [
  "prop_fountain_coping", "prop_lamp", "prop_bench", "prop_cafe_counter",
  "prop_till", "prop_mop_bucket", "prop_coat_rack", "prop_crate",
  "prop_bookshop_shelf", "prop_desk", "prop_letter_opener", "prop_broken_window",
  "prop_clinic_bed", "prop_dispensary_shelf", "prop_medicine_cabinet",
  "prop_pub_bar", "prop_pub_stool", "prop_pub_ledger", "prop_lighter",
  "prop_fireplace", "prop_cocoa_mug", "prop_books", "prop_garden_plant",
  "prop_foxglove", "prop_letters", "prop_documents", "prop_phone", "prop_key",
  "prop_belt", "prop_boots", "prop_muddy_footprint"
];

const ALLOWED_LAYERS = [
  "base", "terrain_detail", "paths", "interior_floors", "walls", "structures",
  "props", "case_overlays", "object_anchors", "evidence_markers", "fog", "debug_bounds"
];

const TILE_COLORS: Record<string, string> = {
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

const PROP_EMOJIS: Record<string, string> = {
  prop_fountain_coping: "⛲",
  prop_lamp: "💡",
  prop_bench: "🪑",
  prop_cafe_counter: "カウンター",
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

const ALLOWED_NESTING = [
  ["loc_village_square", "loc_fountain"],
  ["loc_hobbs_cafe", "loc_cafe_kitchen"],
  ["loc_hobbs_cafe", "loc_cafe_storage"],
  ["loc_bookshop", "loc_bookshop_back"],
  ["loc_clinic", "loc_clinic_dispensary"],
  ["loc_marcus_house", "loc_marcus_study"]
];

function isNestingAllowed(idA: string, idB: string): boolean {
  return ALLOWED_NESTING.some(
    ([parent, child]) => (idA === parent && idB === child) || (idB === parent && idA === child)
  );
}

export default function DevMapEditor() {
  const { showToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Raw editor state
  const [layout, setLayout] = useState<TownLayout | null>(null);
  const [cases, setCases] = useState<CaseRef[]>([]);
  const [canonicalRecs, setCanonicalRecs] = useState<Record<string, { bounds: { x: number; y: number; w: number; h: number }; mode: string }>>({});

  // Undo / Redo stacks
  const [history, setHistory] = useState<TownLayout[]>([]);
  const [redoStack, setRedoStack] = useState<TownLayout[]>([]);
  const [isDirty, setIsDirty] = useState<boolean>(false);

  // UI Tool Settings
  const [activeTool, setActiveTool] = useState<"location" | "object" | "tile" | "prop">("location");
  const [tileBrushTool, setTileBrushTool] = useState<"paint" | "erase">("paint");
  const [selectedTileId, setSelectedTileId] = useState<string>("tile_grass");
  const [selectedPropId, setSelectedPropId] = useState<string>("prop_fountain_coping");
  const [selectedLayer, setSelectedLayer] = useState<string>("props");

  // Selection States
  const [selectedCaseId, setSelectedCaseId] = useState<string>("canonical");
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null);
  const [selectedObjectId, setSelectedObjectId] = useState<string | null>(null);
  const [selectedPropInstanceId, setSelectedPropInstanceId] = useState<string | null>(null);

  // Preview Mode options
  const [previewMode, setPreviewMode] = useState<"debug" | "player_reveal" | "fog">("debug");
  const [fineAdjustment, setFineAdjustment] = useState<boolean>(false);
  const [showEvidenceAnchors, setShowEvidenceAnchors] = useState<boolean>(true);

  // Underlay settings
  const [showUnderlay, setShowUnderlay] = useState<boolean>(true);
  const [underlayOpacity, setUnderlayOpacity] = useState<number>(0.35);
  const [blankGridMode, setBlankGridMode] = useState<boolean>(false);

  // Layer Visibility settings
  const [visibleLayers, setVisibleLayers] = useState<Record<string, boolean>>(() => {
    const defaultVisible: Record<string, boolean> = {};
    ALLOWED_LAYERS.forEach(l => {
      defaultVisible[l] = true;
    });
    return defaultVisible;
  });

  // Modal Dialogs
  const [showExportModal, setShowExportModal] = useState<boolean>(false);
  const [showImportModal, setShowImportModal] = useState<boolean>(false);
  const [importText, setImportText] = useState<string>("");

  const canvasRef = useRef<HTMLDivElement>(null);
  const dragInfo = useRef<{
    type: "location" | "object" | "resize" | "prop";
    id: string;
    startX: number;
    startY: number;
    initialX: number;
    initialY: number;
    initialW?: number;
    initialH?: number;
  } | null>(null);

  // Helper resolvers
  const getLocationEffective = (locId: string) => {
    if (!layout) return null;
    let bounds = canonicalRecs[locId]?.bounds || { x: 4, y: 4, w: 6, h: 6 };
    let mode = canonicalRecs[locId]?.mode || "exterior";
    let source = "recommended";
    let isOverridden = false;

    if (layout.canonical_locations[locId]) {
      bounds = layout.canonical_locations[locId].bounds;
      mode = layout.canonical_locations[locId].mode;
      source = "canonical";
    }

    if (selectedCaseId !== "canonical" && layout.case_overrides[selectedCaseId]?.location_bounds[locId]) {
      bounds = layout.case_overrides[selectedCaseId].location_bounds[locId];
      source = "case_override";
      isOverridden = true;
    }

    return { bounds, mode, source, isOverridden };
  };

  const getObjectEffective = (objId: string) => {
    if (!layout || selectedCaseId === "canonical") return null;
    const anchorData = layout.case_overrides[selectedCaseId]?.object_anchors[objId];
    if (anchorData) {
      return {
        location_id: anchorData.location_id,
        anchor: anchorData.anchor,
        semantic_asset_id: anchorData.semantic_asset_id,
        render_policy: anchorData.render_policy,
        external: anchorData.external
      };
    }
    // Fallback search
    const activeCase = cases.find(c => c.case_id === selectedCaseId);
    const obj = activeCase?.objects.find(o => o.object_id === objId);
    if (obj) {
      const locId = obj.normal_location_id || obj.final_location_id || "loc_village_square";
      const locBounds = getLocationEffective(locId)?.bounds || { x: 10, y: 10, w: 4, h: 4 };
      return {
        location_id: locId,
        anchor: { x: Math.floor(locBounds.x + locBounds.w / 2), y: Math.floor(locBounds.y + locBounds.h / 2) },
        semantic_asset_id: "",
        render_policy: "discovery_gated",
        external: false
      };
    }
    return null;
  };

  const isLocationVisible = (locId: string) => {
    if (!layout || selectedCaseId === "canonical") return true;
    const caseOverride = layout.case_overrides[selectedCaseId];
    if (!caseOverride) return false;
    return caseOverride.visible_locations.includes(locId);
  };

  // Intercept window unload and in-app navigation when layout is unsaved
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "You have unsaved changes in the map editor. Are you sure you want to leave?";
        return e.returnValue;
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [isDirty]);

  // Load layout configurations
  useEffect(() => {
    api.getDevMapLayout()
      .then((data) => {
        // Safe structures init
        const cleanLayout = {
          ...data.layout,
          tile_layers: data.layout.tile_layers || {},
          prop_instances: data.layout.prop_instances || {}
        } as TownLayout;
        setLayout(cleanLayout);
        setCases(data.cases);
        setCanonicalRecs(data.canonical_recommended_locations);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load layout. Enable dev flags.");
        setLoading(false);
      });
  }, []);

  // Hotkey Undo/Redo & Delete listeners
  useEffect(() => {
    const handleKeys = (e: KeyboardEvent) => {
      if (document.activeElement?.tagName === "INPUT" || document.activeElement?.tagName === "TEXTAREA") {
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        e.preventDefault();
        if (e.shiftKey) {
          handleRedo();
        } else {
          handleUndo();
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key === "y") {
        e.preventDefault();
        handleRedo();
      } else if (e.key === "Delete" || e.key === "Backspace") {
        if (selectedPropInstanceId) {
          deleteSelectedPropInstance();
        }
      }
    };
    window.addEventListener("keydown", handleKeys);
    return () => {
      window.removeEventListener("keydown", handleKeys);
    };
  }, [history, redoStack, layout, selectedPropInstanceId]);

  // Active elements derived lists
  const activeLocations = useMemo<CaseLocationRef[]>(() => {
    if (selectedCaseId === "canonical") {
      const allLocs = new Map<string, CaseLocationRef>();
      cases.forEach((c) => {
        c.locations.forEach((l) => {
          allLocs.set(l.location_id, {
            location_id: l.location_id,
            name: l.name,
            description: l.description,
            legacy_bounds: l.legacy_bounds,
            legacy_position: l.legacy_position,
            visual_layer: l.visual_layer
          });
        });
      });
      return Array.from(allLocs.values());
    } else {
      const activeCase = cases.find(c => c.case_id === selectedCaseId);
      return activeCase ? activeCase.locations : [];
    }
  }, [cases, selectedCaseId]);

  const activeObjects = useMemo(() => {
    if (selectedCaseId === "canonical") return [];
    const activeCase = cases.find(c => c.case_id === selectedCaseId);
    return activeCase ? activeCase.objects : [];
  }, [cases, selectedCaseId]);

  const activeProps = useMemo(() => {
    if (!layout || !layout.prop_instances) return [];
    const canonical = layout.prop_instances["canonical"] || [];
    const caseProps = selectedCaseId !== "canonical" ? (layout.prop_instances[selectedCaseId] || []) : [];
    return [...canonical, ...caseProps];
  }, [layout, selectedCaseId]);

  // Containment and overlap validations list
  const validationWarnings = useMemo<string[]>(() => {
    const warnings: string[] = [];
    if (!layout) return warnings;

    const locPositions: Record<string, { x: number; y: number; w: number; h: number }> = {};

    activeLocations.forEach((loc) => {
      const eff = getLocationEffective(loc.location_id);
      if (eff) {
        locPositions[loc.location_id] = eff.bounds;
      }
    });

    // Check overlaps on locations with nesting bypasses
    const locIds = Object.keys(locPositions);
    for (let i = 0; i < locIds.length; i++) {
      for (let j = i + 1; j < locIds.length; j++) {
        const idA = locIds[i];
        const idB = locIds[j];
        if (isNestingAllowed(idA, idB)) continue;

        const bA = locPositions[idA];
        const bB = locPositions[idB];
        const overlap = !(
          bA.x + bA.w <= bB.x ||
          bB.x + bB.w <= bA.x ||
          bA.y + bA.h <= bB.y ||
          bB.y + bB.h <= bA.y
        );
        if (overlap) {
          warnings.push(`Overlap detected between location "${idA}" and "${idB}" without parent-child allowance.`);
        }
      }
    }

    // Check evidence anchor containment constraints
    if (selectedCaseId !== "canonical") {
      activeObjects.forEach((obj) => {
        const effObj = getObjectEffective(obj.object_id);
        if (effObj && effObj.anchor) {
          const { location_id, anchor } = effObj;
          const locBounds = locPositions[location_id];
          if (!locBounds) {
            warnings.push(`Evidence object "${obj.object_id}" anchors inside unconfigured location "${location_id}".`);
            return;
          }
          const isGated = anchor.x >= locBounds.x &&
            anchor.x < locBounds.x + locBounds.w &&
            anchor.y >= locBounds.y &&
            anchor.y < locBounds.y + locBounds.h;
          if (!isGated && anchor.x >= 0 && anchor.y >= 0) {
            warnings.push(`Evidence anchor "${obj.object_id}" is outside the bounds of location "${location_id}".`);
          }
        }
      });
    }

    // Check discovery-gated props have linked object ID
    activeProps.forEach(p => {
      if (p.render_policy === "discovery_gated" && !p.object_id) {
        warnings.push(`Prop instance "${p.instance_id}" has render policy "discovery_gated" but lacks a linked object_id.`);
      }
    });

    return warnings;
  }, [layout, selectedCaseId, activeLocations, activeObjects, activeProps]);



  // State undo/redo triggers
  const pushState = (newLayout: TownLayout) => {
    if (!layout) return;
    setHistory((prev) => [...prev, JSON.parse(JSON.stringify(layout))]);
    setRedoStack([]);
    setLayout(newLayout);
    setIsDirty(true);
  };

  const handleUndo = () => {
    if (history.length === 0 || !layout) return;
    const prev = history[history.length - 1];
    setRedoStack((r) => [...r, layout]);
    setLayout(prev);
    setHistory((h) => h.slice(0, -1));
    setIsDirty(true);
    showToast("Undo completed", "success");
  };

  const handleRedo = () => {
    if (redoStack.length === 0 || !layout) return;
    const next = redoStack[redoStack.length - 1];
    setHistory((h) => [...h, layout]);
    setLayout(next);
    setRedoStack((r) => r.slice(0, -1));
    setIsDirty(true);
    showToast("Redo completed", "success");
  };

  // Canvas Interactions
  const handleCanvasPointerDown = (e: React.PointerEvent) => {
    if (activeTool !== "tile" && activeTool !== "prop") return;
    e.preventDefault();
    if (!canvasRef.current || !layout) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const getGridCoords = (clientX: number, clientY: number) => {
      const tx = Math.floor(((clientX - rect.left) / rect.width) * 64);
      const ty = Math.floor(((clientY - rect.top) / rect.height) * 48);
      return {
        x: Math.max(0, Math.min(63, tx)),
        y: Math.max(0, Math.min(47, ty))
      };
    };

    const startCoords = getGridCoords(e.clientX, e.clientY);
    const preEdit = JSON.parse(JSON.stringify(layout)) as TownLayout;

    if (activeTool === "tile") {
      const performPaint = (gx: number, gy: number) => {
        setLayout((prev) => {
          if (!prev) return null;
          const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
          if (!copy.tile_layers) copy.tile_layers = {};
          if (!copy.tile_layers[selectedLayer]) {
            copy.tile_layers[selectedLayer] = { tiles: [] };
          }
          
          copy.tile_layers[selectedLayer].tiles = copy.tile_layers[selectedLayer].tiles.filter(
            (t) => !(t.x === gx && t.y === gy)
          );

          if (tileBrushTool === "paint") {
            copy.tile_layers[selectedLayer].tiles.push({
              x: gx,
              y: gy,
              tile_id: selectedTileId
            });
          }
          return copy;
        });
        setIsDirty(true);
      };

      performPaint(startCoords.x, startCoords.y);

      const handlePointerMove = (moveEvent: PointerEvent) => {
        const coords = getGridCoords(moveEvent.clientX, moveEvent.clientY);
        performPaint(coords.x, coords.y);
      };

      const handlePointerUp = () => {
        setHistory((prev) => [...prev, preEdit]);
        setRedoStack([]);
        window.removeEventListener("pointermove", handlePointerMove);
        window.removeEventListener("pointerup", handlePointerUp);
      };

      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("pointerup", handlePointerUp);
    } else if (activeTool === "prop") {
      const locAtCoords = activeLocations.find((loc) => {
        const eff = getLocationEffective(loc.location_id);
        if (!eff) return false;
        const { x, y, w, h } = eff.bounds;
        return startCoords.x >= x && startCoords.x < x + w && startCoords.y >= y && startCoords.y < y + h;
      });

      const locationId = locAtCoords ? locAtCoords.location_id : "loc_village_square";

      const newProp: PropInstance = {
        instance_id: `prop_${selectedPropId}_${Date.now().toString().slice(-6)}`,
        asset_id: selectedPropId,
        location_id: locationId,
        x: startCoords.x,
        y: startCoords.y,
        layer: selectedLayer,
        render_policy: "always_visible"
      };

      setLayout((prev) => {
        if (!prev) return null;
        const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
        if (!copy.prop_instances) copy.prop_instances = {};
        const scope = selectedCaseId;
        if (!copy.prop_instances[scope]) {
          copy.prop_instances[scope] = [];
        }
        copy.prop_instances[scope].push(newProp);
        return copy;
      });

      setIsDirty(true);
      setHistory((prev) => [...prev, preEdit]);
      setRedoStack([]);

      setSelectedPropInstanceId(newProp.instance_id);
      dragInfo.current = {
        type: "prop",
        id: newProp.instance_id,
        startX: e.clientX,
        startY: e.clientY,
        initialX: newProp.x,
        initialY: newProp.y
      };

      const handlePointerMove = (moveEvent: PointerEvent) => {
        if (!dragInfo.current) return;
        const deltaX_px = moveEvent.clientX - dragInfo.current.startX;
        const deltaY_px = moveEvent.clientY - dragInfo.current.startY;
        
        let deltaX_tiles = Math.round(deltaX_px * (64 / rect.width));
        let deltaY_tiles = Math.round(deltaY_px * (48 / rect.height));

        const newX = Math.max(0, Math.min(63, dragInfo.current.initialX + deltaX_tiles));
        const newY = Math.max(0, Math.min(47, dragInfo.current.initialY + deltaY_tiles));

        setLayout((prev) => {
          if (!prev) return null;
          const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
          const scope = selectedCaseId;
          if (copy.prop_instances[scope]) {
            const idx = copy.prop_instances[scope].findIndex(p => p.instance_id === newProp.instance_id);
            if (idx !== -1) {
              copy.prop_instances[scope][idx].x = newX;
              copy.prop_instances[scope][idx].y = newY;
            }
          }
          return copy;
        });
      };

      const handlePointerUp = () => {
        dragInfo.current = null;
        window.removeEventListener("pointermove", handlePointerMove);
        window.removeEventListener("pointerup", handlePointerUp);
      };

      window.addEventListener("pointermove", handlePointerMove);
      window.addEventListener("pointerup", handlePointerUp);
    }
  };

  const handlePointerDown = (
    e: React.PointerEvent,
    type: "location" | "object" | "resize",
    id: string
  ) => {
    e.stopPropagation();
    e.preventDefault();
    if (!canvasRef.current || !layout) return;

    const preDrag = JSON.parse(JSON.stringify(layout)) as TownLayout;

    if (type === "location") {
      setSelectedLocationId(id);
      setSelectedObjectId(null);
      setSelectedPropInstanceId(null);
      const eff = getLocationEffective(id);
      if (eff) {
        dragInfo.current = {
          type,
          id,
          startX: e.clientX,
          startY: e.clientY,
          initialX: eff.bounds.x,
          initialY: eff.bounds.y
        };
      }
    } else if (type === "resize") {
      setSelectedLocationId(id);
      setSelectedObjectId(null);
      setSelectedPropInstanceId(null);
      const eff = getLocationEffective(id);
      if (eff) {
        dragInfo.current = {
          type,
          id,
          startX: e.clientX,
          startY: e.clientY,
          initialX: eff.bounds.x,
          initialY: eff.bounds.y,
          initialW: eff.bounds.w,
          initialH: eff.bounds.h
        };
      }
    } else if (type === "object") {
      setSelectedObjectId(id);
      setSelectedLocationId(null);
      setSelectedPropInstanceId(null);
      const eff = getObjectEffective(id);
      if (eff && eff.anchor) {
        dragInfo.current = {
          type,
          id,
          startX: e.clientX,
          startY: e.clientY,
          initialX: eff.anchor.x,
          initialY: eff.anchor.y
        };
      }
    }

    const handlePointerMove = (moveEvent: PointerEvent) => {
      if (!dragInfo.current || !canvasRef.current || !layout) return;
      const drag = dragInfo.current;
      const rect = canvasRef.current.getBoundingClientRect();
      const scaleX = 64 / rect.width;
      const scaleY = 48 / rect.height;

      const deltaX_px = moveEvent.clientX - drag.startX;
      const deltaY_px = moveEvent.clientY - drag.startY;

      let deltaX_tiles = deltaX_px * scaleX;
      let deltaY_tiles = deltaY_px * scaleY;

      if (!fineAdjustment) {
        deltaX_tiles = Math.round(deltaX_tiles);
        deltaY_tiles = Math.round(deltaY_tiles);
      } else {
        deltaX_tiles = Math.round(deltaX_tiles * 2) / 2;
        deltaY_tiles = Math.round(deltaY_tiles * 2) / 2;
      }

      if (drag.type === "location") {
        const newX = Math.max(0, Math.min(64 - 1, drag.initialX + deltaX_tiles));
        const newY = Math.max(0, Math.min(48 - 1, drag.initialY + deltaY_tiles));
        updateLocationBounds(drag.id, { x: newX, y: newY });
      } else if (drag.type === "resize") {
        if (drag.initialW && drag.initialH) {
          const newW = Math.max(1, Math.min(64 - drag.initialX, drag.initialW + deltaX_tiles));
          const newH = Math.max(1, Math.min(48 - drag.initialY, drag.initialH + deltaY_tiles));
          updateLocationBounds(drag.id, { w: newW, h: newH });
        }
      } else if (drag.type === "object") {
        const newX = Math.max(0, Math.min(64 - 1, drag.initialX + deltaX_tiles));
        const newY = Math.max(0, Math.min(48 - 1, drag.initialY + deltaY_tiles));
        updateObjectAnchor(drag.id, { x: newX, y: newY });
      }
    };

    const handlePointerUp = () => {
      dragInfo.current = null;
      setHistory((prev) => [...prev, preDrag]);
      setRedoStack([]);
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
  };

  // State mutations
  const updateLocationBounds = (locId: string, updates: { x?: number; y?: number; w?: number; h?: number }) => {
    if (!layout) return;
    setLayout((prev) => {
      if (!prev) return null;
      const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
      if (selectedCaseId === "canonical") {
        if (!copy.canonical_locations[locId]) {
          copy.canonical_locations[locId] = { bounds: { x: 0, y: 0, w: 4, h: 4 }, mode: "exterior" };
        }
        copy.canonical_locations[locId].bounds = {
          ...copy.canonical_locations[locId].bounds,
          ...updates
        };
      } else {
        if (!copy.case_overrides[selectedCaseId]) {
          copy.case_overrides[selectedCaseId] = { visible_locations: [], location_bounds: {}, object_anchors: {} };
        }
        const bounds = getLocationEffective(locId)?.bounds || { x: 0, y: 0, w: 4, h: 4 };
        copy.case_overrides[selectedCaseId].location_bounds[locId] = {
          ...bounds,
          ...updates
        };
      }
      return copy;
    });
    setIsDirty(true);
  };

  const updateObjectAnchor = (objId: string, updates: { x?: number; y?: number }) => {
    if (!layout || selectedCaseId === "canonical") return;
    setLayout((prev) => {
      if (!prev) return null;
      const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
      if (!copy.case_overrides[selectedCaseId]) {
        copy.case_overrides[selectedCaseId] = { visible_locations: [], location_bounds: {}, object_anchors: {} };
      }
      const existing = getObjectEffective(objId);
      const locId = existing?.location_id || "loc_village_square";
      const renderPolicy = existing?.render_policy || "discovery_gated";
      const semAsset = existing?.semantic_asset_id || "";
      const isExt = existing?.external || false;
      const anchor = existing?.anchor || { x: 0, y: 0 };

      copy.case_overrides[selectedCaseId].object_anchors[objId] = {
        location_id: locId,
        anchor: { ...anchor, ...updates },
        semantic_asset_id: semAsset,
        render_policy: renderPolicy,
        external: isExt
      };
      return copy;
    });
    setIsDirty(true);
  };

  const toggleLocationVisibility = (locId: string) => {
    if (!layout || selectedCaseId === "canonical") return;
    const preEdit = JSON.parse(JSON.stringify(layout)) as TownLayout;
    setLayout((prev) => {
      if (!prev) return null;
      const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
      if (!copy.case_overrides[selectedCaseId]) {
        copy.case_overrides[selectedCaseId] = { visible_locations: [], location_bounds: {}, object_anchors: {} };
      }
      const list = copy.case_overrides[selectedCaseId].visible_locations;
      if (list.includes(locId)) {
        copy.case_overrides[selectedCaseId].visible_locations = list.filter(id => id !== locId);
      } else {
        copy.case_overrides[selectedCaseId].visible_locations = [...list, locId];
      }
      return copy;
    });
    setIsDirty(true);
    setHistory((prev) => [...prev, preEdit]);
    setRedoStack([]);
  };

  const deleteSelectedPropInstance = () => {
    if (!selectedPropInstanceId || !layout) return;
    const preEdit = JSON.parse(JSON.stringify(layout)) as TownLayout;
    setLayout((prev) => {
      if (!prev) return null;
      const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
      for (const scope of Object.keys(copy.prop_instances || {})) {
        copy.prop_instances[scope] = copy.prop_instances[scope].filter(
          p => p.instance_id !== selectedPropInstanceId
        );
      }
      return copy;
    });
    setSelectedPropInstanceId(null);
    setIsDirty(true);
    setHistory((prev) => [...prev, preEdit]);
    setRedoStack([]);
    showToast("Prop instance deleted", "success");
  };

  const promoteToCanonical = () => {
    if (!layout || selectedCaseId === "canonical" || !selectedLocationId) return;
    const preEdit = JSON.parse(JSON.stringify(layout)) as TownLayout;
    const eff = getLocationEffective(selectedLocationId);
    if (!eff) return;

    setLayout((prev) => {
      if (!prev) return null;
      const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
      if (!copy.canonical_locations[selectedLocationId]) {
        copy.canonical_locations[selectedLocationId] = { bounds: eff.bounds, mode: eff.mode };
      } else {
        copy.canonical_locations[selectedLocationId].bounds = eff.bounds;
      }
      if (copy.case_overrides[selectedCaseId]?.location_bounds[selectedLocationId]) {
        delete copy.case_overrides[selectedCaseId].location_bounds[selectedLocationId];
      }
      return copy;
    });
    setIsDirty(true);
    setHistory((prev) => [...prev, preEdit]);
    setRedoStack([]);
    showToast(`Promoted bounds of '${selectedLocationId}' to canonical town template.`, "success");
  };

  // Reset helpers
  const resetToCanonicalRec = () => {
    if (!selectedLocationId || !layout) return;
    const rec = canonicalRecs[selectedLocationId];
    if (rec) {
      const preEdit = JSON.parse(JSON.stringify(layout)) as TownLayout;
      updateLocationBounds(selectedLocationId, rec.bounds);
      setHistory((prev) => [...prev, preEdit]);
      setRedoStack([]);
      showToast("Reset to recommended layout bounds", "info");
    }
  };

  const resetToLegacyFallback = () => {
    if (!selectedLocationId || !layout) return;
    const loc = activeLocations.find(l => l.location_id === selectedLocationId);
    if (loc && loc.legacy_bounds) {
      const preEdit = JSON.parse(JSON.stringify(layout)) as TownLayout;
      updateLocationBounds(selectedLocationId, {
        x: loc.legacy_bounds.x / 32,
        y: loc.legacy_bounds.y / 32,
        w: loc.legacy_bounds.width / 32,
        h: loc.legacy_bounds.height / 32
      });
      setHistory((prev) => [...prev, preEdit]);
      setRedoStack([]);
      showToast("Reset to legacy contract bounds", "info");
    }
  };

  // Persistent server operations
  const handleSave = () => {
    if (!layout) return;
    if (validationWarnings.length > 0) {
      showToast(`Cannot save: validation warnings are present.`, "error");
      return;
    }

    api.saveDevMapLayout(layout)
      .then(() => {
        setIsDirty(false);
        showToast("Layout saved atomically with backup created.", "success");
      })
      .catch((err) => {
        showToast(`Save failed: ${err.message}`, "error");
      });
  };

  const handleImportTextSubmit = () => {
    try {
      const parsed = JSON.parse(importText) as TownLayout;
      if (parsed.version !== "town_layout_editor_v2") {
        showToast("Import failed: Version must be town_layout_editor_v2", "error");
        return;
      }
      if (!parsed.grid || parsed.grid.cols !== 64 || parsed.grid.rows !== 48) {
        showToast("Import failed: Grid size must be 64x48", "error");
        return;
      }

      pushState({
        ...parsed,
        tile_layers: parsed.tile_layers || {},
        prop_instances: parsed.prop_instances || {}
      });

      setShowImportModal(false);
      showToast("JSON layout imported successfully. Review grid changes and click Save.", "success");
    } catch (e: any) {
      showToast(`JSON syntax error: ${e.message}`, "error");
    }
  };

  const handleExit = () => {
    if (isDirty) {
      if (!window.confirm("You have unsaved layout modifications. Exit anyway?")) {
        return;
      }
    }
    window.location.hash = "#/";
  };

  const renderGridLines = () => {
    const lines = [];
    for (let i = 1; i < 64; i++) {
      lines.push(
        <div
          key={`v-${i}`}
          style={{
            position: "absolute",
            left: `${(i / 64) * 100}%`,
            top: 0,
            bottom: 0,
            width: "1px",
            background: "rgba(255, 255, 255, 0.05)",
            pointerEvents: "none"
          }}
        />
      );
    }
    for (let i = 1; i < 48; i++) {
      lines.push(
        <div
          key={`h-${i}`}
          style={{
            position: "absolute",
            top: `${(i / 48) * 100}%`,
            left: 0,
            right: 0,
            height: "1px",
            background: "rgba(255, 255, 255, 0.05)",
            pointerEvents: "none"
          }}
        />
      );
    }
    return lines;
  };

  if (loading) {
    return <div className="dev-map-loading">Loading Developer Map Workspace...</div>;
  }

  if (error || !layout) {
    return (
      <div className="dev-map-error">
        <h3>Developer Environment Error</h3>
        <p>{error || "Layout configuration not parsed."}</p>
        <button className="btn btn-primary" onClick={() => window.location.reload()}>Retry Connection</button>
      </div>
    );
  }

  return (
    <div className="dev-map-root">
      <style>{`
        .dev-map-root {
          display: flex;
          flex-direction: column;
          height: 100vh;
          width: 100vw;
          background: #09090b;
          color: #e2e8f0;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          overflow: hidden;
        }
        .dev-map-loading, .dev-map-error {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100vh;
          width: 100vw;
          background: #09090b;
          color: #e2e8f0;
        }
        .dev-map-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 24px;
          background: #18181b;
          border-bottom: 1px solid #27272a;
          z-index: 10;
        }
        .header-title-section {
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .header-title-section h2 {
          font-size: 1.1rem;
          margin: 0;
          font-weight: 700;
          color: #fff;
        }
        .dirty-badge {
          background: rgba(234, 179, 8, 0.15);
          color: #eab308;
          border: 1px solid rgba(234, 179, 8, 0.3);
          padding: 2px 8px;
          border-radius: 9999px;
          font-size: 0.75rem;
          font-weight: 600;
        }
        .actions-group {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .btn {
          padding: 8px 14px;
          border-radius: 6px;
          font-size: 0.85rem;
          font-weight: 600;
          border: none;
          cursor: pointer;
          transition: all 0.15s ease;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
        .btn-primary {
          background: #0ea5e9;
          color: #fff;
        }
        .btn-primary:hover {
          background: #0284c7;
        }
        .btn-secondary {
          background: #27272a;
          color: #e2e8f0;
          border: 1px solid #3f3f46;
        }
        .btn-secondary:hover {
          background: #3f3f46;
        }
        .btn-danger {
          background: #be123c;
          color: #fff;
        }
        .btn-danger:hover {
          background: #9f1239;
        }
        .main-editor-layout {
          display: flex;
          flex: 1;
          overflow: hidden;
          position: relative;
        }
        .left-sidebar {
          width: 320px;
          background: #18181b;
          border-right: 1px solid #27272a;
          display: flex;
          flex-direction: column;
          overflow-y: auto;
          padding: 20px;
          gap: 20px;
        }
        .properties-panel {
          width: 340px;
          background: #18181b;
          border-left: 1px solid #27272a;
          display: flex;
          flex-direction: column;
          overflow-y: auto;
          padding: 20px;
          gap: 20px;
        }
        .section-title {
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: #38bdf8;
          margin-bottom: 8px;
          font-weight: 700;
        }
        .control-group {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .control-group label {
          font-size: 0.75rem;
          color: #94a3b8;
        }
        .control-group select, .control-group input, .control-group textarea {
          background: #09090b;
          border: 1px solid #27272a;
          color: #e2e8f0;
          padding: 8px 12px;
          border-radius: 6px;
          font-size: 0.85rem;
          outline: none;
        }
        .control-group select:focus, .control-group input:focus {
          border-color: #38bdf8;
        }
        .tool-bar-selector {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
        }
        .tool-btn {
          padding: 10px;
          background: #09090b;
          border: 1px solid #27272a;
          border-radius: 6px;
          color: #94a3b8;
          cursor: pointer;
          font-weight: 600;
          font-size: 0.8rem;
          text-align: center;
          transition: all 0.15s ease;
        }
        .tool-btn.active {
          background: rgba(14, 165, 233, 0.1);
          border-color: #0ea5e9;
          color: #0ea5e9;
        }
        .palette-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 6px;
          max-height: 180px;
          overflow-y: auto;
          background: #09090b;
          padding: 8px;
          border-radius: 6px;
          border: 1px solid #27272a;
          align-items: start;
        }
        .palette-item {
          aspect-ratio: 1 / 1;
          width: 100%;
          border-radius: 4px;
          border: 1px solid #27272a;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          transition: all 0.15s ease;
          overflow: hidden;
          position: relative;
          min-height: 54px;
        }
        .palette-item:hover {
          transform: scale(1.05);
          border-color: #fff;
        }
        .palette-item.active {
          border-color: #38bdf8;
          box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.4);
        }
        .palette-item-text {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          background: rgba(0, 0, 0, 0.65);
          font-size: 7px;
          text-align: center;
          white-space: nowrap;
          overflow: hidden;
          padding: 1px 0;
        }
        .layer-list {
          display: flex;
          flex-direction: column;
          gap: 4px;
          background: #09090b;
          padding: 8px;
          border-radius: 6px;
          border: 1px solid #27272a;
          max-height: 150px;
          overflow-y: auto;
        }
        .layer-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          font-size: 0.75rem;
          color: #94a3b8;
          padding: 2px 4px;
        }
        .editor-workspace {
          flex: 1;
          display: flex;
          padding: 20px;
          overflow: auto;
          align-items: center;
          justify-content: center;
          background: #09090b;
        }
        .canvas-container {
          position: relative;
          background: #111113;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
          border: 2px solid #27272a;
          border-radius: 8px;
          overflow: hidden;
          user-select: none;
        }
        .canvas-bg-art {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background-size: cover;
          pointer-events: none;
          z-index: 1;
        }
        .canvas-safety-margin {
          position: absolute;
          left: 6.25%;
          top: 8.33%;
          right: 6.25%;
          bottom: 8.33%;
          border: 2px dashed rgba(244, 63, 94, 0.25);
          pointer-events: none;
          display: flex;
          align-items: flex-start;
          justify-content: flex-start;
          padding: 8px;
          color: rgba(244, 63, 94, 0.4);
          font-size: 9px;
          font-family: monospace;
          z-index: 10;
        }
        .location-block {
          position: absolute;
          border-style: solid;
          box-sizing: border-box;
          cursor: move;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          z-index: 8;
          transition: border-width 0.1s;
        }
        .location-block:hover {
          filter: brightness(1.1);
        }
        .location-block.selected {
          box-shadow: 0 0 0 2px #fff;
        }
        .location-block .label {
          font-size: 11px;
          font-weight: 700;
          color: #fff;
          text-shadow: 0 2px 4px rgba(0, 0, 0, 0.8);
          text-align: center;
          padding: 4px;
        }
        .resize-handle {
          position: absolute;
          width: 14px;
          height: 14px;
          background: #fff;
          border: 2px solid #000;
          bottom: -7px;
          right: -7px;
          cursor: se-resize;
          border-radius: 50%;
          z-index: 10;
        }
        .object-anchor-dot {
          position: absolute;
          width: 16px;
          height: 16px;
          border-radius: 50%;
          background: #ef4444;
          border: 2px solid #fff;
          transform: translate(-50%, -50%);
          cursor: move;
          z-index: 9;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.5);
        }
        .object-anchor-dot.selected {
          background: #38bdf8;
          box-shadow: 0 0 0 3px #fff;
        }
        .warnings-panel {
          max-height: 160px;
          overflow-y: auto;
          background: rgba(244, 63, 94, 0.05);
          border: 1px solid rgba(244, 63, 94, 0.15);
          color: #fda4af;
          font-size: 0.8rem;
          padding: 8px;
          border-radius: 6px;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.85);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 100;
        }
        .modal-content {
          background: #18181b;
          border: 1px solid #27272a;
          padding: 24px;
          border-radius: 12px;
          width: 90%;
          max-width: 680px;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .modal-content textarea {
          width: 100%;
          height: 320px;
          background: #09090b;
          border: 1px solid #27272a;
          color: #e2e8f0;
          font-family: monospace;
          padding: 12px;
          font-size: 0.85rem;
          border-radius: 6px;
          outline: none;
          resize: none;
        }
      `}</style>

      {/* Header Panel */}
      <header className="dev-map-header">
        <div className="header-title-section">
          <h2>Map Layout Builder</h2>
          {isDirty && <span className="dirty-badge">Unsaved changes</span>}
          <div className="actions-group">
            <button className="btn btn-secondary" onClick={handleUndo} disabled={history.length === 0}>
              ↩ Undo
            </button>
            <button className="btn btn-secondary" onClick={handleRedo} disabled={redoStack.length === 0}>
              ↪ Redo
            </button>
          </div>
        </div>
        <div className="actions-group">
          <button className="btn btn-secondary" onClick={() => setShowImportModal(true)}>
            📥 Import JSON
          </button>
          <button className="btn btn-secondary" onClick={() => setShowExportModal(true)}>
            📤 Export JSON
          </button>
          <button className="btn btn-primary" onClick={handleSave}>
            💾 Save Layout
          </button>
          <button className="btn btn-danger" onClick={handleExit}>
            🚪 Exit to Game
          </button>
        </div>
      </header>

      {/* Main Grid View */}
      <div className="main-editor-layout">
        {/* Left Toolbar panel */}
        <aside className="left-sidebar">
          {/* Editor Target Context */}
          <div className="control-group">
            <label className="section-title">Target Scope</label>
            <select value={selectedCaseId} onChange={(e) => {
              setSelectedCaseId(e.target.value);
              setSelectedLocationId(null);
              setSelectedObjectId(null);
              setSelectedPropInstanceId(null);
            }}>
              <option value="canonical">Canonical Town Template</option>
              {cases.map((c) => (
                <option key={c.case_id} value={c.case_id}>{c.case_id.toUpperCase()} - {c.title}</option>
              ))}
            </select>
          </div>

          {/* Tool Modes Selector */}
          <div className="control-group">
            <label className="section-title">Active Tool Mode</label>
            <div className="tool-bar-selector">
              <button 
                className={`tool-btn ${activeTool === "location" ? "active" : ""}`}
                onClick={() => {
                  setActiveTool("location");
                  setSelectedPropInstanceId(null);
                  setSelectedObjectId(null);
                }}
              >
                🗺 Location
              </button>
              <button 
                className={`tool-btn ${activeTool === "object" ? "active" : ""}`}
                onClick={() => {
                  setActiveTool("object");
                  setSelectedLocationId(null);
                  setSelectedPropInstanceId(null);
                }}
                disabled={selectedCaseId === "canonical"}
              >
                📍 Anchor
              </button>
              <button 
                className={`tool-btn ${activeTool === "tile" ? "active" : ""}`}
                onClick={() => {
                  setActiveTool("tile");
                  setSelectedLocationId(null);
                  setSelectedObjectId(null);
                  setSelectedPropInstanceId(null);
                }}
              >
                🖌 Tile Paint
              </button>
              <button 
                className={`tool-btn ${activeTool === "prop" ? "active" : ""}`}
                onClick={() => {
                  setActiveTool("prop");
                  setSelectedLocationId(null);
                  setSelectedObjectId(null);
                }}
              >
                🌳 Props / Assets
              </button>
            </div>
          </div>

          {/* Underlay Opacity & View Toggles */}
          <div className="control-group">
            <label className="section-title">Underlay Settings</label>
            <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", fontSize: "0.8rem", color: "#94a3b8" }}>
              <input type="checkbox" checked={blankGridMode} onChange={(e) => setBlankGridMode(e.target.checked)} />
              Blank Neutral Grid Mode
            </label>
            {!blankGridMode && (
              <>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", fontSize: "0.8rem", color: "#94a3b8", marginTop: "4px" }}>
                  <input type="checkbox" checked={showUnderlay} onChange={(e) => setShowUnderlay(e.target.checked)} />
                  Show Background Underlay (Temp Reference)
                </label>
                <div style={{ display: "flex", flexDirection: "column", gap: "2px", marginTop: "6px" }}>
                  <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Underlay Opacity: {Math.round(underlayOpacity * 100)}%</span>
                  <input 
                    type="range" 
                    min="0" 
                    max="1" 
                    step="0.05" 
                    value={underlayOpacity} 
                    onChange={(e) => setUnderlayOpacity(parseFloat(e.target.value))} 
                  />
                </div>
              </>
            )}
          </div>

          {/* Layer Visibility Settings */}
          <div className="control-group">
            <label className="section-title">Layer Ordering Visibility</label>
            <div className="layer-list">
              {ALLOWED_LAYERS.map(l => (
                <label key={l} className="layer-item">
                  <span>{l}</span>
                  <input 
                    type="checkbox" 
                    checked={visibleLayers[l]} 
                    onChange={() => {
                      setVisibleLayers(prev => ({ ...prev, [l]: !prev[l] }));
                    }} 
                  />
                </label>
              ))}
            </div>
          </div>

          {/* Paint Mode Palette Panel */}
          {activeTool === "tile" && (
            <div className="control-group">
              <label className="section-title">Tile Palette</label>
              <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
                <button 
                  className={`tool-btn ${tileBrushTool === "paint" ? "active" : ""}`}
                  style={{ flex: 1 }}
                  onClick={() => setTileBrushTool("paint")}
                >
                  🖌 Paint
                </button>
                <button 
                  className={`tool-btn ${tileBrushTool === "erase" ? "active" : ""}`}
                  style={{ flex: 1 }}
                  onClick={() => setTileBrushTool("erase")}
                >
                  🧽 Eraser
                </button>
              </div>
              <div className="control-group" style={{ marginBottom: "6px" }}>
                <label>Target Layer</label>
                <select value={selectedLayer} onChange={(e) => setSelectedLayer(e.target.value)}>
                  {ALLOWED_LAYERS.map(l => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </div>
              {tileBrushTool === "paint" && (
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

          {/* Prop Placement Palette Panel */}
          {activeTool === "prop" && (
            <div className="control-group">
              <label className="section-title">Asset Prop Palette</label>
              <div className="control-group" style={{ marginBottom: "6px" }}>
                <label>Target Layer</label>
                <select value={selectedLayer} onChange={(e) => setSelectedLayer(e.target.value)}>
                  {ALLOWED_LAYERS.map(l => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </div>
              <div className="palette-grid">
                {ALLOWED_PROPS.map((pId) => (
                  <div 
                    key={pId} 
                    className={`palette-item ${selectedPropId === pId ? "active" : ""}`}
                    style={{ backgroundColor: "#27272a" }}
                    onClick={() => setSelectedPropId(pId)}
                    title={pId}
                  >
                    <span style={{ fontSize: "14px" }}>{PROP_EMOJIS[pId] || "📦"}</span>
                    <span className="palette-item-text">{pId.replace("prop_", "")}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* Workspace Canvas Area */}
        <main className="editor-workspace">
          <div 
            className="canvas-container" 
            ref={canvasRef}
            style={{
              width: "100%",
              maxWidth: "960px",
              aspectRatio: "64 / 48",
            }}
            onPointerDown={handleCanvasPointerDown}
          >
            {/* Grid Line Lines */}
            {renderGridLines()}

            {/* Background Daylight Art */}
            <div 
              className="canvas-bg-art" 
              style={{
                backgroundImage: `url("/art/case_004/fountain_daylight_map.png")`,
                opacity: !blankGridMode && showUnderlay ? underlayOpacity : 0,
                display: !blankGridMode && showUnderlay ? "block" : "none"
              }}
            />

            {/* Outer margin lines */}
            <div className="canvas-safety-margin">
              OUTER PLAYABLE BOUNDARY PERIMETER
            </div>

            {/* Sparse Painted Tiles */}
            {Object.entries(layout.tile_layers || {}).map(([layerName, layerData]) => {
              if (!visibleLayers[layerName]) return null;
              return layerData.tiles.map((tile, idx) => (
                <div
                  key={`${layerName}-${tile.x}-${tile.y}-${idx}`}
                  style={{
                    position: "absolute",
                    left: `${(tile.x / 64) * 100}%`,
                    top: `${(tile.y / 48) * 100}%`,
                    width: `${(1 / 64) * 100}%`,
                    height: `${(1 / 48) * 100}%`,
                    backgroundColor: TILE_COLORS[tile.tile_id] || "#ccc",
                    border: "1px solid rgba(255, 255, 255, 0.05)",
                    zIndex: ALLOWED_LAYERS.indexOf(layerName) + 2,
                    pointerEvents: "none"
                  }}
                />
              ));
            })}

            {/* Placed Prop Instances */}
            {activeProps.map((prop) => {
              const layerVal = prop.layer || "props";
              if (!visibleLayers[layerVal]) return null;
              const isSelected = selectedPropInstanceId === prop.instance_id;
              
              return (
                <div
                  key={prop.instance_id}
                  style={{
                    position: "absolute",
                    left: `${(prop.x / 64) * 100}%`,
                    top: `${(prop.y / 48) * 100}%`,
                    width: `${((prop.w || 1) / 64) * 100}%`,
                    height: `${((prop.h || 1) / 48) * 100}%`,
                    backgroundColor: isSelected ? "rgba(56, 189, 248, 0.6)" : "rgba(245, 158, 11, 0.45)",
                    border: isSelected ? "2px solid #0ea5e9" : "1px solid #f59e0b",
                    color: "#fff",
                    fontSize: "8px",
                    fontWeight: "bold",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "move",
                    zIndex: ALLOWED_LAYERS.indexOf(layerVal) + 2
                  }}
                  onPointerDown={(e) => {
                    e.stopPropagation();
                    setSelectedPropInstanceId(prop.instance_id);
                    setSelectedLocationId(null);
                    setSelectedObjectId(null);

                    if (!canvasRef.current || !layout) return;
                    const preDrag = JSON.parse(JSON.stringify(layout)) as TownLayout;
                    const rect = canvasRef.current.getBoundingClientRect();

                    dragInfo.current = {
                      type: "prop",
                      id: prop.instance_id,
                      startX: e.clientX,
                      startY: e.clientY,
                      initialX: prop.x,
                      initialY: prop.y
                    };

                    const handlePointerMove = (moveEvent: PointerEvent) => {
                      if (!dragInfo.current) return;
                      const deltaX_px = moveEvent.clientX - dragInfo.current.startX;
                      const deltaY_px = moveEvent.clientY - dragInfo.current.startY;
                      let deltaX_tiles = Math.round(deltaX_px * (64 / rect.width));
                      let deltaY_tiles = Math.round(deltaY_px * (48 / rect.height));

                      const newX = Math.max(0, Math.min(63, dragInfo.current.initialX + deltaX_tiles));
                      const newY = Math.max(0, Math.min(47, dragInfo.current.initialY + deltaY_tiles));

                      setLayout((prev) => {
                        if (!prev) return null;
                        const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
                        for (const scope of Object.keys(copy.prop_instances || {})) {
                          const idx = copy.prop_instances[scope].findIndex(p => p.instance_id === prop.instance_id);
                          if (idx !== -1) {
                            copy.prop_instances[scope][idx].x = newX;
                            copy.prop_instances[scope][idx].y = newY;
                            break;
                          }
                        }
                        return copy;
                      });
                      setIsDirty(true);
                    };

                    const handlePointerUp = () => {
                      dragInfo.current = null;
                      setHistory((prev) => [...prev, preDrag]);
                      setRedoStack([]);
                      window.removeEventListener("pointermove", handlePointerMove);
                      window.removeEventListener("pointerup", handlePointerUp);
                    };

                    window.addEventListener("pointermove", handlePointerMove);
                    window.addEventListener("pointerup", handlePointerUp);
                  }}
                >
                  <span style={{ fontSize: "14px", whiteSpace: "nowrap" }} title={prop.asset_id}>
                    {PROP_EMOJIS[prop.asset_id] || "📦"}
                  </span>
                </div>
              );
            })}

            {/* Locations */}
            {visibleLayers["debug_bounds"] && activeLocations.map((loc) => {
              const eff = getLocationEffective(loc.location_id);
              if (!eff) return null;

              const isVisible = isLocationVisible(loc.location_id);
              if (!isVisible && previewMode !== "debug") return null;

              const isSelected = selectedLocationId === loc.location_id;
              const { x, y, w, h } = eff.bounds;

              let borderCol = "#64748b";
              let bgCol = "rgba(100, 116, 139, 0.15)";
              if (eff.source === "case_override") {
                borderCol = "#fda4af";
                bgCol = "rgba(253, 164, 175, 0.15)";
              } else if (eff.source === "canonical") {
                borderCol = "#38bdf8";
                bgCol = "rgba(56, 189, 248, 0.12)";
              }

              let opacity = 1;
              if (previewMode === "fog" && !isVisible) {
                opacity = 0.15;
              }

              return (
                <div
                  key={loc.location_id}
                  className={`location-block ${isSelected ? "selected" : ""}`}
                  style={{
                    left: `${(x / 64) * 100}%`,
                    top: `${(y / 48) * 100}%`,
                    width: `${(w / 64) * 100}%`,
                    height: `${(h / 48) * 100}%`,
                    borderColor: borderCol,
                    borderWidth: isSelected ? "3px" : "2px",
                    background: bgCol,
                    opacity,
                    zIndex: 20
                  }}
                  onPointerDown={(e) => handlePointerDown(e, "location", loc.location_id)}
                >
                  <div className="label">
                    {loc.name}
                    <div style={{ fontSize: "8px", opacity: 0.65, marginTop: "2px" }}>
                      ({x},{y}) {w}×{h}
                    </div>
                  </div>
                  {isSelected && (
                    <div
                      className="resize-handle"
                      onPointerDown={(e) => handlePointerDown(e, "resize", loc.location_id)}
                    />
                  )}
                </div>
              );
            })}

            {/* Object Evidence Anchors */}
            {visibleLayers["object_anchors"] && showEvidenceAnchors && selectedCaseId !== "canonical" &&
              activeObjects.map((obj) => {
                const effObj = getObjectEffective(obj.object_id);
                if (!effObj || !effObj.anchor) return null;

                const isSelected = selectedObjectId === obj.object_id;
                const { x, y } = effObj.anchor;
                const isLocVisible = isLocationVisible(effObj.location_id);
                if (previewMode === "player_reveal" && !isLocVisible) return null;

                return (
                  <div
                    key={obj.object_id}
                    className={`object-anchor-dot ${isSelected ? "selected" : ""}`}
                    style={{
                      left: `${(x / 64) * 100}%`,
                      top: `${(y / 48) * 100}%`,
                      opacity: previewMode === "fog" && !isLocVisible ? 0.3 : 1,
                      zIndex: 25
                    }}
                    title={`${obj.name} (${x}, ${y})`}
                    onPointerDown={(e) => handlePointerDown(e, "object", obj.object_id)}
                  />
                );
              })}
          </div>
        </main>

        {/* Right Properties Config Panel */}
        <aside className="properties-panel">
          {/* Selected Location Config */}
          {selectedLocationId ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className="section-title">Selected Location</div>
              <div className="control-group">
                <label>ID</label>
                <input type="text" value={selectedLocationId} readOnly style={{ opacity: 0.6 }} />
              </div>

              {(() => {
                const loc = activeLocations.find(l => l.location_id === selectedLocationId);
                const eff = getLocationEffective(selectedLocationId);
                if (!loc || !eff) return null;

                return (
                  <>
                    <div className="control-group">
                      <label>Name</label>
                      <input type="text" value={loc.name} readOnly style={{ opacity: 0.6 }} />
                    </div>
                    <div className="control-group">
                      <label>Source Type</label>
                      <div style={{ fontSize: "0.85rem", color: "#38bdf8", fontWeight: 600 }}>
                        {eff.source.toUpperCase()} {eff.isOverridden && "(Override Active)"}
                      </div>
                    </div>
                    <div className="control-group" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                      <div>
                        <label>Tile X</label>
                        <input
                          type="number"
                          value={eff.bounds.x}
                          step={fineAdjustment ? 0.5 : 1}
                          onChange={(e) => updateLocationBounds(selectedLocationId, { x: parseFloat(e.target.value) })}
                        />
                      </div>
                      <div>
                        <label>Tile Y</label>
                        <input
                          type="number"
                          value={eff.bounds.y}
                          step={fineAdjustment ? 0.5 : 1}
                          onChange={(e) => updateLocationBounds(selectedLocationId, { y: parseFloat(e.target.value) })}
                        />
                      </div>
                    </div>
                    <div className="control-group" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                      <div>
                        <label>Width</label>
                        <input
                          type="number"
                          value={eff.bounds.w}
                          step={fineAdjustment ? 0.5 : 1}
                          onChange={(e) => updateLocationBounds(selectedLocationId, { w: parseFloat(e.target.value) })}
                        />
                      </div>
                      <div>
                        <label>Height</label>
                        <input
                          type="number"
                          value={eff.bounds.h}
                          step={fineAdjustment ? 0.5 : 1}
                          onChange={(e) => updateLocationBounds(selectedLocationId, { h: parseFloat(e.target.value) })}
                        />
                      </div>
                    </div>
                    <div className="control-group">
                      <label>Mode</label>
                      <select
                        value={eff.mode}
                        onChange={(e) => {
                          const val = e.target.value;
                          setLayout((prev) => {
                            if (!prev) return null;
                            const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
                            if (!copy.canonical_locations[selectedLocationId]) {
                              copy.canonical_locations[selectedLocationId] = { bounds: eff.bounds, mode: val };
                            } else {
                              copy.canonical_locations[selectedLocationId].mode = val;
                            }
                            return copy;
                          });
                        }}
                      >
                        <option value="exterior">Exterior</option>
                        <option value="interior">Interior</option>
                      </select>
                    </div>

                    {selectedCaseId !== "canonical" && (
                      <div className="control-group">
                        <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
                          <input 
                            type="checkbox"
                            checked={isLocationVisible(selectedLocationId)}
                            onChange={() => toggleLocationVisibility(selectedLocationId)}
                          />
                          Visible in this Case override
                        </label>
                      </div>
                    )}

                    <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
                      <button className="btn btn-secondary" style={{ flex: 1 }} onClick={resetToCanonicalRec}>
                        Recommended
                      </button>
                      <button className="btn btn-secondary" style={{ flex: 1 }} onClick={resetToLegacyFallback}>
                        Legacy
                      </button>
                    </div>
                  </>
                );
              })()}
            </div>
          ) : selectedObjectId && selectedCaseId !== "canonical" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className="section-title">Selected Object Anchor</div>
              <div className="control-group">
                <label>ID</label>
                <input type="text" value={selectedObjectId} readOnly style={{ opacity: 0.6 }} />
              </div>

              {(() => {
                const obj = activeObjects.find(o => o.object_id === selectedObjectId);
                const eff = getObjectEffective(selectedObjectId);
                if (!obj || !eff) return null;

                return (
                  <>
                    <div className="control-group">
                      <label>Name</label>
                      <input type="text" value={obj.name} readOnly style={{ opacity: 0.6 }} />
                    </div>
                    <div className="control-group" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                      <div>
                        <label>Anchor X</label>
                        <input
                          type="number"
                          value={eff.anchor.x}
                          step={fineAdjustment ? 0.5 : 1}
                          onChange={(e) => updateObjectAnchor(selectedObjectId, { x: parseFloat(e.target.value) })}
                        />
                      </div>
                      <div>
                        <label>Anchor Y</label>
                        <input
                          type="number"
                          value={eff.anchor.y}
                          step={fineAdjustment ? 0.5 : 1}
                          onChange={(e) => updateObjectAnchor(selectedObjectId, { y: parseFloat(e.target.value) })}
                        />
                      </div>
                    </div>
                    <div className="control-group">
                      <label>Render Policy</label>
                      <select 
                        value={eff.render_policy || "discovery_gated"} 
                        onChange={(e) => {
                          const val = e.target.value;
                          setLayout((prev) => {
                            if (!prev) return null;
                            const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
                            copy.case_overrides[selectedCaseId].object_anchors[selectedObjectId].render_policy = val;
                            return copy;
                          });
                          setIsDirty(true);
                        }}
                      >
                        <option value="always_visible">Always Visible</option>
                        <option value="case_visible">Case Visible</option>
                        <option value="discovery_gated">Discovery Gated (In-game Clue discovery)</option>
                        <option value="hidden_until_revealed">Hidden Until Revealed</option>
                        <option value="debug_only">Debug Only</option>
                      </select>
                    </div>
                  </>
                );
              })()}
            </div>
          ) : selectedPropInstanceId ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className="section-title">Selected Prop Instance</div>
              <div className="control-group">
                <label>Instance ID</label>
                <input type="text" value={selectedPropInstanceId} readOnly style={{ opacity: 0.6 }} />
              </div>

              {(() => {
                const prop = activeProps.find(p => p.instance_id === selectedPropInstanceId);
                if (!prop) return null;

                return (
                  <>
                    <div className="control-group">
                      <label>Asset ID</label>
                      <input type="text" value={prop.asset_id} readOnly style={{ opacity: 0.6 }} />
                    </div>

                    <div className="control-group" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                      <div>
                        <label>Prop X</label>
                        <input
                          type="number"
                          value={prop.x}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value);
                            setLayout((prev) => {
                              if (!prev) return null;
                              const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
                              for (const scope of Object.keys(copy.prop_instances || {})) {
                                const idx = copy.prop_instances[scope].findIndex(p => p.instance_id === selectedPropInstanceId);
                                if (idx !== -1) {
                                  copy.prop_instances[scope][idx].x = val;
                                  break;
                                }
                              }
                              return copy;
                            });
                          }}
                        />
                      </div>
                      <div>
                        <label>Prop Y</label>
                        <input
                          type="number"
                          value={prop.y}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value);
                            setLayout((prev) => {
                              if (!prev) return null;
                              const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
                              for (const scope of Object.keys(copy.prop_instances || {})) {
                                const idx = copy.prop_instances[scope].findIndex(p => p.instance_id === selectedPropInstanceId);
                                if (idx !== -1) {
                                  copy.prop_instances[scope][idx].y = val;
                                  break;
                                }
                              }
                              return copy;
                            });
                          }}
                        />
                      </div>
                    </div>

                    <div className="control-group" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                      <div>
                        <label>Width</label>
                        <input
                          type="number"
                          value={prop.w || 1}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value);
                            setLayout((prev) => {
                              if (!prev) return null;
                              const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
                              for (const scope of Object.keys(copy.prop_instances || {})) {
                                const idx = copy.prop_instances[scope].findIndex(p => p.instance_id === selectedPropInstanceId);
                                if (idx !== -1) {
                                  copy.prop_instances[scope][idx].w = val;
                                  break;
                                }
                              }
                              return copy;
                            });
                          }}
                        />
                      </div>
                      <div>
                        <label>Height</label>
                        <input
                          type="number"
                          value={prop.h || 1}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value);
                            setLayout((prev) => {
                              if (!prev) return null;
                              const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
                              for (const scope of Object.keys(copy.prop_instances || {})) {
                                const idx = copy.prop_instances[scope].findIndex(p => p.instance_id === selectedPropInstanceId);
                                if (idx !== -1) {
                                  copy.prop_instances[scope][idx].h = val;
                                  break;
                                }
                              }
                              return copy;
                            });
                          }}
                        />
                      </div>
                    </div>

                    <div className="control-group">
                      <label>Render Policy</label>
                      <select
                        value={prop.render_policy || "always_visible"}
                        onChange={(e) => {
                          const val = e.target.value;
                          setLayout((prev) => {
                            if (!prev) return null;
                            const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
                            for (const scope of Object.keys(copy.prop_instances || {})) {
                              const idx = copy.prop_instances[scope].findIndex(p => p.instance_id === selectedPropInstanceId);
                              if (idx !== -1) {
                                copy.prop_instances[scope][idx].render_policy = val;
                                break;
                              }
                            }
                            return copy;
                          });
                        }}
                      >
                        <option value="always_visible">Always Visible</option>
                        <option value="case_visible">Case Visible</option>
                        <option value="discovery_gated">Discovery Gated</option>
                        <option value="hidden_until_revealed">Hidden Until Revealed</option>
                        <option value="debug_only">Debug Only</option>
                      </select>
                    </div>

                    <div className="control-group">
                      <label>Linked Clue Object ID (Optional)</label>
                      <input 
                        type="text" 
                        placeholder="e.g. obj_mud_bootprint"
                        value={prop.object_id || ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          setLayout((prev) => {
                            if (!prev) return null;
                            const copy = JSON.parse(JSON.stringify(prev)) as TownLayout;
                            for (const scope of Object.keys(copy.prop_instances || {})) {
                              const idx = copy.prop_instances[scope].findIndex(p => p.instance_id === selectedPropInstanceId);
                              if (idx !== -1) {
                                copy.prop_instances[scope][idx].object_id = val || undefined;
                                break;
                              }
                            }
                            return copy;
                          });
                        }}
                      />
                    </div>

                    <button className="btn btn-danger" onClick={deleteSelectedPropInstance}>
                      🗑 Delete Prop
                    </button>
                  </>
                );
              })()}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className="section-title">Global Adjustments</div>
              <div className="control-group">
                <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
                  <input 
                    type="checkbox" 
                    checked={fineAdjustment} 
                    onChange={(e) => setFineAdjustment(e.target.checked)} 
                  />
                  Fine snap (0.5 bounds increments)
                </label>
              </div>

              <div className="control-group">
                <label className="section-title">Preview Overlay Modes</label>
                <select value={previewMode} onChange={(e) => setPreviewMode(e.target.value as any)}>
                  <option value="debug">Canonical Debug View</option>
                  <option value="player_reveal">Player Case Reveal View</option>
                  <option value="fog">Fogged Non-case Areas</option>
                </select>
              </div>

              <div className="control-group">
                <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
                  <input 
                    type="checkbox"
                    checked={showEvidenceAnchors}
                    onChange={(e) => setShowEvidenceAnchors(e.target.checked)}
                  />
                  Show Evidence Anchors
                </label>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <div className="section-title">Validations ({validationWarnings.length})</div>
                {validationWarnings.length === 0 ? (
                  <div style={{ color: "#4ade80", fontSize: "0.85rem", padding: "8px", background: "rgba(74, 222, 128, 0.05)", borderRadius: "6px", border: "1px solid rgba(74, 222, 128, 0.1)" }}>
                    ✓ No coordinate warnings.
                  </div>
                ) : (
                  <div className="warnings-panel">
                    {validationWarnings.map((w, idx) => (
                      <div key={idx}>• {w}</div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {selectedCaseId !== "canonical" && selectedLocationId && (
            <div className="control-group" style={{ marginTop: "auto" }}>
              <button className="btn btn-secondary" onClick={promoteToCanonical}>
                👑 Promote bounds to canonical
              </button>
            </div>
          )}
        </aside>
      </div>

      {/* Export JSON Modal */}
      {showExportModal && (
        <div className="modal-overlay" onClick={() => setShowExportModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="section-title">Raw JSON Payload Export</div>
            <textarea readOnly value={JSON.stringify(layout, null, 2)} onClick={(e) => (e.target as any).select()} />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
              <button className="btn btn-secondary" onClick={() => {
                navigator.clipboard.writeText(JSON.stringify(layout, null, 2));
                showToast("Copied layout to clipboard!", "success");
              }}>
                📋 Copy JSON
              </button>
              <button className="btn btn-primary" onClick={() => setShowExportModal(false)}>
                Close Window
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Import JSON Modal */}
      {showImportModal && (
        <div className="modal-overlay" onClick={() => setShowImportModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="section-title">Paste Layout JSON (Schema V2)</div>
            <textarea 
              value={importText} 
              placeholder='Paste JSON here...'
              onChange={(e) => setImportText(e.target.value)} 
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
              <button className="btn btn-secondary" onClick={() => setShowImportModal(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleImportTextSubmit}>
                Preview Layout
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
