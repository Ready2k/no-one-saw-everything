import type { MapReplayData } from "../types";
import { mapImageUrl } from "../map/mapAssets";

// The map is pixel art, so crops are scaled with image-rendering: pixelated
// (see .intro-map-crop / .loc-transition-crop in styles.css).
const CROP_PAD = 1.8; // bounds fill ~1/pad of the crop

export default function MapCrop({
  data,
  locationId,
  width = 340,
  height = 200,
  className = "intro-map-crop",
}: {
  data: MapReplayData;
  locationId: string;
  width?: number;
  height?: number;
  className?: string;
}) {
  const loc = data.locations.find((l) => l.location_id === locationId);
  if (!loc) return null;
  const { width: mapW, height: mapH } = data.map;
  const cropPad = data.visual?.crop_padding_by_location?.[locationId] ?? CROP_PAD;
  let cx: number;
  let cy: number;
  let scale: number;
  if (loc.map_bounds) {
    const b = loc.map_bounds;
    cx = b.x + b.width / 2;
    cy = b.y + b.height / 2;
    // Cover the establishing-shot frame. `min` leaves letterbox bars whenever
    // a tall location (such as the pub bounds) is shown in the wide card.
    scale = Math.max(width / (b.width * cropPad), height / (b.height * cropPad));
  } else if (loc.map_position) {
    cx = loc.map_position.x;
    cy = loc.map_position.y;
    scale = 2;
  } else {
    return null;
  }
  return (
    <div
      className={className}
      style={{
        width,
        height,
        backgroundImage: `url(${mapImageUrl(data.map.image)})`,
        backgroundSize: `${mapW * scale}px ${mapH * scale}px`,
        backgroundPosition: `${width / 2 - cx * scale}px ${height / 2 - cy * scale}px`,
      }}
      role="img"
      aria-label={`Map view of ${loc.name}`}
    />
  );
}
