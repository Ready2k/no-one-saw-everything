// Asset abstraction for the map replay layer. The backend tells us which
// map asset to use; this module resolves it to servable URLs so the full
// tilemap renderer could be swapped in later without touching the views.

export function mapImageUrl(image: string): string {
  return image; // backend already returns a public path, e.g. /map/the_ville.png
}

export function spriteUrl(spriteAsset: string): string {
  return `/map/sprites/${spriteAsset}`;
}

// Original Smallville character sheets are 96x128: a 3x4 grid of 32x32
// frames (columns: step-left / idle / step-right; rows: down / left /
// right / up). We render the idle, facing-down frame.
export const SPRITE_SHEET = {
  frameWidth: 32,
  frameHeight: 32,
  idleDownX: -32, // middle column
  idleDownY: 0, // top row
} as const;
