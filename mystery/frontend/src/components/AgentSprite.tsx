import type { MapAgent } from "../types";
import { SPRITE_SHEET, spriteUrl } from "../map/mapAssets";

// A single idle frame cropped from the original 96x128 Smallville sheet.
// The sprite is only a visual avatar — the label always shows the
// canonical mystery character name.
export default function AgentSprite({
  agent,
  x,
  y,
  stale,
  lastSeen,
  onClick,
}: {
  agent: MapAgent;
  x: number;
  y: number;
  stale: boolean;
  lastSeen: string | null;
  onClick?: () => void;
}) {
  const title = stale && lastSeen
    ? `${agent.full_name} — last seen ${lastSeen}`
    : agent.full_name;
  return (
    <button
      className={`map-agent ${stale ? "stale" : ""} ${agent.is_victim ? "victim" : ""}`}
      style={{ left: x, top: y }}
      title={title}
      onClick={onClick}
      data-agent-id={agent.agent_id}
    >
      <span
        className="map-agent-sprite"
        style={{
          width: SPRITE_SHEET.frameWidth,
          height: SPRITE_SHEET.frameHeight,
          backgroundImage: `url(${spriteUrl(agent.sprite_asset)})`,
          backgroundPosition: `${SPRITE_SHEET.idleDownX}px ${SPRITE_SHEET.idleDownY}px`,
        }}
      />
      <span className="map-agent-name">
        {agent.full_name.split(" ")[0]}
        {stale && lastSeen ? ` · ${lastSeen}` : ""}
      </span>
    </button>
  );
}
