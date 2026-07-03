import { useEffect, useState } from "react";
import type { LocationPublic, MapReplayData } from "../types";
import { cinematicsEnabled } from "../settings";
import { getMapInfo } from "../map/mapInfo";
import MapCrop from "./MapCrop";

const TRANSITION_MS = 600; // spec: ≤600ms, always skippable

/** True (and marks the location seen) when the establishing shot should play.
 * Plays at most once per location per browser-tab session. */
export function shouldPlayLocationTransition(locationId: string): boolean {
  if (!cinematicsEnabled()) return false;
  const key = `mystery_loc_seen_${locationId}`;
  if (sessionStorage.getItem(key)) return false;
  sessionStorage.setItem(key, "1");
  return true;
}

export default function LocationTransition({
  location,
  onDone,
}: {
  location: LocationPublic;
  onDone: () => void;
}) {
  const [mapData, setMapData] = useState<MapReplayData | null>(null);

  useEffect(() => {
    if (!location.illustration) {
      // Usually already cached by an earlier view; a slow first fetch just
      // means the shot shows the name card alone.
      getMapInfo().then(setMapData).catch(() => {});
    }
    const timer = setTimeout(onDone, TRANSITION_MS);
    return () => clearTimeout(timer);
  }, [location, onDone]);

  return (
    <div className="loc-transition" onClick={onDone} title="Click to skip">
      {location.illustration ? (
        <img
          className="loc-transition-art"
          src={location.illustration}
          alt={location.name}
          onError={(e) => ((e.currentTarget as HTMLImageElement).style.display = "none")}
        />
      ) : (
        mapData && (
          <MapCrop
            data={mapData}
            locationId={location.location_id}
            className="loc-transition-crop"
          />
        )
      )}
      <h2>{location.name}</h2>
    </div>
  );
}
