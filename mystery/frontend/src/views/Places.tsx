import { useEffect, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type { InspectResult, LocationPublic } from "../types";
import { ClueCard } from "./shared";
import { MagnifyingSearch } from "../components/MagnifyingSearch";
import { audioManager } from "../audio";
import LocationTransition, {
  shouldPlayLocationTransition,
} from "../components/LocationTransition";
import { getMapInfo } from "../map/mapInfo";
import type { MapReplayData } from "../types";

export default function Places() {
  const { locations } = useWorld();
  const [mapData, setMapData] = useState<MapReplayData | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<InspectResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [transitionLoc, setTransitionLoc] = useState<LocationPublic | null>(null);

  useEffect(() => {
    getMapInfo().then(setMapData).catch(() => setMapData(null));
  }, []);

  const inspect = async (locationId: string) => {
    const loc = locations.find((l) => l.location_id === locationId);
    if (loc && shouldPlayLocationTransition(locationId)) setTransitionLoc(loc);
    setSelected(locationId);
    setBusy(true);
    try {
      const res = await api.inspect(locationId);
      if (res.new_clues?.length) {
        audioManager.playStinger("clue_discovered");
      }
      setResult(res);
    } finally {
      setBusy(false);
    }
  };

  const handleDiscover = async (clueId: string) => {
    if (!result) return;
    try {
      const discoveredClue = await api.discoverClue(clueId);
      audioManager.playStinger("clue_discovered");
      setResult((prev: InspectResult | null) => {
        if (!prev) return prev;
        return {
          ...prev,
          hidden_clues: prev.hidden_clues.filter((c: any) => c.clue_id !== clueId),
          known_clues: [...prev.known_clues, discoveredClue],
        };
      });
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="places">
      {transitionLoc && (
        <LocationTransition
          location={transitionLoc}
          onDone={() => setTransitionLoc(null)}
        />
      )}
      <div className="place-list panel">
        <h2>Search the village</h2>
        <p className="muted small">
          Inspect a place to search it for physical evidence. Some things only
          make sense once you know what to look for.
        </p>
        {locations.map((l) => (
          <button
            key={l.location_id}
            className={`place ${selected === l.location_id ? "active" : ""}`}
            onClick={() => inspect(l.location_id)}
          >
            <span className="place-name">{l.name}</span>
            {l.visibility_type === "private" && (
              <span className="badge ambiguous">private</span>
            )}
          </button>
        ))}
      </div>
      <div className="place-detail">
        {!result && <p className="muted">Pick a location to search it.</p>}
        {busy && <p className="muted">Searching…</p>}
        {result && !busy && (
          <div className="places-scroll-container">
            <h2>{result.location.name}</h2>
            
            {result.location.visibility_type === "private" && (
               <div className="alert warning" style={{ marginBottom: "1rem" }}>
                 <strong>Private area.</strong> You can search, but this may affect suspicion/trust if seen.
               </div>
            )}
            
            <MagnifyingSearch
               bounds={result.location.illustration
                 ? { x: 0, y: 0, width: 100, height: 100 }
                 : result.location.map_bounds}
               hiddenClues={result.hidden_clues || []}
               imageUrl={result.location.illustration || mapData?.map.image}
               mapWidth={result.location.illustration ? 100 : mapData?.map.width}
               mapHeight={result.location.illustration ? 100 : mapData?.map.height}
               isIllustration={Boolean(result.location.illustration)}
               onDiscover={handleDiscover}
            />

            <div className="search-status" style={{ marginBottom: "1rem" }}>
               <p style={{ margin: 0 }}><strong>Search status:</strong> {(result.known_clues.length)} / {(result.known_clues.length + (result.hidden_clues?.length || 0))} clues found</p>
            </div>

            <h3>Found evidence</h3>
            {result.known_clues.length > 0 ? (
               <div className="found-evidence-list">
                 {result.known_clues.map((c: any) => (
                   <ClueCard key={c.clue_id} clue={c} />
                 ))}
               </div>
            ) : (
               <p className="muted">Nothing found yet.</p>
            )}

            <h3 style={{ marginTop: "1rem" }}>Notes</h3>
            <p>{result.location.description}</p>
            {result.hint && <p className="hint-text">{result.hint}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
