import { useEffect, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type { MapReplayData } from "../types";
import { mapImageUrl } from "../map/mapAssets";
import Portrait from "../components/Portrait";

// Fixed crop viewport for the discovery-location illustration; the map is
// pixel art, so the crop is scaled with image-rendering: pixelated in CSS.
const CROP_W = 340;
const CROP_H = 200;
const CROP_PAD = 1.8; // bounds fill ~1/pad of the crop

function DiscoveryMapCrop({ data, locationId }: { data: MapReplayData; locationId: string }) {
  const loc = data.locations.find((l) => l.location_id === locationId);
  if (!loc) return null;
  const { width, height } = data.map;
  let cx: number;
  let cy: number;
  let scale: number;
  if (loc.map_bounds) {
    const b = loc.map_bounds;
    cx = b.x + b.width / 2;
    cy = b.y + b.height / 2;
    scale = Math.min(CROP_W / (b.width * CROP_PAD), CROP_H / (b.height * CROP_PAD));
  } else if (loc.map_position) {
    cx = loc.map_position.x;
    cy = loc.map_position.y;
    scale = 2;
  } else {
    return null;
  }
  return (
    <div
      className="intro-map-crop"
      style={{
        width: CROP_W,
        height: CROP_H,
        backgroundImage: `url(${mapImageUrl(data.map.image)})`,
        backgroundSize: `${width * scale}px ${height * scale}px`,
        backgroundPosition: `${CROP_W / 2 - cx * scale}px ${CROP_H / 2 - cy * scale}px`,
      }}
      role="img"
      aria-label={`Map view of ${loc.name}`}
    />
  );
}

export default function Intro({ onBegin }: { onBegin: () => void }) {
  const { caseOverview: c, agents } = useWorld();
  const [mapData, setMapData] = useState<MapReplayData | null>(null);
  const [witnessIds, setWitnessIds] = useState<string[]>([]);

  // Cosmetic enrichments — the scene works without either of these.
  useEffect(() => {
    api.mapReplay().then(setMapData).catch(() => {});
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
            <DiscoveryMapCrop
              data={mapData}
              locationId={c.discovery_location.location_id}
            />
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
