import { useEffect, useMemo, useRef, useState } from "react";
import { api, hhmm, minutes } from "../api";
import { useWorld, type MapJump } from "../App";
import type { CluePublic, LocationPublic, MapEvent, MapReplayData } from "../types";
import LocationTransition, {
  shouldPlayLocationTransition,
} from "../components/LocationTransition";
import VisualMap from "../components/VisualMap";
import MapTimeline from "../components/MapTimeline";
import { markerMeta } from "../components/EventMarker";
import { agentPinsAt, buildTracks, markersAt, agentTracePath } from "../map/mapProjection";
import { audioManager } from "../audio";

const TICK_MS = 600; // real ms per replayed game-minute at 1x

function mapLocationsForClue(clue: CluePublic) {
  return [...new Set([
    ...clue.linked_location_ids,
    ...(clue.source_location_id ? [clue.source_location_id] : []),
  ])];
}

export default function MapReplay({
  jump,
  onConsumeJump,
  onOpenSuspect,
}: {
  jump: MapJump | null;
  onConsumeJump: () => void;
  onOpenSuspect: (agentId: string) => void;
}) {
  const { caseOverview, agentName, locationName } = useWorld();
  const [data, setData] = useState<MapReplayData | null>(null);
  const [clues, setClues] = useState<CluePublic[]>([]);
  const [truthMode, setTruthMode] = useState(false);
  const [accused, setAccused] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [t, setT] = useState(minutes(caseOverview.sim_start_time));
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [locationFilter, setLocationFilter] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<MapEvent | null>(null);
  const [selectedLocationId, setSelectedLocationId] = useState<string | null>(null);
  const [inspectResult, setInspectResult] = useState<string | null>(null);
  const [toast, setToast] = useState<CluePublic[] | null>(null);
  const [transitionLoc, setTransitionLoc] = useState<LocationPublic | null>(null);
  const [showTrace, setShowTrace] = useState(false);
  const [selectedClueId, setSelectedClueId] = useState<string | null>(null);
  const [evidenceFocusLocationId, setEvidenceFocusLocationId] = useState<string | null>(null);

  const toastTimer = useRef<number>(0);
  const playFrame = useRef<number>(0);

  useEffect(() => {
    return () => window.clearTimeout(toastTimer.current);
  }, []);

  // Full-range fetch; filtering is applied client-side on already-projected
  // (player-safe) data so agent position tracks stay complete.
  useEffect(() => {
    api
      .mapReplay(truthMode ? { mode: "truth" } : undefined)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(String(e)));
    api.status().then((s) => setAccused(s.accused)).catch(() => {});
    api.clues().then(setClues).catch(() => {});
  }, [truthMode]);

  const startMin = minutes(caseOverview.sim_start_time);
  const endMin = minutes(caseOverview.discovery_time);

  // Continuous play loop. The map projection accepts fractional minutes, so
  // witnessed movement travels smoothly instead of stepping once per minute.
  useEffect(() => {
    if (!playing) return;
    let lastFrame = performance.now();
    const advance = (now: number) => {
      const elapsed = now - lastFrame;
      lastFrame = now;
      setT((prev) => {
        const next = prev + (elapsed / TICK_MS) * speed;
        if (next >= endMin) {
          setPlaying(false);
          return endMin;
        }
        return next;
      });
      playFrame.current = window.requestAnimationFrame(advance);
    };
    playFrame.current = window.requestAnimationFrame(advance);
    return () => window.cancelAnimationFrame(playFrame.current);
  }, [playing, speed, endMin]);

  // Jump requests from the case board ("view clue on map"). Waits for the
  // replay data so an event reference can resolve to its time/location.
  useEffect(() => {
    if (!jump || !data) return;
    let locationId = jump.locationId ?? null;
    let time = jump.time ?? null;
    if (jump.eventId) {
      const event = data.events.find((e) => e.event_id === jump.eventId);
      if (event) {
        // Only player-visible events resolve; hidden ones simply don't match.
        setSelectedEvent(event);
        locationId = locationId ?? null;
        time = time ?? event.time;
        if (!jump.locationId) setSelectedLocationId(null);
      }
    }
    if (locationId) {
      setSelectedLocationId(locationId);
      if (!jump.eventId) setSelectedEvent(null);
    }
    if (time) setT(minutes(time));
    setPlaying(false);
    onConsumeJump();
  }, [jump, data, onConsumeJump]);

  const tracks = useMemo(() => (data ? buildTracks(data) : null), [data]);

  const filteredEvents = useMemo(() => {
    if (!data) return [];
    return data.events.filter((e) => {
      if (locationFilter && e.location_id !== locationFilter) return false;
      // agent_ids is already identity-safe: ambiguous events carry none.
      if (agentFilter && !e.agent_ids.includes(agentFilter)) return false;
      return true;
    });
  }, [data, locationFilter, agentFilter]);

  const pins = useMemo(() => {
    if (!data || !tracks) return [];
    const all = agentPinsAt(data, tracks, t);
    return agentFilter ? all.filter((p) => p.agent.agent_id === agentFilter) : all;
  }, [data, tracks, t, agentFilter]);

  const traceSegments = useMemo(() => {
    if (!showTrace || !agentFilter || !data || !tracks) return [];
    return agentTracePath(data, tracks, agentFilter, t, truthMode);
  }, [showTrace, agentFilter, data, tracks, t, truthMode]);

  const markers = useMemo(() => markersAt(filteredEvents, t), [filteredEvents, t]);

  const pastEvents = useMemo(
    () => filteredEvents.filter((e) => minutes(e.time) <= t),
    [filteredEvents, t]
  );
  const feedRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight });
  }, [pastEvents.length]);

  if (error) return <p className="muted">Map replay unavailable: {error}</p>;
  if (!data) return <p className="muted">Loading the village map…</p>;

  const selectedLocation = data.locations.find(
    (l) => l.location_id === selectedLocationId
  );
  const selectedClue = clues.find((clue) => clue.clue_id === selectedClueId) ?? null;
  const selectClue = (clue: CluePublic) => {
    const firstLocationId = mapLocationsForClue(clue)[0] ?? null;
    setSelectedClueId(clue.clue_id);
    setSelectedEvent(null);
    setSelectedLocationId(firstLocationId);
    setEvidenceFocusLocationId(firstLocationId);
    setPlaying(false);
  };

  const pinEvent = async (event: MapEvent) => {
    const result = await api.pinEvent(event.event_id);
    if (result.new_clues.length) {
      audioManager.playStinger("clue_discovered");
      setToast(result.new_clues);
      setClues((current) => [
        ...current,
        ...result.new_clues.filter((clue) => !current.some((known) => known.clue_id === clue.clue_id)),
      ]);
      window.clearTimeout(toastTimer.current);
      toastTimer.current = window.setTimeout(() => setToast(null), 6000);
    }
    setData((prev) =>
      prev
        ? {
            ...prev,
            events: prev.events.map((e) =>
              e.event_id === event.event_id ? { ...e, pinned: true } : e
            ),
          }
        : prev
    );
    setSelectedEvent((prev) =>
      prev && prev.event_id === event.event_id ? { ...prev, pinned: true } : prev
    );
  };

  const inspectLocation = async (locationId: string) => {
    const result = await api.inspect(locationId);
    if (result.new_clues.length) {
      audioManager.playStinger("clue_discovered");
      setToast(result.new_clues);
      setClues((current) => [
        ...current,
        ...result.new_clues.filter((clue) => !current.some((known) => known.clue_id === clue.clue_id)),
      ]);
      window.clearTimeout(toastTimer.current);
      toastTimer.current = window.setTimeout(() => setToast(null), 6000);
    }
    setInspectResult(
      result.new_clues.length
        ? `Found: ${result.new_clues.map((c) => c.title).join(", ")}`
        : result.hint ?? "Nothing new here."
    );
  };

  return (
    <div className="map-replay">
      {transitionLoc && (
        <LocationTransition
          location={transitionLoc}
          onDone={() => setTransitionLoc(null)}
        />
      )}
      <div className="map-replay-main">
        <div className="map-toolbar panel">
          <select value={locationFilter} onChange={(e) => setLocationFilter(e.target.value)}>
            <option value="">All locations</option>
            {data.locations.map((l) => (
              <option key={l.location_id} value={l.location_id}>
                {l.name}
              </option>
            ))}
          </select>
          <select value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)}>
            <option value="">Everyone</option>
            {data.agents.map((a) => (
              <option key={a.agent_id} value={a.agent_id}>
                {a.full_name}
                {a.is_victim ? " (victim)" : ""}
              </option>
            ))}
          </select>
          {agentFilter && (
            <label className="truth-toggle">
              <input
                type="checkbox"
                checked={showTrace}
                onChange={(e) => setShowTrace(e.target.checked)}
              />
              Show movement trace
            </label>
          )}
          {agentFilter && !truthMode && (
            <span className="muted small">
              Only publicly identifiable moments are shown.
              {showTrace && " Gaps mean the person was out of sight."}
            </span>
          )}
          {accused && (
            <label className="truth-toggle">
              <input
                type="checkbox"
                checked={truthMode}
                onChange={(e) => setTruthMode(e.target.checked)}
              />
              Truth replay
            </label>
          )}
        </div>

        {truthMode && (
          <div className="truth-banner">
            TRUTH REVEAL REPLAY — showing the full hidden timeline.
          </div>
        )}

        <VisualMap
          data={data}
          pins={pins}
          markers={markers}
          traceSegments={traceSegments}
          selectedEventId={selectedEvent?.event_id ?? null}
          selectedLocationId={selectedLocationId}
          focusLocationId={locationFilter || evidenceFocusLocationId}
          evidenceLocationIds={selectedClue ? mapLocationsForClue(selectedClue) : []}
          evidenceAgentIds={selectedClue?.linked_agent_ids ?? []}
          currentMinutes={t}
          onSelectEvent={(e) => {
            setSelectedEvent(e);
            setSelectedLocationId(null);
            setSelectedClueId(null);
            setEvidenceFocusLocationId(null);
          }}
          onSelectLocation={(id) => {
            setSelectedLocationId(id);
            setSelectedEvent(null);
            setSelectedClueId(null);
            setEvidenceFocusLocationId(null);
            setInspectResult(null);
            const loc = data.locations.find((l) => l.location_id === id);
            if (loc && shouldPlayLocationTransition(id)) setTransitionLoc(loc);
          }}
          onSelectAgent={onOpenSuspect}
        />

        <MapTimeline
          startMin={startMin}
          endMin={endMin}
          current={t}
          playing={playing}
          speed={speed}
          murderWindow={caseOverview.murder_window}
          onScrub={(v) => {
            setT(v);
            setPlaying(false);
          }}
          onTogglePlay={() => {
            if (!playing && t >= endMin) setT(startMin);
            setPlaying(!playing);
          }}
          onSpeed={setSpeed}
        />
      </div>

      <aside className="map-side panel">
        {toast && (
          <div className="clue-toast">
            {toast.map((c) => (
              <div key={c.clue_id}>
                <strong>New clue:</strong> {c.title}
              </div>
            ))}
          </div>
        )}

        {selectedEvent && (
          <div className="map-detail">
            <h3>
              {selectedEvent.time} · {markerMeta(selectedEvent.visual_event_type).label}
            </h3>
            <p>{selectedEvent.description}</p>
            <p className="muted small">
              {locationName(selectedEvent.location_id)}
              {selectedEvent.agent_ids.length > 0 &&
                ` · ${selectedEvent.agent_ids.map(agentName).join(", ")}`}
              {selectedEvent.visibility !== "public" && " · unclear sighting"}
            </p>
            {!truthMode && (
              <button
                className="pin"
                disabled={selectedEvent.pinned}
                onClick={() => pinEvent(selectedEvent)}
              >
                {selectedEvent.pinned ? "Pinned to notes" : "Pin to notes"}
              </button>
            )}
          </div>
        )}

        {selectedLocation && (
          <div className="map-detail">
            <h3>{selectedLocation.name}</h3>
            <p className="muted">{selectedLocation.description}</p>
            <button className="pin" onClick={() => inspectLocation(selectedLocation.location_id)}>
              Inspect this place
            </button>
            {inspectResult && <p className="small">{inspectResult}</p>}
          </div>
        )}

        {selectedClue && (
          <section className="map-evidence-detail" aria-label={`Evidence lead: ${selectedClue.title}`}>
            <div className="map-evidence-detail-head">
              <span>Evidence lead</span>
              <button type="button" onClick={() => { setSelectedClueId(null); setEvidenceFocusLocationId(null); }}>
                Clear
              </button>
            </div>
            <h3>{selectedClue.title}</h3>
            <p>{selectedClue.description}</p>
            <div className="map-evidence-links">
              {mapLocationsForClue(selectedClue).map((id) => (
                <span key={id}>📍 {locationName(id)}</span>
              ))}
              {selectedClue.linked_agent_ids.map((id) => (
                <button type="button" key={id} onClick={() => onOpenSuspect(id)}>
                  {agentName(id)}
                </button>
              ))}
              {selectedClue.linked_agent_ids.length > 0 && <small>Open a person’s dossier to review the connection.</small>}
            </div>
          </section>
        )}

        <section className="map-evidence-leads" aria-label="Discovered evidence leads">
          <h4>Evidence leads ({clues.length})</h4>
          {clues.length === 0 ? (
            <p className="muted small">Discovered evidence will appear here and light up its linked places and people.</p>
          ) : (
            <div className="map-evidence-list">
              {clues.map((clue) => (
                <button
                  type="button"
                  key={clue.clue_id}
                  className={selectedClueId === clue.clue_id ? "active" : ""}
                  onClick={() => selectClue(clue)}
                >
                  <span>{clue.title}</span>
                  {(() => {
                    const locations = mapLocationsForClue(clue);
                    return <small>{locations.length ? `${locations.length} place${locations.length === 1 ? "" : "s"}` : "Person link only"}</small>;
                  })()}
                </button>
              ))}
            </div>
          )}
        </section>

        <h4 className="map-feed-title">
          Observed up to {hhmm(t)} ({pastEvents.length})
        </h4>
        <div className="map-feed" ref={feedRef}>
          {pastEvents.length === 0 && (
            <p className="muted small">Nothing observed yet. Press play or scrub forward.</p>
          )}
          {pastEvents.map((e) => (
            <button
              key={e.event_id}
              className={`map-feed-event ${selectedEvent?.event_id === e.event_id ? "active" : ""} ${e.visibility !== "public" ? "ambiguous" : ""}`}
              onClick={() => {
                setT(minutes(e.time));
                setPlaying(false);
                setSelectedEvent(e);
                setSelectedLocationId(null);
              }}
            >
              <span className="map-feed-time">{e.time}</span>
              <span className="map-feed-desc">
                {markerMeta(e.visual_event_type).glyph} {e.description}
              </span>
            </button>
          ))}
        </div>
      </aside>
    </div>
  );
}
