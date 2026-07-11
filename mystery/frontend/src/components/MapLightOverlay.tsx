import type { MapLightOverlay as MapLightOverlayData } from "../types";

function pct(v: number, total: number): string {
  return `${(v / total) * 100}%`;
}

function clockMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function isActiveAt(light: MapLightOverlayData, currentMinutes: number): boolean {
  const t = ((currentMinutes % 1440) + 1440) % 1440;
  const from = clockMinutes(light.from);
  const to = clockMinutes(light.to);
  if (from === to) return true;
  if (from < to) return t >= from && t < to;
  return t >= from || t < to;
}

export default function MapLightOverlay({
  light,
  width,
  height,
  currentMinutes,
}: {
  light: MapLightOverlayData;
  width: number;
  height: number;
  currentMinutes: number;
}) {
  if (!isActiveAt(light, currentMinutes)) return null;

  return (
    <div
      className={`map-light-local ${light.semantic_asset_id}`}
      style={{
        left: pct(light.x - light.width / 2, width),
        top: pct(light.y - light.height / 2, height),
        width: pct(light.width, width),
        height: pct(light.height, height),
        opacity: light.opacity ?? 0.7,
      }}
      aria-hidden="true"
    />
  );
}
