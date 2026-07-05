import { useEffect, useRef, useState, type WheelEvent as ReactWheelEvent } from "react";
import type { MapEvent, MapReplayData } from "../types";
import type { AgentPin, TraceSegment } from "../map/mapProjection";
import { locationCenter } from "../map/mapProjection";
import { AGENT_TILE_SCALE, MAP_GRID, mapImageUrl } from "../map/mapAssets";
import AgentSprite from "./AgentSprite";
import EventMarker from "./EventMarker";

// Positions are stored in map-image pixels; we place everything with
// percentages so the map can scale responsively.
function pct(v: number, total: number): string {
  return `${(v / total) * 100}%`;
}

const MIN_SCALE = 1;
const MAX_SCALE = 6;
const DRAG_CLICK_THRESHOLD = 5; // px of movement before a drag suppresses the click
const FOCUS_FILL = 0.6; // focused location bounds fill this fraction of the viewport
const FOCUS_POINT_SCALE = 2.5; // fallback zoom for locations with only a point
// Floor so agents stay clickable at full zoom-out, where one tile can be
// only a few px; irrelevant once zoomed in since the true tile size then
// exceeds it (this must stay small or characters look oversized again).
const MIN_AGENT_PX = 10;

export default function VisualMap({
  data,
  pins,
  markers,
  traceSegments = [],
  selectedEventId,
  selectedLocationId,
  focusLocationId = null,
  onSelectEvent,
  onSelectLocation,
  onSelectAgent,
}: {
  data: MapReplayData;
  pins: AgentPin[];
  markers: MapEvent[];
  traceSegments?: TraceSegment[];
  selectedEventId: string | null;
  selectedLocationId: string | null;
  focusLocationId?: string | null;
  onSelectEvent: (event: MapEvent) => void;
  onSelectLocation: (locationId: string) => void;
  onSelectAgent: (agentId: string) => void;
}) {
  const { width, height } = data.map;

  const viewportRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState({ scale: 1, tx: 0, ty: 0 });
  // Location bounds are only shown for the selected or label-hovered
  // location, so the default view stays clean like the source game.
  const [hoveredLocationId, setHoveredLocationId] = useState<string | null>(null);
  // Unscaled (pre-transform) viewport box, used to size agent sprites to a
  // real map tile's footprint instead of a fixed pixel size — otherwise
  // they render the same size regardless of how far the map is zoomed out.
  const [containerSize, setContainerSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const update = () => setContainerSize({ w: el.clientWidth, h: el.clientHeight });
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  // The floor is expressed in on-screen px, so divide it by the current
  // zoom before comparing against the true (pre-transform) tile size —
  // otherwise the floor would itself get multiplied by the zoom transform
  // and characters would grow past their correct tile size once zoomed in.
  const agentSize = {
    width: Math.max((containerSize.w / MAP_GRID.cols) * AGENT_TILE_SCALE, MIN_AGENT_PX / view.scale),
    height: Math.max((containerSize.h / MAP_GRID.rows) * AGENT_TILE_SCALE, MIN_AGENT_PX / view.scale),
  };
  const drag = useRef<{ startX: number; startY: number; tx: number; ty: number; moved: boolean } | null>(null);
  const suppressClick = useRef(false);
  // True while the view change came from a focus jump (dropdown selection),
  // so that jump animates; direct wheel/drag input stays immediate.
  const smooth = useRef(false);
  const [showLabels, setShowLabels] = useState(true);

  const clampView = (scale: number, tx: number, ty: number) => {
    const el = viewportRef.current;
    const vw = el?.clientWidth ?? 1;
    const vh = el?.clientHeight ?? 1;
    // Content is vw x vh at scale=1; at higher scale it's larger than the
    // viewport, so translation is clamped to keep it covering the viewport.
    const minTx = Math.min(0, vw - vw * scale);
    const minTy = Math.min(0, vh - vh * scale);
    return {
      scale,
      tx: Math.min(0, Math.max(minTx, tx)),
      ty: Math.min(0, Math.max(minTy, ty)),
    };
  };

  const zoomAt = (clientX: number, clientY: number, factor: number) => {
    const el = viewportRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const px = clientX - rect.left;
    const py = clientY - rect.top;
    setView((prev) => {
      const nextScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev.scale * factor));
      const contentX = (px - prev.tx) / prev.scale;
      const contentY = (py - prev.ty) / prev.scale;
      const tx = px - contentX * nextScale;
      const ty = py - contentY * nextScale;
      return clampView(nextScale, tx, ty);
    });
  };

  // Zoom to the focused location (dropdown selection); clear back to full view.
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    if (!focusLocationId) {
      smooth.current = true;
      setView({ scale: 1, tx: 0, ty: 0 });
      return;
    }
    const loc = data.locations.find((l) => l.location_id === focusLocationId);
    if (!loc) return;
    let cxFrac: number;
    let cyFrac: number;
    let scale: number;
    if (loc.map_bounds) {
      const b = loc.map_bounds;
      cxFrac = (b.x + b.width / 2) / width;
      cyFrac = (b.y + b.height / 2) / height;
      scale = FOCUS_FILL * Math.min(width / b.width, height / b.height);
    } else if (loc.map_position) {
      cxFrac = loc.map_position.x / width;
      cyFrac = loc.map_position.y / height;
      scale = FOCUS_POINT_SCALE;
    } else {
      return;
    }
    scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
    const vw = el.clientWidth;
    const vh = el.clientHeight;
    smooth.current = true;
    setView(clampView(scale, vw / 2 - cxFrac * vw * scale, vh / 2 - cyFrac * vh * scale));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusLocationId, data.locations, width, height]);

  const handleWheel = (e: ReactWheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    smooth.current = false;
    const factor = Math.exp(-e.deltaY * 0.0015);
    zoomAt(e.clientX, e.clientY, factor);
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    smooth.current = false;
    drag.current = { startX: e.clientX, startY: e.clientY, tx: view.tx, ty: view.ty, moved: false };
    // Pointer capture can throw (e.g. InvalidPointerId) for pointer sessions
    // the browser doesn't consider capturable; panning still works via the
    // bubbled move/up handlers without it, so failure here is harmless.
    try {
      (e.target as Element).setPointerCapture?.(e.pointerId);
    } catch {
      // ignore — see comment above
    }
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    const dx = e.clientX - drag.current.startX;
    const dy = e.clientY - drag.current.startY;
    if (Math.hypot(dx, dy) > DRAG_CLICK_THRESHOLD) drag.current.moved = true;
    if (drag.current.moved && view.scale > 1) {
      // Capture the drag origin now — the setView updater can run more than
      // once (e.g. React StrictMode double-invoke), and by a later call
      // handlePointerUp may already have reset drag.current to null.
      const originTx = drag.current.tx;
      const originTy = drag.current.ty;
      setView((prev) => clampView(prev.scale, originTx + dx, originTy + dy));
    }
  };

  const handlePointerUp = () => {
    if (drag.current?.moved) {
      suppressClick.current = true;
      // Clear after the click event that follows pointerup has had a chance to fire.
      setTimeout(() => (suppressClick.current = false), 0);
    }
    drag.current = null;
  };

  const handleClickCapture = (e: React.MouseEvent<HTMLDivElement>) => {
    if (suppressClick.current) {
      e.stopPropagation();
      e.preventDefault();
    }
  };

  const resetView = () => setView({ scale: 1, tx: 0, ty: 0 });
  const zoomButton = (factor: number) => () => {
    const el = viewportRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, factor);
  };

  // Nudge markers sharing a location so they don't overlap.
  const markerOffsets = new Map<string, number>();

  return (
    <div
      className="visual-map-viewport"
      ref={viewportRef}
      style={{
        aspectRatio: `${width} / ${height}`,
        width: `min(100%, calc(64vh * ${(width / height).toFixed(4)}))`,
        alignSelf: "center",
      }}
      onWheel={handleWheel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerUp}
      onClickCapture={handleClickCapture}
    >
      <div className="map-zoom-controls">
        <button type="button" onClick={zoomButton(1.4)} title="Zoom in">
          +
        </button>
        <button type="button" onClick={zoomButton(1 / 1.4)} title="Zoom out">
          −
        </button>
        <button type="button" onClick={resetView} title="Reset view" disabled={view.scale === 1}>
          ⟲
        </button>
        <button 
          type="button" 
          onClick={() => setShowLabels(s => !s)} 
          title={showLabels ? "Hide labels" : "Show labels"}
          style={{ fontSize: '1rem', marginTop: '4px', opacity: showLabels ? 1 : 0.5 }}
        >
          👁
        </button>
      </div>

      <div
        className={`visual-map ${view.scale > 1 ? "zoomed" : ""}`}
        style={{
          transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.scale})`,
          transition: smooth.current ? "transform 0.45s ease" : undefined,

        } as React.CSSProperties}
      >
        <img
          className="visual-map-image"
          src={mapImageUrl(data.map.image)}
          alt="Village map"
          draggable={false}
        />

        {traceSegments.length > 0 && (
          <svg className="map-trace-svg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
            {traceSegments.map((seg, i) => (
              <g key={i}>
                <polyline
                  className="map-trace-line"
                  points={seg.points.map(p => `${p.x},${p.y}`).join(" ")}
                  fill="none"
                />
                {seg.points.map((p, j) => p.isEvent && (
                  <circle
                    key={j}
                    className="map-trace-dot"
                    cx={p.x}
                    cy={p.y}
                    r={2.5}
                  />
                ))}
              </g>
            ))}
          </svg>
        )}

        {data.locations.map((loc) => {
          if (!loc.map_position) return null;
          const selected = selectedLocationId === loc.location_id;
          return (
            <div key={loc.location_id}>
              {loc.map_bounds && (
                <div
                  className={`map-loc-bounds ${selected ? "selected" : ""} ${
                    selected || hoveredLocationId === loc.location_id ? "visible" : ""
                  } layer-${loc.visual_layer ?? "exterior"}`}
                  style={{
                    left: pct(loc.map_bounds.x, width),
                    top: pct(loc.map_bounds.y, height),
                    width: pct(loc.map_bounds.width, width),
                    height: pct(loc.map_bounds.height, height),
                    // The zoom transform scales border thickness too; divide it
                    // out so the dashes stay hairline at any zoom level.
                    borderWidth: `${Math.max(1.25 / view.scale, 0.4)}px`,
                  }}
                />
              )}
              {showLabels && (
                <button
                  className={`map-loc-label ${selected ? "selected" : ""}`}
                  style={{
                    left: pct(loc.map_position.x, width),
                    top: pct(loc.map_position.y, height),
                  }}
                  onClick={() => onSelectLocation(loc.location_id)}
                  onMouseEnter={() => setHoveredLocationId(loc.location_id)}
                  onMouseLeave={() =>
                    setHoveredLocationId((prev) => (prev === loc.location_id ? null : prev))
                  }
                  title={loc.description}
                >
                  {loc.name}
                </button>
              )}
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
              size={agentSize}
              // staleMinutes is Infinity before an agent's first event of the
              // day — that's their assumed starting position, not aging
              // information, so it shouldn't get the "stale" fade. Only fade
              // once they've actually been seen and it's been a while since.
              stale={Number.isFinite(pin.staleMinutes) && pin.staleMinutes > 10}
              lastSeen={pin.lastSeenTime}
              onClick={() => onSelectAgent(pin.agent.agent_id)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
