import type { MapAgent } from "../types";

const PAWN_FINISHES = [
  "brass",
  "verdigris",
  "slate",
  "umber",
  "ivory",
  "oxblood",
  "cobalt",
] as const;

function pawnFinish(agentId: string) {
  let value = 0;
  for (let i = 0; i < agentId.length; i += 1) value = (value * 31 + agentId.charCodeAt(i)) >>> 0;
  return PAWN_FINISHES[value % PAWN_FINISHES.length];
}

function pawnMonogram(name: string) {
  const words = name.trim().split(/\s+/);
  return words.length > 1
    ? `${words[0][0]}${words[words.length - 1]?.[0] ?? ""}`
    : words[0]?.slice(0, 2) ?? "?";
}

// The village map uses engraved investigator's pawns rather than character
// sprites. The finish is stable per agent, while the monogram and name keep
// every marker quickly identifiable without turning the map into an RPG.
export default function AgentSprite({
  agent,
  x,
  y,
  size,
  zoomCompensation = 1,
  stale,
  lastSeen,
  onClick,
}: {
  agent: MapAgent;
  x: number;
  y: number;
  size: { width: number; height: number };
  zoomCompensation?: number;
  stale: boolean;
  lastSeen: string | null;
  onClick?: () => void;
}) {
  const title = agent.is_background
    ? `${agent.full_name} — ${agent.occupation}`
    : stale && lastSeen
      ? `${agent.full_name} — last seen ${lastSeen}`
      : agent.full_name;
  const finish = agent.is_victim ? "victim" : pawnFinish(agent.agent_id);
  return (
    <button
      className={`map-agent ${agent.is_background ? "background-agent" : ""} ${stale ? "stale" : ""} ${agent.is_victim ? "victim" : ""}`}
      style={{
        left: x,
        top: y,
        transform: "translate(-50%, -60%)",
        width: size.width,
        height: size.height,
      }}
      title={title}
      onClick={onClick}
      data-agent-id={agent.agent_id}
    >
      <span
        className={`map-agent-pawn finish-${finish}`}
        style={{ width: size.width, height: size.height }}
        aria-hidden="true"
      >
        <span className="map-agent-pawn-cap" />
        <span className="map-agent-pawn-face">{pawnMonogram(agent.full_name)}</span>
        <span className="map-agent-pawn-base" />
      </span>
      <span
        className="map-agent-name"
        style={{
          position: "absolute",
          top: "100%",
          left: "50%",
          transform: `translate(-50%, 0) scale(${zoomCompensation})`,
          transformOrigin: "top center",
          marginTop: "2px",
          display: "inline-block",
        }}
      >
        {agent.full_name.split(" ")[0]}
        {stale && lastSeen ? ` · ${lastSeen}` : ""}
      </span>
    </button>
  );
}
