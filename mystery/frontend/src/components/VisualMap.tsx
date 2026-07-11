import { useEffect, useRef, useState } from "react";
import type { MapEvent, MapReplayData } from "../types";
import type { AgentPin, TraceSegment } from "../map/mapProjection";
import { locationCenter } from "../map/mapProjection";
import { AGENT_TILE_SCALE, MAP_GRID, mapImageTiles, mapImageUrl } from "../map/mapAssets";
import { lightingTint } from "../map/lighting";
import AgentSprite from "./AgentSprite";
import EventMarker from "./EventMarker";
import SemanticMapObject from "./SemanticMapObject";

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
const CANONICAL_DEFAULT_SCALE = 3; // center square of the expanded 3x3 world
// Floor so agents stay clickable at full zoom-out, where one tile can be
// only a few px; irrelevant once zoomed in since the true tile size then
// exceeds it (this must stay small or characters look oversized again).
const MIN_AGENT_PX = 10;

// Ambient base-terrain fills for exterior environmental zones the map editor
// made visible but which sit OUTSIDE the hand-authored centre-third artwork
// (lake/fishery/woodland). Purely decorative — these carry no evidence and are
// discovery-safe. loc_meadow is intentionally omitted: its bounds overlap the
// painted town art, so the base image already dresses it.
const TERRAIN_ZONES: Record<string, string> = {
  loc_lake:
    "radial-gradient(120% 90% at 40% 32%, rgba(150,200,232,0.30), transparent 62%), linear-gradient(160deg, #35709f, #285a85)",
  loc_fishery:
    "linear-gradient(150deg, #6f5f45, #55452d)",
  loc_woodland:
    "radial-gradient(circle at 18% 40%, #3c6d3f 0 9px, transparent 10px), radial-gradient(circle at 62% 68%, #356239 0 11px, transparent 12px), radial-gradient(circle at 85% 30%, #3a6a3d 0 8px, transparent 9px), linear-gradient(#2f5a32, #29502f)",
};

export default function VisualMap({
  data,
  pins,
  markers,
  traceSegments = [],
  selectedEventId,
  selectedLocationId,
  focusLocationId = null,
  currentMinutes = null,
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
  // Minutes-since-midnight for the scrub position, used to tint the map for
  // time of day. Omitted (null) where no timeline is in play — the map then
  // renders with no lighting overlay.
  currentMinutes?: number | null;
  onSelectEvent: (event: MapEvent) => void;
  onSelectLocation: (locationId: string) => void;
  onSelectAgent: (agentId: string) => void;
}) {
  const { width, height } = data.map;
  const isCanonicalOverworld = data.visual?.mode === "canonical_overworld";
  const isCanonicalPilot = data.visual?.mode === "canonical_pilot" || isCanonicalOverworld;
  const artworkFrameStyle = data.visual?.mode === "canonical_pilot"
    ? {
        left: "33.333%",
        top: "33.333%",
        width: "33.333%",
        height: "33.333%",
      }
    : {
        left: "0%",
        top: "0%",
        width: "100%",
        height: "100%",
      };
  const defaultViewForMode = (vw: number, vh: number) => {
    if (!isCanonicalPilot) return { scale: 1, tx: 0, ty: 0 };
    const scale = CANONICAL_DEFAULT_SCALE;
    return {
      scale,
      tx: -(vw * ((scale - 1) / 2)),
      ty: -(vh * ((scale - 1) / 2)),
    };
  };

  const viewportRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState(() => {
    if (!isCanonicalPilot) return { scale: 1, tx: 0, ty: 0 };
    // Before layout is measured, use proportional values; an effect below
    // snaps these to the real viewport size on mount/resize.
    return { scale: CANONICAL_DEFAULT_SCALE, tx: -1, ty: -1 };
  });
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
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    smooth.current = true;
    const next = defaultViewForMode(el.clientWidth, el.clientHeight);
    setView(clampView(next.scale, next.tx, next.ty));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCanonicalPilot]);
  // The floor is expressed in on-screen px, so divide it by the current
  // zoom before comparing against the true (pre-transform) tile size —
  // otherwise the floor would itself get multiplied by the zoom transform
  // and characters would grow past their correct tile size once zoomed in.
  const grid = data.map.grid ?? MAP_GRID;
  const agentSize = {
    width: Math.max((containerSize.w / grid.cols) * AGENT_TILE_SCALE, MIN_AGENT_PX / view.scale),
    height: Math.max((containerSize.h / grid.rows) * AGENT_TILE_SCALE, MIN_AGENT_PX / view.scale),
  };
  // Past the tile-swap threshold the close-up (roofless interior) art is
  // shown, so locations switch to their internal-view bounds when authored;
  // unset internal bounds inherit the external ones.
  const internalThreshold = data.map.zoom_image_tiles?.threshold ?? Infinity;
  const internalView = view.scale >= internalThreshold;
  const effBounds = (loc: MapReplayData["locations"][number]) =>
    internalView && loc.map_bounds_internal ? loc.map_bounds_internal : loc.map_bounds;

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
  const defaultScale = isCanonicalPilot ? CANONICAL_DEFAULT_SCALE : 1;
  const defaultViewNow = (() => {
    const el = viewportRef.current;
    return el ? defaultViewForMode(el.clientWidth, el.clientHeight) : { scale: defaultScale, tx: 0, ty: 0 };
  })();
  const isAtDefaultView =
    Math.abs(view.scale - defaultViewNow.scale) < 0.001 &&
    Math.abs(view.tx - defaultViewNow.tx) < 0.5 &&
    Math.abs(view.ty - defaultViewNow.ty) < 0.5;

  // Zoom to the focused location (dropdown selection); clear back to full view.
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    if (!focusLocationId) {
      smooth.current = true;
      const next = defaultViewForMode(el.clientWidth, el.clientHeight);
      setView(clampView(next.scale, next.tx, next.ty));
      return;
    }
    const loc = data.locations.find((l) => l.location_id === focusLocationId);
    if (!loc) return;
    let cxFrac: number;
    let cyFrac: number;
    let scale: number;
    if (loc.map_bounds) {
      let b = loc.map_bounds;
      scale = FOCUS_FILL * Math.min(width / b.width, height / b.height);
      // If the focus lands past the tile-swap threshold, the close-up art is
      // shown — target the internal-view bounds instead when authored.
      if (scale >= internalThreshold && loc.map_bounds_internal) {
        b = loc.map_bounds_internal;
        scale = FOCUS_FILL * Math.min(width / b.width, height / b.height);
      }
      cxFrac = (b.x + b.width / 2) / width;
      cyFrac = (b.y + b.height / 2) / height;
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

  const handleWheel = (e: WheelEvent) => {
    e.preventDefault();
    smooth.current = false;
    const factor = Math.exp(-e.deltaY * 0.0015);
    zoomAt(e.clientX, e.clientY, factor);
  };
  // React registers onWheel as a passive listener by default, so calling
  // preventDefault() through the JSX prop is silently ignored (and logs
  // "Unable to preventDefault inside passive event listener invocation") —
  // the page scrolls under the map instead of the map zooming. A native,
  // explicitly non-passive listener is required to actually block scroll.
  const handleWheelRef = useRef(handleWheel);
  handleWheelRef.current = handleWheel;
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const listener = (e: WheelEvent) => handleWheelRef.current(e);
    el.addEventListener("wheel", listener, { passive: false });
    return () => el.removeEventListener("wheel", listener);
  }, []);

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

  const resetView = () => {
    const el = viewportRef.current;
    if (!el) return;
    smooth.current = true;
    const next = defaultViewForMode(el.clientWidth, el.clientHeight);
    setView(clampView(next.scale, next.tx, next.ty));
  };
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
        <button type="button" onClick={resetView} title="Reset view" disabled={isAtDefaultView}>
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
          backgroundColor: "#166534",
        } as React.CSSProperties}
      >
        <div
          className="visual-map-artwork"
          style={artworkFrameStyle}
        >
          <div className="visual-map-image-frame">
            {(() => {
              const tiles = mapImageTiles(data.map, view.scale);
              const artStyle = isCanonicalPilot ? { filter: "saturate(0.96) brightness(1.08)" } : undefined;
              if (tiles) {
                return (
                  <div className="visual-map-image" style={artStyle} role="img" aria-label="Village map">
                    {tiles.map((t) => (
                      <img
                        key={t.url}
                        className="visual-map-image-tile"
                        src={t.url}
                        alt=""
                        draggable={false}
                        style={{
                          left: `${t.leftPct}%`,
                          top: `${t.topPct}%`,
                          width: `${t.widthPct}%`,
                          height: `${t.heightPct}%`,
                        }}
                      />
                    ))}
                  </div>
                );
              }
              return (
                <img
                  className="visual-map-image"
                  src={mapImageUrl(data.map.image)}
                  alt="Village map"
                  draggable={false}
                  style={artStyle}
                />
              );
            })()}

            {currentMinutes != null && (
              <div
                className="map-lighting-overlay"
                style={{
                  backgroundColor: lightingTint(currentMinutes),
                  opacity: isCanonicalPilot ? 0.42 : 1,
                }}
              />
            )}
          </div>
        </div>

        {isCanonicalPilot && !isCanonicalOverworld &&
          data.locations.map((loc) => {
            const bg = TERRAIN_ZONES[loc.location_id];
            if (!bg || !loc.map_bounds) return null;
            const b = loc.map_bounds;
            return (
              <div
                key={`terrain-${loc.location_id}`}
                className="map-terrain-zone"
                style={{
                  left: pct(b.x, width),
                  top: pct(b.y, height),
                  width: pct(b.width, width),
                  height: pct(b.height, height),
                  backgroundImage: bg,
                }}
              >
                {currentMinutes != null && (
                  <div
                    className="map-terrain-tint"
                    style={{ backgroundColor: lightingTint(currentMinutes) }}
                  />
                )}
              </div>
            );
          })}

        {(data.visual?.object_visuals ?? data.visual?.objects ?? [])
          .filter((object) => object.safe_to_render && object.marker_state === "active")
          .map((object) => (
            <SemanticMapObject
              key={object.object_id}
              object={object}
              width={width}
              height={height}
            />
          ))}

        {traceSegments.length > 0 && (
          <svg className="map-trace-svg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
            {traceSegments.map((seg, i) => (
              <g key={i}>
                <polyline
                  className="map-trace-line"
                  points={seg.points.map((p) => `${p.x},${p.y}`).join(" ")}
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
          const bounds = effBounds(loc);
          // Keep the label centred on the bounds shown in the active view.
          const labelPos =
            internalView && loc.map_bounds_internal
              ? {
                  x: loc.map_bounds_internal.x + loc.map_bounds_internal.width / 2,
                  y: loc.map_bounds_internal.y + loc.map_bounds_internal.height / 2,
                }
              : loc.map_position;
          return (
            <div key={loc.location_id}>
              {bounds && (
                <div
                  className={`map-loc-bounds ${selected ? "selected" : ""} ${
                    selected || hoveredLocationId === loc.location_id ? "visible" : ""
                  } layer-${loc.visual_layer ?? "exterior"}`}
                  style={{
                    left: pct(bounds.x, width),
                    top: pct(bounds.y, height),
                    width: pct(bounds.width, width),
                    height: pct(bounds.height, height),
                    borderWidth: `${Math.max(1.25 / view.scale, 0.4)}px`,
                  }}
                />
              )}
              {showLabels && (
                <button
                  className={`map-loc-label ${selected ? "selected" : ""}`}
                  style={{
                    left: pct(labelPos.x, width),
                    top: pct(labelPos.y, height),
                    transform: `translate(-50%, -50%) scale(${1 / view.scale})`,
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
                zoomCompensation={1 / view.scale}
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
            style={{
              left: pct(pin.x, width),
              top: pct(pin.y, height),
            }}
          >
            <AgentSprite
              agent={pin.agent}
              x={0}
              y={0}
              size={agentSize}
              zoomCompensation={1 / view.scale}
              stale={Number.isFinite(pin.staleMinutes) && pin.staleMinutes > 10}
              lastSeen={pin.lastSeenTime}
              onClick={() => {
                if (!pin.agent.is_background) onSelectAgent(pin.agent.agent_id);
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
