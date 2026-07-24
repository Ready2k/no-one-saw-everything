// Asset abstraction for the map replay layer. The backend tells us which
// map asset to use; this module resolves it to servable URLs so the full
// tilemap renderer could be swapped in later without touching the views.

export function mapImageUrl(image: string): string {
  return image; // backend already returns a public path, e.g. /map/the_ville.png
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

export function spriteUrl(spriteAsset: string): string {
  return `/map/sprites/${spriteAsset}`;
}

// Original Smallville character sheets are a 3x4 grid of frames (columns:
// step-left / idle / step-right; rows: down / left / right / up). We render
// the idle, facing-down frame. Expressed as grid indices (not pixels) so the
// frame can be drawn at any on-screen size via background-size scaling.
export const SPRITE_SHEET = {
  cols: 3,
  rows: 4,
  idleCol: 1,
  idleRow: 0,
} as const;

// Legacy fallback grid. Migrated maps return their own grid in MapReplayData.
export const MAP_GRID = { cols: 140, rows: 100 } as const;

// The original Phaser renderer (upstream generative-agents demo,
// main_script.html) draws each 32x32 character frame at displayWidth=40
// against tile_width=32 (`new_sprite.displayWidth = 40; scaleY = scaleX`) —
// i.e. characters are deliberately drawn at 1.25x a tile, not exactly 1:1,
// so they read clearly and overlap neighboring tiles slightly. Matched here
// so sprite proportions agree with the source game.
export const AGENT_TILE_SCALE = 40 / 32;
