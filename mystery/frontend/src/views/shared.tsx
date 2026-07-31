import { useRef, useState } from "react";
import type { ClaimPublic, CluePublic } from "../types";
import { useUiNav, useWorld } from "../App";
import { evidenceArt } from "../evidenceArt";
import { sfx } from "../sfx";

export function ClueCard({ clue, isNew }: { clue: CluePublic; isNew?: boolean }) {
  const { jumpToMap } = useUiNav();
  const { caseOverview, agentName, locationName } = useWorld();
  const mapLocationId: string | undefined = clue.linked_location_ids[0];
  const mapEventId: string | undefined = clue.linked_event_ids[0];
  const evidenceImage = evidenceArt(caseOverview?.case_id, clue.clue_id);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const linkedPerson = clue.linked_agent_ids[0] ? agentName(clue.linked_agent_ids[0]) : null;
  const linkedPlace = mapLocationId ? locationName(mapLocationId) : null;
  const confidence = clue.reliability >= 0.85 ? "high" : clue.reliability >= 0.6 ? "moderate" : "low";
  const sourceLabel = ["physical_evidence", "document", "object_trail"].includes(clue.clue_type)
    ? "Direct evidence"
    : ["witness_statement", "confession"].includes(clue.clue_type)
      ? "Testimony"
      : clue.clue_type === "observation"
        ? "Observation"
        : "Lead";
  const testPrompt = linkedPerson && linkedPlace
    ? `Does ${linkedPerson}'s account fit what this clue connects to ${linkedPlace}?`
    : linkedPerson
      ? `Which part of ${linkedPerson}'s account could this clue test?`
      : linkedPlace
        ? `Who could confirm what happened at ${linkedPlace}?`
        : "Which statement or timeline moment could this clue test?";
  return (
    <div className={`clue-card ${isNew ? "new" : ""}`}>
      {evidenceImage && (
        <button
          className="evidence-plate"
          type="button"
          onClick={() => {
            sfx.evidenceInspect();
            setEvidenceOpen(true);
          }}
        >
          <img src={evidenceImage} alt="" />
          <span>Examine recovered evidence</span>
        </button>
      )}
      <div className="clue-head">
        <strong>{clue.title}</strong>
        <span className={`badge strength-${clue.strength}`}>{clue.strength}</span>
        {clue.ambiguity === "high" && <span className="badge ambiguous">ambiguous</span>}
        {isNew && <span className="badge new">new</span>}
        {(mapLocationId || mapEventId) && (
          <button
            className="clue-map-link"
            title="View on the map"
            onClick={() => {
              sfx.mapSelect();
              jumpToMap({ locationId: mapLocationId, eventId: mapEventId });
            }}
          >
            🗺 map
          </button>
        )}
      </div>
      <div className="clue-confidence" title="A clue's source and reliability are not a verdict; compare it with other facts.">
        <span className={`clue-source ${sourceLabel.toLowerCase().replace(" ", "-")}`}>{sourceLabel}</span>
        <span>{confidence} confidence</span>
      </div>
      <p>{clue.description}</p>
      <p className="clue-test-prompt"><span>Detective's question</span>{testPrompt}</p>
      {evidenceImage && evidenceOpen && (
        <EvidenceViewer title={clue.title} imageUrl={evidenceImage} onClose={() => setEvidenceOpen(false)} />
      )}
    </div>
  );
}

function EvidenceViewer({ title, imageUrl, onClose }: { title: string; imageUrl: string; onClose: () => void }) {
  const [rotation, setRotation] = useState(0);
  const startX = useRef<number | null>(null);
  const startRotation = useRef(0);
  return (
    <div className="evidence-viewer-backdrop" role="presentation" onClick={onClose}>
      <section className="evidence-viewer" role="dialog" aria-modal="true" aria-label={`Examine ${title}`} onClick={(event) => event.stopPropagation()}>
        <div className="evidence-viewer-head">
          <div><span>Evidence examination</span><h3>{title}</h3></div>
          <button type="button" onClick={() => { sfx.click(); onClose(); }}>Close</button>
        </div>
        <div
          className="evidence-viewer-stage"
          onPointerDown={(event) => { startX.current = event.clientX; startRotation.current = rotation; event.currentTarget.setPointerCapture(event.pointerId); }}
          onPointerMove={(event) => { if (startX.current !== null) setRotation(startRotation.current + (event.clientX - startX.current) / 3); }}
          onPointerUp={() => { startX.current = null; }}
        >
          <img src={imageUrl} alt={title} style={{ transform: `rotate(${rotation}deg)` }} />
          <span className="evidence-viewer-hint">Drag to rotate the evidence plate</span>
        </div>
      </section>
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
