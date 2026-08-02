import type { MapReplayData } from "../types";
import { mapImageForScale, mapImageTiles } from "../map/mapAssets";

// The canonical map is high-resolution lifelike artwork; browser smoothing
// must remain enabled when establishing-shot crops are scaled.
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
    let b = loc.map_bounds;
    scale = Math.max(width / (b.width * cropPad), height / (b.height * cropPad));
    // Crops tight enough to trip the tile swap show the roofless close-up
    // art, so frame the internal-view bounds instead when authored.
    const threshold = data.map.zoom_image_tiles?.threshold ?? data.map.zoom_image?.threshold;
    if (threshold != null && scale >= threshold && loc.map_bounds_internal) {
      b = loc.map_bounds_internal;
      scale = Math.max(width / (b.width * cropPad), height / (b.height * cropPad));
    }
    cx = b.x + b.width / 2;
    cy = b.y + b.height / 2;
    // Cover the establishing-shot frame. `min` leaves letterbox bars whenever
    // a tall location (such as the pub bounds) is shown in the wide card.
  } else if (loc.map_position) {
    cx = loc.map_position.x;
    cy = loc.map_position.y;
    scale = 2;
  } else {
    return null;
  }
  const tiles = mapImageTiles(data.map, scale);
  if (tiles) {
    // Mosaic art: emulate the background-position crop with a positioned
    // full-map layer inside an overflow-hidden frame.
    //
    // Each mosaic tile is a 5-6MB HD image, and a full mosaic is 3x3 (9) or
    // more with zoom variants — this crop only ever shows a small window
    // (`width`x`height`) onto it, so fetching every tile regardless of
    // whether it's inside that window used to mean ~50MB+ downloaded for a
    // 340x200px establishing-shot card. Skip any tile whose rectangle
    // doesn't actually intersect the visible crop window.
    const layerLeft = width / 2 - cx * scale;
    const layerTop = height / 2 - cy * scale;
    const visibleLeft = -layerLeft;
    const visibleTop = -layerTop;
    const visibleRight = visibleLeft + width;
    const visibleBottom = visibleTop + height;
    const visibleTiles = tiles.filter((t) => {
      const tileLeft = (t.leftPct / 100) * mapW * scale;
      const tileTop = (t.topPct / 100) * mapH * scale;
      const tileRight = tileLeft + (t.widthPct / 100) * mapW * scale;
      const tileBottom = tileTop + (t.heightPct / 100) * mapH * scale;
      return (
        tileRight > visibleLeft &&
        tileLeft < visibleRight &&
        tileBottom > visibleTop &&
        tileTop < visibleBottom
      );
    });
    return (
      <div
        className={className}
        style={{ width, height, position: "relative", overflow: "hidden" }}
        role="img"
        aria-label={`Map view of ${loc.name}`}
      >
        <div
          style={{
            position: "absolute",
            left: layerLeft,
            top: layerTop,
            width: mapW * scale,
            height: mapH * scale,
          }}
        >
          {visibleTiles.map((t) => (
            <img
              key={t.url}
              src={t.url}
              alt=""
              draggable={false}
              loading="lazy"
              decoding="async"
              style={{
                position: "absolute",
                left: `${t.leftPct}%`,
                top: `${t.topPct}%`,
                width: `${t.widthPct}%`,
                height: `${t.heightPct}%`,
                display: "block",
              }}
            />
          ))}
        </div>
      </div>
    );
  }
  return (
    <div
      className={className}
      style={{
        width,
        height,
        backgroundImage: `url(${mapImageForScale(data.map, scale)})`,
        backgroundSize: `${mapW * scale}px ${mapH * scale}px`,
        backgroundPosition: `${width / 2 - cx * scale}px ${height / 2 - cy * scale}px`,
      }}
      role="img"
      aria-label={`Map view of ${loc.name}`}
    />
  );
}
