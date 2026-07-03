import { useEffect, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type { MapReplayData } from "../types";
import { getMapInfo } from "../map/mapInfo";
import MapCrop from "../components/MapCrop";
import Portrait from "../components/Portrait";

export default function Intro({ onBegin }: { onBegin: () => void }) {
  const { caseOverview: c, agents } = useWorld();
  const [mapData, setMapData] = useState<MapReplayData | null>(null);
  const [witnessIds, setWitnessIds] = useState<string[]>([]);

  // Cosmetic enrichments — the scene works without either of these.
  useEffect(() => {
    getMapInfo().then(setMapData).catch(() => {});
    api
      .events({
        location_id: c.discovery_location.location_id,
        time_from: c.murder_window[0],
        time_to: c.discovery_time,
      })
      .then((events) => {
        const ids = new Set<string>();
        for (const e of events) for (const id of e.agent_ids) ids.add(id);
        ids.delete(c.victim.agent_id);
        setWitnessIds([...ids]);
      })
      .catch(() => {});
  }, [c]);

  // Esc always skips.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onBegin();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onBegin]);

  const witnesses = witnessIds
    .map((id) => agents.find((a) => a.agent_id === id))
    .filter((a) => a != null);

  return (
    <div className="intro-scene">
      <button className="intro-skip" onClick={onBegin} title="Skip (Esc)">
        Skip ›
      </button>
      <div className="intro-stage">
        <p className="intro-beat intro-time">{c.discovery_time}</p>
        <div className="intro-beat intro-victim">
          <Portrait agent={c.victim} size="large" />
          <h1>{c.victim.full_name} is dead.</h1>
        </div>
        <p className="intro-beat intro-description">
          {c.scene_description || c.overview_text}
        </p>
        <div className="intro-beat intro-place">
          {mapData && (
            <MapCrop data={mapData} locationId={c.discovery_location.location_id} />
          )}
          <p className="muted">
            Found in the <strong>{c.discovery_location.name}</strong> by{" "}
            <strong>
              <Portrait agent={c.discovered_by} /> {c.discovered_by.full_name}
            </strong>
            .
          </p>
        </div>
        {witnesses.length > 0 && (
          <div className="intro-beat intro-witnesses">
            <p className="muted small">Seen nearby around that time:</p>
            <div className="intro-witness-row">
              {witnesses.map((w) => (
                <span key={w.agent_id} className="intro-witness">
                  <Portrait agent={w} /> {w.full_name}
                </span>
              ))}
            </div>
          </div>
        )}
        <button className="primary intro-beat intro-cta" onClick={onBegin}>
          Begin Investigation
        </button>
      </div>
    </div>
  );
}
