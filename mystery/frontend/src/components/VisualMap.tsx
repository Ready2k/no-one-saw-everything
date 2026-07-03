import type { MapEvent, MapReplayData } from "../types";
import type { AgentPin } from "../map/mapProjection";
import { locationCenter } from "../map/mapProjection";
import { mapImageUrl } from "../map/mapAssets";
import AgentSprite from "./AgentSprite";
import EventMarker from "./EventMarker";

// Positions are stored in map-image pixels; we place everything with
// percentages so the map can scale responsively.
function pct(v: number, total: number): string {
  return `${(v / total) * 100}%`;
}

export default function VisualMap({
  data,
  pins,
  markers,
  selectedEventId,
  selectedLocationId,
  onSelectEvent,
  onSelectLocation,
  onSelectAgent,
}: {
  data: MapReplayData;
  pins: AgentPin[];
  markers: MapEvent[];
  selectedEventId: string | null;
  selectedLocationId: string | null;
  onSelectEvent: (event: MapEvent) => void;
  onSelectLocation: (locationId: string) => void;
  onSelectAgent: (agentId: string) => void;
}) {
  const { width, height } = data.map;

  // Nudge markers sharing a location so they don't overlap.
  const markerOffsets = new Map<string, number>();

  return (
    <div
      className="visual-map"
      style={{
        aspectRatio: `${width} / ${height}`,
        width: `min(100%, calc(64vh * ${(width / height).toFixed(4)}))`,
        alignSelf: "center",
      }}
    >
      <img
        className="visual-map-image"
        src={mapImageUrl(data.map.image)}
        alt="Village map"
        draggable={false}
      />

      {data.locations.map((loc) => {
        if (!loc.map_position) return null;
        const selected = selectedLocationId === loc.location_id;
        return (
          <div key={loc.location_id}>
            {loc.map_bounds && (
              <div
                className={`map-loc-bounds ${selected ? "selected" : ""} layer-${loc.visual_layer ?? "exterior"}`}
                style={{
                  left: pct(loc.map_bounds.x, width),
                  top: pct(loc.map_bounds.y, height),
                  width: pct(loc.map_bounds.width, width),
                  height: pct(loc.map_bounds.height, height),
                }}
              />
            )}
            <button
              className={`map-loc-label ${selected ? "selected" : ""}`}
              style={{
                left: pct(loc.map_position.x, width),
                top: pct(loc.map_position.y, height),
              }}
              onClick={() => onSelectLocation(loc.location_id)}
              title={loc.description}
            >
              {loc.name}
            </button>
          </div>
        );
      })}

      {markers.map((e) => {
        const center = locationCenter(data.locations, e.location_id);
        if (!center) return null;
        const n = markerOffsets.get(e.location_id) ?? 0;
        markerOffsets.set(e.location_id, n + 1);
        return (
          <div
            key={e.event_id}
            className="map-marker-anchor"
            style={{
              left: pct(center.x + n * 16 - 8, width),
              top: pct(center.y - 14, height),
            }}
          >
            <EventMarker
              event={e}
              x={0}
              y={0}
              selected={selectedEventId === e.event_id}
              onClick={() => onSelectEvent(e)}
            />
          </div>
        );
      })}

      {pins.map((pin) => (
        <div
          key={pin.agent.agent_id}
          className="map-agent-anchor"
          style={{ left: pct(pin.x, width), top: pct(pin.y, height) }}
        >
          <AgentSprite
            agent={pin.agent}
            x={0}
            y={0}
            stale={pin.staleMinutes > 10}
            lastSeen={pin.lastSeenTime}
            onClick={() => onSelectAgent(pin.agent.agent_id)}
          />
        </div>
      ))}
    </div>
  );
}
