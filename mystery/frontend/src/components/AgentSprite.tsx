import type { MapAgent } from "../types";
import { SPRITE_SHEET, spriteUrl } from "../map/mapAssets";

// A single idle frame cropped from the original Smallville sheet, drawn at
// exactly one map-tile's on-screen footprint (see MAP_GRID) so characters
// stay proportionate to furniture/buildings at any zoom level.
export default function AgentSprite({
  agent,
  x,
  y,
  size,
  stale,
  lastSeen,
  onClick,
}: {
  agent: MapAgent;
  x: number;
  y: number;
  size: { width: number; height: number };
  stale: boolean;
  lastSeen: string | null;
  onClick?: () => void;
}) {
  const title = agent.is_background
    ? `${agent.full_name} — ${agent.occupation}`
    : stale && lastSeen
      ? `${agent.full_name} — last seen ${lastSeen}`
      : agent.full_name;
  return (
    <button
      className={`map-agent ${agent.is_background ? "background-agent" : ""} ${stale ? "stale" : ""} ${agent.is_victim ? "victim" : ""}`}
      style={{ left: x, top: y }}
      title={title}
      onClick={onClick}
      data-agent-id={agent.agent_id}
    >
      <span
        className="map-agent-sprite"
        style={{
          width: size.width,
          height: size.height,
          backgroundImage: `url(${spriteUrl(agent.sprite_asset)})`,
          backgroundSize: `${SPRITE_SHEET.cols * size.width}px ${SPRITE_SHEET.rows * size.height}px`,
          backgroundPosition: `${-SPRITE_SHEET.idleCol * size.width}px ${-SPRITE_SHEET.idleRow * size.height}px`,
        }}
      />
      <span className="map-agent-name">
        {agent.full_name.split(" ")[0]}
        {stale && lastSeen ? ` · ${lastSeen}` : ""}
      </span>
    </button>
  );
}
