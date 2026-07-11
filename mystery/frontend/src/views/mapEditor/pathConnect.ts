// Deterministic path auto-connection for placed buildings.
//
// A building's dressing gives it a 2-tile front-door path stub (mirroring the
// backend's dress_building contract). This module carves the shortest walkable
// route from that stub to the nearest tile of the existing path network —
// painted tile_path / tile_cobble tiles or another building's stub — so users
// dropping buildings onto a blank mosaic cell get connected streets without
// hand-painting every tile. Visual-only, like everything in the layout.

import { BuildingInstance, TileEntry, TownLayout, buildingFrontEdge, edgeStripCells, rotatedFootprint } from "./editorTypes";

export const PATH_NETWORK_TILES = new Set(["tile_path", "tile_cobble"]);

const BLOCKING_TILES = new Set([
  "tile_wall_exterior",
  "tile_wall_interior",
  "tile_water",
  "tile_water_edge",
  "tile_fence",
  "tile_hedge",
  "tile_tree"
]);

export type ConnectFailure = "no_stub" | "no_network" | "unreachable";

export interface ConnectResult {
  tiles: TileEntry[];
  alreadyConnected?: boolean;
  failure?: ConnectFailure;
}

const key = (x: number, y: number) => y * 4096 + x;

function collectSets(layout: TownLayout): { blocked: Set<number>; network: Set<number> } {
  const blocked = new Set<number>();
  const network = new Set<number>();
  for (const layer of Object.values(layout.tile_layers || {})) {
    for (const t of layer.tiles || []) {
      if (BLOCKING_TILES.has(t.tile_id)) blocked.add(key(t.x, t.y));
      else if (PATH_NETWORK_TILES.has(t.tile_id)) network.add(key(t.x, t.y));
    }
  }
  // Footprints double as walls even if a structures tile went missing.
  for (const b of layout.building_instances || []) {
    const fp = rotatedFootprint(b.footprint || { w: 1, h: 1 }, b.rotation || 0);
    for (let dx = 0; dx < fp.w; dx++) for (let dy = 0; dy < fp.h; dy++) blocked.add(key(b.x + dx, b.y + dy));
  }
  return { blocked, network };
}

/** The building's own path cells: its dressed front stub (and service path). */
export function buildingStubCells(building: BuildingInstance): Array<{ x: number; y: number }> {
  const stub = (building.derived_tiles?.paths?.tiles || []).filter((t) => PATH_NETWORK_TILES.has(t.tile_id));
  if (stub.length) return stub.map((t) => ({ x: t.x, y: t.y }));
  // No dressed stub — fall back to the strip of ground along the front wall.
  const rotation = building.rotation || 0;
  const fp = rotatedFootprint(building.footprint || { w: 1, h: 1 }, rotation);
  return edgeStripCells(building.x, building.y, fp.w, fp.h, buildingFrontEdge(rotation), 1);
}

/**
 * Shortest 4-directional route from `building`'s stub to the nearest path
 * network tile that is not part of the stub itself. Returns only the new
 * tile_path entries to paint (cells already on the network are skipped).
 */
export function connectBuildingToPaths(layout: TownLayout, building: BuildingInstance): ConnectResult {
  const { cols, rows } = layout.grid;
  const { blocked, network } = collectSets(layout);

  const sources = buildingStubCells(building).filter(
    (c) => c.x >= 0 && c.y >= 0 && c.x < cols && c.y < rows && !blocked.has(key(c.x, c.y))
  );
  if (!sources.length) return { tiles: [], failure: "no_stub" };

  const own = new Set(sources.map((c) => key(c.x, c.y)));
  const targets = new Set([...network].filter((k) => !own.has(k)));
  if (!targets.size) return { tiles: [], failure: "no_network" };

  // Already touching the wider network?
  for (const c of sources) {
    if (targets.has(key(c.x, c.y))) return { tiles: [], alreadyConnected: true };
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]] as const) {
      if (targets.has(key(c.x + dx, c.y + dy))) return { tiles: [], alreadyConnected: true };
    }
  }

  // Multi-source BFS over walkable ground.
  const cameFrom = new Map<number, number>();
  let frontier = sources.map((c) => key(c.x, c.y));
  const visited = new Set(frontier);
  let goal = -1;
  while (frontier.length && goal < 0) {
    const next: number[] = [];
    for (const k of frontier) {
      const x = k % 4096;
      const y = Math.floor(k / 4096);
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]] as const) {
        const nx = x + dx;
        const ny = y + dy;
        if (nx < 0 || ny < 0 || nx >= cols || ny >= rows) continue;
        const nk = key(nx, ny);
        if (visited.has(nk) || blocked.has(nk)) continue;
        visited.add(nk);
        cameFrom.set(nk, k);
        if (targets.has(nk)) {
          goal = nk;
          break;
        }
        next.push(nk);
      }
      if (goal >= 0) break;
    }
    frontier = next;
  }
  if (goal < 0) return { tiles: [], failure: "unreachable" };

  const tiles: TileEntry[] = [];
  for (let k = cameFrom.get(goal); k !== undefined && !own.has(k); k = cameFrom.get(k)) {
    tiles.push({ x: k % 4096, y: Math.floor(k / 4096), tile_id: "tile_path" });
  }
  return { tiles };
}

export interface ConnectAllSummary {
  added: TileEntry[];
  connected: number;
  alreadyConnected: number;
  failed: Array<{ instance_id: string; failure: ConnectFailure }>;
}

/**
 * Re-connect every placed building, chaining as it goes: connector tiles laid
 * for one building become network for the next, so buildings on an otherwise
 * blank cell link up to each other.
 */
export function connectAllBuildings(layout: TownLayout): ConnectAllSummary {
  const summary: ConnectAllSummary = { added: [], connected: 0, alreadyConnected: 0, failed: [] };
  const pathsLayer = (layout.tile_layers.paths ||= { tiles: [] });
  for (const building of layout.building_instances || []) {
    const result = connectBuildingToPaths(layout, building);
    if (result.alreadyConnected) summary.alreadyConnected += 1;
    else if (result.failure) summary.failed.push({ instance_id: building.instance_id, failure: result.failure });
    else {
      pathsLayer.tiles.push(...result.tiles);
      summary.added.push(...result.tiles);
      summary.connected += 1;
    }
  }
  return summary;
}
