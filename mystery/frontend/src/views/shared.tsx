import type { ClaimPublic, CluePublic } from "../types";
import { useWorld } from "../App";

export function ClueCard({ clue, isNew }: { clue: CluePublic; isNew?: boolean }) {
  return (
    <div className={`clue-card ${isNew ? "new" : ""}`}>
      <div className="clue-head">
        <strong>{clue.title}</strong>
        <span className={`badge strength-${clue.strength}`}>{clue.strength}</span>
        {clue.ambiguity === "high" && <span className="badge ambiguous">ambiguous</span>}
        {isNew && <span className="badge new">new</span>}
      </div>
      <p>{clue.description}</p>
    </div>
  );
}

export function ClaimRow({ claim }: { claim: ClaimPublic }) {
  const { agentName, locationName } = useWorld();
  return (
    <div className="claim-row">
      <span className={`badge status-${claim.player_known_status}`}>
        {claim.player_known_status}
      </span>
      <span className="claim-text">
        <strong>{agentName(claim.speaker_agent_id)}:</strong> {claim.claim_text}
      </span>
      <span className="muted small">
        {claim.time_reference ?? ""}
        {claim.location_reference_id ? ` · ${locationName(claim.location_reference_id)}` : ""}
      </span>
    </div>
  );
}
