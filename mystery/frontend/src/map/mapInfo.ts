// Session-cached map geometry (image + location bounds) for views that only
// need a crop of the village map, not the full replay event stream.

import { api } from "../api";
import type { MapReplayData } from "../types";

let cached: Promise<MapReplayData> | null = null;

export function getMapInfo(): Promise<MapReplayData> {
  if (!cached) {
    cached = api.mapReplay().catch((e) => {
      cached = null; // allow retry on transient failure
      throw e;
    });
  }
  return cached;
}
