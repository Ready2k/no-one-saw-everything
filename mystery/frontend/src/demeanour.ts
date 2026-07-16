// How a suspect's composure reads to the player, derived from the cumulative pressure the
// interrogation has applied (0 = fully composed, 1 = breaking). Purely presentational: this maps
// the same 0-1 value the portrait/mugshot use into words and a meter, and never feeds game logic.
//
// Framed as the suspect's COMPOSURE, not the detective's "pressure": the bar drains as you corner
// them, so the player can watch it fall toward empty and feel a break coming — which the old
// single "pressure ↑" tick never conveyed.

export interface Demeanour {
  /** One-word read of how they are holding up. */
  label: string;
  /** Coarse band, for colour/CSS. */
  level: "composed" | "guarded" | "rattled" | "cornered" | "breaking";
  /** Composure remaining, 0-100, for the meter width. */
  composure: number;
  /** A short line describing what the player is seeing. */
  hint: string;
}

export function demeanourFor(pressure: number, lastShift?: string | null): Demeanour {
  const composure = Math.round((1 - Math.max(0, Math.min(1, pressure))) * 100);

  // A fresh emotional beat from the last answer overrides the steady-state read for one turn —
  // "floundering" or "broken" is more truthful in the moment than whatever the meter says.
  const shift = (lastShift ?? "").toLowerCase();
  if (shift === "broken" || shift === "shattered") {
    return { label: "Breaking", level: "breaking", composure, hint: "They have stopped holding it together." };
  }
  if (shift === "floundering") {
    return { label: "Floundering", level: "cornered", composure, hint: "They are contradicting themselves." };
  }

  if (pressure >= 0.85) {
    return { label: "Breaking", level: "breaking", composure, hint: "One more push and they will give." };
  }
  if (pressure >= 0.6) {
    return { label: "Cornered", level: "cornered", composure, hint: "Their story is coming apart." };
  }
  if (pressure >= 0.35) {
    return { label: "Rattled", level: "rattled", composure, hint: "You have got under their skin." };
  }
  if (pressure >= 0.12) {
    return { label: "Guarded", level: "guarded", composure, hint: "They are choosing their words." };
  }
  return { label: "Composed", level: "composed", composure, hint: "Nothing you have said has touched them yet." };
}
