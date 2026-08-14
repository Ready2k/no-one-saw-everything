import { describe, it, expect } from "vitest";
import { agentTracePath, buildTracks, type TrackPoint } from "./mapProjection";
import type { MapReplayData, MapEvent } from "../types";

function mockData(): MapReplayData {
  return {
    case_id: "test",
    mode: "player",
    map: { asset: "map.png", image: "map.png", width: 1000, height: 1000 },
    time_range: { start: "08:00", end: "09:00" },
    locations: [
      { location_id: "loc1", name: "Loc1", description: "", connected_location_ids: [], visibility_type: "public", illustration: null, map_position: { x: 100, y: 100 }, map_bounds: null, visual_layer: "exterior" },
      { location_id: "loc2", name: "Loc2", description: "", connected_location_ids: [], visibility_type: "public", illustration: null, map_position: { x: 200, y: 200 }, map_bounds: null, visual_layer: "exterior" },
      { location_id: "loc3", name: "Loc3", description: "", connected_location_ids: [], visibility_type: "private", illustration: null, map_position: { x: 300, y: 300 }, map_bounds: null, visual_layer: "exterior" }
    ],
    agents: [
      { agent_id: "agent1", full_name: "Agent 1", age: 30, occupation: "", traits: [], portrait: null, portrait_art: null, home_location_id: "loc1", work_location_id: "loc2", routine_summary: "", is_victim: false, is_background: false, stall_fillers: [] }
    ],
    events: []
  };
}

function mockEvent(time: string, location_id: string, visibility: "public" | "private" | "public_partial", type: "agent_present" | "agent_move" = "agent_present", from_location_id: string | null = null): MapEvent {
  return {
    event_id: Math.random().toString(),
    time,
    location_id,
    agent_ids: ["agent1"],
    event_type: "test",
    description: "test",
    visibility,
    importance: 1,
    visual_event_type: type,
    from_location_id,
    to_location_id: location_id
  };
}

describe("agentTracePath", () => {
  it("returns empty trace when tracks are empty", () => {
    const data = mockData();
    const tracks = new Map<string, TrackPoint[]>();
    const segments = agentTracePath(data, tracks, "agent1", 480, false);
    expect(segments).toEqual([]);
  });

  it("includes public events up to current replay time", () => {
    const data = mockData();
    data.events = [
      mockEvent("08:00", "loc1", "public"),
      mockEvent("08:05", "loc1", "public"),
      mockEvent("08:15", "loc1", "public") // beyond tMin
    ];
    const tracks = buildTracks(data);
    
    // tMin = 485 (08:05)
    const segments = agentTracePath(data, tracks, "agent1", 485, false);
    expect(segments.length).toBe(1);
    expect(segments[0].points.length).toBe(2);
    expect(segments[0].points[0].tMin).toBe(480);
    expect(segments[0].points[1].tMin).toBe(485);
  });

  it("includes all events in data.events", () => {
    const data = mockData();
    data.events = [
      mockEvent("08:00", "loc1", "public"),
      mockEvent("08:05", "loc2", "private"), // Private but player knows it
      mockEvent("08:10", "loc2", "public")
    ];
    const tracks = buildTracks(data);
    
    const segments = agentTracePath(data, tracks, "agent1", 490, false);
    expect(segments.length).toBe(1); // Gap is 5 mins, so it's a single trace
    expect(segments[0].points.length).toBe(3);
  });

  it("splits into separate segments after an out-of-sight gap", () => {
    const data = mockData();
    data.events = [
      mockEvent("08:00", "loc1", "public"),
      mockEvent("08:20", "loc2", "public") // 20 minute gap > 15
    ];
    const tracks = buildTracks(data);
    
    const segments = agentTracePath(data, tracks, "agent1", 500, false);
    expect(segments.length).toBe(2);
    expect(segments[0].points[0].tMin).toBe(480);
    expect(segments[1].points[0].tMin).toBe(500);
  });

  it("interpolates movement", () => {
    const data = mockData();
    data.events = [
      mockEvent("08:00", "loc1", "public"),
      mockEvent("08:01", "loc2", "public", "agent_move", "loc1")
    ];
    const tracks = buildTracks(data);
    
    // Check midway interpolation
    const segments = agentTracePath(data, tracks, "agent1", 482, false);
    expect(segments.length).toBe(1);
    // point at 08:00, move start at 08:01, move midway at 08:02 (482)
    expect(segments[0].points.length).toBe(3);
    expect(segments[0].points[2].tMin).toBe(482);
    expect(segments[0].points[2].x).toBeGreaterThan(100);
    expect(segments[0].points[2].x).toBeLessThan(200);
  });
});
