import { useEffect, useRef, useState } from "react";
import { demeanourFor } from "../demeanour";

/**
 * A suspect's composure, made visible. The bar drains as the interrogation applies pressure, so
 * the player can see they are getting somewhere and sense a break coming — replacing the old,
 * fleeting "pressure ↑" text with something they can actually read.
 *
 * `pressure` is the same 0-1 session value the mugshot/portrait use. `lastShift` is the emotional
 * beat from the most recent answer, which colours the read for one turn. Cosmetic throughout.
 */
export default function ComposureMeter({
  name,
  pressure,
  lastShift,
}: {
  name: string;
  pressure: number;
  lastShift?: string | null;
}) {
  const d = demeanourFor(pressure, lastShift);

  // Flash the meter when composure drops, so a hit registers even if the player's eyes are on
  // the transcript.
  const prev = useRef(pressure);
  const [justDropped, setJustDropped] = useState(false);
  useEffect(() => {
    if (pressure > prev.current + 0.001) {
      setJustDropped(true);
      const t = setTimeout(() => setJustDropped(false), 900);
      prev.current = pressure;
      return () => clearTimeout(t);
    }
    prev.current = pressure;
  }, [pressure]);

  return (
    <div className={`composure-meter level-${d.level}${justDropped ? " composure-hit" : ""}`}>
      <div className="composure-head">
        <span className="composure-label">{d.label}</span>
        <span className="composure-readout muted small">composure {d.composure}%</span>
      </div>
      <div
        className="composure-track"
        role="meter"
        aria-valuenow={d.composure}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${name}'s composure`}
      >
        <div className="composure-fill" style={{ width: `${d.composure}%` }} />
      </div>
      <p className="composure-hint muted small">{d.hint}</p>
    </div>
  );
}
