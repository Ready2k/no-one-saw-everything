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
  internalView = false,
}: {
  light: MapLightOverlayData;
  width: number;
  height: number;
  currentMinutes: number;
  internalView?: boolean;
}) {
  if (!isActiveAt(light, currentMinutes)) return null;

  // The internal (roofless interior) mosaic tile is a different painted
  // asset than the exterior one — buildings are redrawn as isolated cutaway
  // rooms, not pixel-aligned with their exterior footprint — so a light
  // measured against the exterior art can land on grass or furniture once
  // zoomed in. Locations with an authored `*_internal` override swap to a
  // position/asset measured against that interior art instead.
  const useInternal = internalView && light.x_internal != null && light.y_internal != null;
  const x = useInternal ? light.x_internal! : light.x;
  const y = useInternal ? light.y_internal! : light.y;
  const w = useInternal ? light.width_internal ?? light.width : light.width;
  const h = useInternal ? light.height_internal ?? light.height : light.height;
  const asset = useInternal ? light.semantic_asset_id_internal ?? light.semantic_asset_id : light.semantic_asset_id;
  const opacity = useInternal ? light.opacity_internal ?? light.opacity ?? 0.7 : light.opacity ?? 0.7;

  return (
    <div
      className={`map-light-local ${asset}`}
      style={{
        left: pct(x - w / 2, width),
        top: pct(y - h / 2, height),
        width: pct(w, width),
        height: pct(h, height),
        opacity,
      }}
      aria-hidden="true"
    />
  );
}
