import { useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type { InspectResult } from "../types";
import { ClueCard } from "./shared";

export default function Places() {
  const { locations } = useWorld();
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<InspectResult | null>(null);
  const [busy, setBusy] = useState(false);

  const inspect = async (locationId: string) => {
    setSelected(locationId);
    setBusy(true);
    try {
      setResult(await api.inspect(locationId));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="places">
      <div className="place-list panel">
        <h2>Search the village</h2>
        <p className="muted small">
          Inspect a place to search it for physical evidence. Some things only
          make sense once you know what to look for.
        </p>
        {locations.map((l) => (
          <button
            key={l.location_id}
            className={`place ${selected === l.location_id ? "active" : ""}`}
            onClick={() => inspect(l.location_id)}
          >
            <span className="place-name">{l.name}</span>
            {l.visibility_type === "private" && (
              <span className="badge ambiguous">private</span>
            )}
          </button>
        ))}
      </div>
      <div className="place-detail">
        {!result && <p className="muted">Pick a location to search it.</p>}
        {busy && <p className="muted">Searching…</p>}
        {result && !busy && (
          <>
            <h2>{result.location.name}</h2>
            <p>{result.location.description}</p>
            {result.new_clues.length > 0 && (
              <>
                <h3>Found</h3>
                {result.new_clues.map((c) => (
                  <ClueCard key={c.clue_id} clue={c} isNew />
                ))}
              </>
            )}
            {result.known_clues.length > 0 && (
              <>
                <h3>Already catalogued</h3>
                {result.known_clues.map((c) => (
                  <ClueCard key={c.clue_id} clue={c} />
                ))}
              </>
            )}
            {result.new_clues.length === 0 && result.known_clues.length === 0 && (
              <p className="muted">Nothing of obvious interest here.</p>
            )}
            {result.hint && <p className="hint-text">{result.hint}</p>}
          </>
        )}
      </div>
    </div>
  );
}
