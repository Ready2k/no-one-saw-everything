import { useEffect, useState } from "react";

// Phase D (spec 14): frontend-only staged reveal for challenges whose
// existing engine outcome represents a caught contradiction —
// contradiction_locked, or partial_admission (story changes under evidence
// and an unresolved contradiction note is created). No new classification;
// this only selects among outcomes the backend already returns. The sound
// cue comes from the existing lastChallenge effect in Suspects.tsx; the
// deterministic outcome text is rendered unchanged beneath/after it.

const COLLIDE_MS = 1100; // cards slam together, then the outcome reveals

export default function ContradictionBeat({
  claimText,
  evidenceText,
  outcomeText,
  outcomeLabel,
  onDone,
}: {
  claimText: string;
  evidenceText: string;
  outcomeText: string;
  outcomeLabel: string;
  onDone: () => void;
}) {
  const [phase, setPhase] = useState<"collide" | "outcome">("collide");

  useEffect(() => {
    const timer = setTimeout(() => setPhase("outcome"), COLLIDE_MS);
    return () => clearTimeout(timer);
  }, []);

  // Esc always dismisses; a click advances, then dismisses.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDone();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDone]);

  return (
    <div
      className="contradiction-beat"
      onClick={() => (phase === "outcome" ? onDone() : setPhase("outcome"))}
      title="Click to skip"
    >
      <div className="beat-cards">
        <div className="beat-card beat-claim">
          <span className="beat-label">They claimed</span>
          <p>“{claimText}”</p>
        </div>
        <div className="beat-vs">✕</div>
        <div className="beat-card beat-evidence">
          <span className="beat-label">But you know</span>
          <p>{evidenceText}</p>
        </div>
      </div>
      {phase === "outcome" && (
        <div className="beat-outcome">
          <span className="badge outcome">{outcomeLabel}</span>
          <p>{outcomeText}</p>
          <button className="primary" onClick={onDone}>
            Continue
          </button>
        </div>
      )}
    </div>
  );
}
