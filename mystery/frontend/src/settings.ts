// Player presentation preferences (cosmetic only, persisted per browser).

const CINEMATICS_KEY = "mystery_cinematics";

/** User preference, ignoring the OS-level reduced-motion setting. */
export function cinematicsPref(): boolean {
  return localStorage.getItem(CINEMATICS_KEY) !== "off";
}

export function setCinematicsPref(on: boolean): void {
  localStorage.setItem(CINEMATICS_KEY, on ? "on" : "off");
}

/** Whether cinematic transitions should actually play right now. */
export function cinematicsEnabled(): boolean {
  if (!cinematicsPref()) return false;
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return false;
  return true;
}
