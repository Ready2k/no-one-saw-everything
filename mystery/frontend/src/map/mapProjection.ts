// Client-side projection of the player-safe event log onto map space.
// This layer only interprets what the backend already decided is visible:
// it never derives truth. An agent's rendered position is their *last
// publicly known* position, which is exactly the player's knowledge.

import { minutes } from "../api";
import type {
  MapAgent,
  MapEvent,
  MapLocation,
  MapPosition,
  MapReplayData,
} from "../types";

const MOVE_DURATION_MIN = 3; // minutes an agent_move animates over
export const MARKER_TRAIL_MIN = 6; // event markers linger this long

export interface TrackPoint {
  timeMin: number;
  locationId: string;
  event: MapEvent;
}

export interface AgentPin {
  agent: MapAgent;
  x: number;
  y: number;
  staleMinutes: number; // minutes since last public sighting
  lastSeenTime: string | null;
  lastSeenLocationId: string | null;
}

export function locationCenter(
  locations: MapLocation[],
  locationId: string | null
): MapPosition | null {
  if (!locationId) return null;
  const loc = locations.find((l) => l.location_id === locationId);
  return loc?.map_position ?? null;
}

/** Per-agent list of publicly known sightings, sorted by time. */
export function buildTracks(data: MapReplayData): Map<string, TrackPoint[]> {
  const tracks = new Map<string, TrackPoint[]>();
  for (const agent of data.agents) tracks.set(agent.agent_id, []);
  for (const event of data.events) {
    for (const agentId of event.agent_ids) {
      tracks.get(agentId)?.push({
        timeMin: minutes(event.time),
        locationId: event.to_location_id ?? event.location_id,
        event,
      });
    }
  }
  for (const points of tracks.values()) points.sort((a, b) => a.timeMin - b.timeMin);
  return tracks;
}

function spread(index: number, count: number): { dx: number; dy: number } {
  if (count <= 1) return { dx: 0, dy: 0 };
  const angle = (2 * Math.PI * index) / count;
  return { dx: Math.cos(angle) * 12, dy: Math.sin(angle) * 12 };
}

/** Where each agent is drawn at minute t — last known sighting, with
 * agent_move events interpolated between from/to locations. */
export function agentPinsAt(
  data: MapReplayData,
  tracks: Map<string, TrackPoint[]>,
  tMin: number
): AgentPin[] {
  const raw: (Omit<AgentPin, "x" | "y"> & { pos: MapPosition; locId: string })[] = [];

  for (const agent of data.agents) {
    const points = tracks.get(agent.agent_id) ?? [];
    let current: TrackPoint | null = null;
    for (const p of points) {
      if (p.timeMin <= tMin) current = p;
      else break;
    }

    let locId = current?.locationId ?? agent.home_location_id;
    let pos = locationCenter(data.locations, locId ?? null);

    // Animate along from -> to during a move.
    if (current && current.event.visual_event_type === "agent_move") {
      const fromPos = locationCenter(data.locations, current.event.from_location_id);
      const toPos = locationCenter(data.locations, current.locationId);
      if (fromPos && toPos) {
        const progress = Math.min(1, (tMin - current.timeMin) / MOVE_DURATION_MIN);
        pos = {
          x: fromPos.x + (toPos.x - fromPos.x) * progress,
          y: fromPos.y + (toPos.y - fromPos.y) * progress,
        };
      }
    }

    if (!pos || !locId) continue; // nowhere known to draw them
    raw.push({
      agent,
      pos,
      locId,
      staleMinutes: current ? tMin - current.timeMin : Number.POSITIVE_INFINITY,
      lastSeenTime: current?.event.time ?? null,
      lastSeenLocationId: current?.locationId ?? null,
    });
  }

  // Spread out agents sharing a location so sprites don't stack.
  const byLoc = new Map<string, number>();
  for (const r of raw) byLoc.set(r.locId, (byLoc.get(r.locId) ?? 0) + 1);
  const seen = new Map<string, number>();
  return raw.map((r) => {
    const index = seen.get(r.locId) ?? 0;
    seen.set(r.locId, index + 1);
    const { dx, dy } = spread(index, byLoc.get(r.locId) ?? 1);
    return {
      agent: r.agent,
      x: r.pos.x + dx,
      y: r.pos.y + dy,
      staleMinutes: r.staleMinutes,
      lastSeenTime: r.lastSeenTime,
      lastSeenLocationId: r.lastSeenLocationId,
    };
  });
}

/** Events rendered as markers at minute t: recent happenings linger for a
 * short trail so scrubbing reveals them. */
export function markersAt(events: MapEvent[], tMin: number): MapEvent[] {
  return events.filter((e) => {
    const et = minutes(e.time);
    return et <= tMin && tMin - et <= MARKER_TRAIL_MIN;
  });
}
