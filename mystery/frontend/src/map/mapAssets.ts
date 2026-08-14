// Asset abstraction for the map replay layer. The backend tells us which
// map asset to use; this module resolves it to servable URLs so the full
// tilemap renderer could be swapped in later without touching the views.

export function mapImageUrl(image: string): string {
  return image; // backend already returns a public path, e.g. /art/town/...
}

/** Select a same-frame close-zoom asset when a single-image map has one. */
export function mapImageForScale(
  map: { image: string; zoom_image?: { threshold: number; url: string } },
  scale?: number
): string {
  return scale != null && map.zoom_image && scale >= map.zoom_image.threshold
    ? map.zoom_image.url
    : map.image;
}

// A map's art may arrive as a mosaic (map.image_tiles) instead of one image.
// Resolve it to percent-positioned pieces that tile the full map rectangle;
// null means "no mosaic — render map.image as a single image".
export interface MapImageTile {
  url: string;
  leftPct: number;
  topPct: number;
  widthPct: number;
  heightPct: number;
}

export function mapImageTiles(map: {
  image: string;
  image_tiles?: { cols: number; rows: number; urls: string[][] };
  zoom_image_tiles?: { threshold: number; urls: string[][] };
}, scale?: number): MapImageTile[] | null {
  const t = map.image_tiles;
  if (!t || !t.cols || !t.rows || !t.urls?.length) return null;
  const urls =
    scale != null && map.zoom_image_tiles && scale >= map.zoom_image_tiles.threshold
      ? map.zoom_image_tiles.urls
      : t.urls;
  const tiles: MapImageTile[] = [];
  urls.forEach((rowUrls, r) =>
    rowUrls.forEach((url, c) =>
      tiles.push({
        url: mapImageUrl(url),
        leftPct: (c / t.cols) * 100,
        topPct: (r / t.rows) * 100,
        widthPct: 100 / t.cols,
        heightPct: 100 / t.rows,
      })
    )
  );
  return tiles;
}

// Fallback grid for a map definition that carries no grid of its own.
export const MAP_GRID = { cols: 140, rows: 100 } as const;

// Agent markers are drawn at 1.25x a grid tile rather than exactly 1:1, so a
// moving figure reads clearly against the town art and overlaps its
// neighbouring tiles slightly. Cosmetic only.
export const AGENT_TILE_SCALE = 40 / 32;
