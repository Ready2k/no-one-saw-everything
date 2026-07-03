import { useState } from "react";
import type { AgentPublic } from "../types";

// Pressure is a 0-1 cumulative value from the session (see backend
// session.py). Expressions switch at these thresholds; tune freely —
// they are cosmetic and never feed back into game logic.
export const DEFENSIVE_THRESHOLD = 0.3;
export const CRACKING_THRESHOLD = 0.7;

export type ExpressionState = "calm" | "defensive" | "cracking";

export function expressionForPressure(pressure: number): ExpressionState {
  if (pressure >= CRACKING_THRESHOLD) return "cracking";
  if (pressure >= DEFENSIVE_THRESHOLD) return "defensive";
  return "calm";
}

/** Best available asset for the desired expression: cracking > defensive > calm. */
function portraitAsset(agent: AgentPublic, expression: ExpressionState): string | null {
  const art = agent.portrait_art;
  if (!art) return null;
  if (expression === "cracking" && art.cracking) return art.cracking;
  if (expression !== "calm" && art.defensive) return art.defensive;
  return art.calm ?? art.defensive ?? art.cracking;
}

export default function Portrait({
  agent,
  pressure = 0,
  size = "small",
}: {
  agent: AgentPublic;
  pressure?: number;
  size?: "small" | "large";
}) {
  const [broken, setBroken] = useState(false);
  const expression = expressionForPressure(pressure);
  const asset = broken ? null : portraitAsset(agent, expression);
  if (!asset) {
    // Legacy fallback: emoji string rendered as text, exactly as before.
    return <span className={`portrait portrait-${size}`}>{agent.portrait}</span>;
  }
  return (
    <img
      className={`portrait portrait-img portrait-${size} expression-${expression}`}
      src={asset}
      alt={`${agent.full_name} (${expression})`}
      onError={() => setBroken(true)}
    />
  );
}
