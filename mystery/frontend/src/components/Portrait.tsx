import { useState } from "react";
import type { AgentPublic } from "../types";
import { SPRITE_SHEET } from "../map/mapAssets";
import { lifelikeCalmPortrait } from "../characterArt";

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
  const lifelike = lifelikeCalmPortrait(agent);
  if (lifelike) return lifelike;
  const art = agent.portrait_art;
  if (!art) return null;
  if (expression === "cracking" && art.cracking) return art.cracking;
  if (expression !== "calm" && art.defensive) return art.defensive;
  return art.calm ?? art.defensive ?? art.cracking;
}

// The idle facing-down frame sits at column 1, row 0 of the 3×4 sprite sheet.
const IDLE_COL = SPRITE_SHEET.idleCol; // 1
const IDLE_ROW = SPRITE_SHEET.idleRow; // 0
const SHEET_COLS = SPRITE_SHEET.cols;  // 3
const SHEET_ROWS = SPRITE_SHEET.rows;  // 4

/**
 * Render a div that crops just the idle-down frame out of a sprite sheet,
 * sized to fill the portrait slot exactly.
 */
function SpritePortrait({
  spriteAsset,
  name,
  size,
}: {
  spriteAsset: string;
  name: string;
  size: "small" | "large";
}) {
  // The sprite sheet's idle col is at col-index 1 of 3; we want to show only
  // that cell. We do this via background-size + background-position on a div.
  return (
    <span
      className={`portrait portrait-sprite portrait-${size}`}
      title={name}
      role="img"
      aria-label={name}
      style={{
        backgroundImage: `url(/map/sprites/${spriteAsset})`,
        backgroundSize: `${SHEET_COLS * 100}% ${SHEET_ROWS * 100}%`,
        backgroundPosition: `${(IDLE_COL / (SHEET_COLS - 1)) * 100}% ${(IDLE_ROW / (SHEET_ROWS - 1)) * 100}%`,
        backgroundRepeat: "no-repeat",
        display: "inline-block",
        imageRendering: "pixelated",
      }}
    />
  );
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

  // Priority 1: explicit portrait_art image
  if (asset) {
    return (
      <img
        className={`portrait portrait-img portrait-${size} expression-${expression}`}
        src={asset}
        alt={`${agent.full_name} (${expression})`}
        onError={() => setBroken(true)}
      />
    );
  }

  // Priority 2: sprite sheet idle frame (character image, not emoji)
  if (agent.sprite_asset && !broken) {
    return (
      <SpritePortrait
        spriteAsset={agent.sprite_asset}
        name={agent.full_name}
        size={size}
      />
    );
  }

  // Priority 3: legacy emoji fallback — a generic themed icon (☕, 🧣, 📦...),
  // not a distinguishing likeness. Every call site pairs this with the
  // character's name as visible text, so it's decorative: hidden from
  // assistive tech rather than announced as if it identified anyone.
  return (
    <span className={`portrait portrait-${size}`} aria-hidden="true">
      {agent.portrait}
    </span>
  );
}
