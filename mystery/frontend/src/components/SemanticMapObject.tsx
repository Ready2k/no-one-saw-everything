import type { MapVisualObject } from "../types";

function pct(value: number, total: number): string {
  return `${(value / total) * 100}%`;
}

/**
 * Safe visual hook for semantic props/evidence. Suppressed objects never
 * reach this component; discovery remains owned by the backend clue session.
 */
export default function SemanticMapObject({
  object,
  width,
  height,
  zoomCompensation = 1,
}: {
  object: MapVisualObject;
  width: number;
  height: number;
  zoomCompensation?: number;
}) {
  return (
    <div
      className={`semantic-map-object ${object.damaged ? "damaged" : ""}`}
      style={{
        left: pct(object.position.x, width),
        top: pct(object.position.y, height),
        transform: `translate(-50%, -50%) scale(${zoomCompensation})`,
      }}
      title={`${object.semantic_asset_id} — discovered evidence`}
      aria-label={`Discovered evidence: ${object.semantic_asset_id}`}
    >
      {object.glyph ?? "•"}
    </div>
  );
}
