import type { CSSProperties } from "react";
import type { CaseWeather } from "../types";

/**
 * Player-safe environmental dressing for authored cases. These effects are
 * deliberately cosmetic: no particle points at a clue, person, or route.
 */

type RainDropStyle = CSSProperties & { ["--rain-x"]: string; ["--rain-delay"]: string; ["--rain-duration"]: string; ["--rain-length"]: string };
type RainDrop = { depth: "far" | "mid" | "near"; style: RainDropStyle };

// A fixed field prevents drops from popping to new positions on a replay
// render. The uneven distribution and three depths keep it from reading as a
// scrolling pattern of parallel lines.
const RAIN_DROPS: RainDrop[] = Array.from({ length: 58 }, (_, index) => {
  const random = (salt: number) => ((index * 37 + salt * 71 + index * index * 13) % 101) / 100;
  const depth = index % 9 === 0 ? "near" : index % 3 === 0 ? "mid" : "far";
  const duration = depth === "near" ? 0.72 + random(1) * 0.22 : depth === "mid" ? 1.02 + random(1) * 0.3 : 1.32 + random(1) * 0.42;
  const length = depth === "near" ? 10 + random(2) * 7 : depth === "mid" ? 6 + random(2) * 5 : 3 + random(2) * 4;
  return {
    depth,
    style: {
      "--rain-x": `${-4 + random(3) * 108}%`,
      "--rain-delay": `${-(random(4) * duration).toFixed(2)}s`,
      "--rain-duration": `${duration.toFixed(2)}s`,
      "--rain-length": `${length.toFixed(1)}px`,
    },
  };
});
export default function CaseAtmosphere({
  caseId,
  weather,
  scope = "map",
  locationId,
}: {
  caseId: string;
  weather?: CaseWeather;
  scope?: "map" | "place";
  locationId?: string;
}) {
  // Existing authored wet-dawn cases retain their treatment until their
  // metadata is re-saved. Every newly generated case supplies weather.
  const activeWeather = weather ?? ((caseId === "case_005" || caseId === "case_010")
    ? { condition: "rain", intensity: "moderate", wind: "breezy" } as const
    : { condition: "overcast", intensity: "light", wind: "calm" } as const);

  // The map is an exterior overview. Individual search illustrations may be
  // indoors, so keep weather outside rather than laying rain over rooms.
  const exteriorPlaceIds = new Set([
    "loc_village_square",
    "loc_rear_alley",
    "loc_owen_house",
    "loc_back_lane",
  ]);
  const isExterior = scope === "map" || (locationId != null && exteriorPlaceIds.has(locationId));
  if (!isExterior) return null;

  // Case 010 shares the weather and village, but its storage-room murder has
  // no fire: reserve smoke for Case 005's actual discovery scene.
  const smoke = caseId === "case_005" && locationId === "loc_rear_alley";
  const rain = activeWeather.condition === "rain" || activeWeather.condition === "storm";
  const snow = activeWeather.condition === "snow";
  const mist = ["rain", "storm", "fog", "slush"].includes(activeWeather.condition);
  const clouds = activeWeather.condition !== "clear";
  const wind = activeWeather.condition === "wind" || activeWeather.condition === "storm" || activeWeather.wind !== "calm";
  return (
    <div
      className={`case-atmosphere case-atmosphere-${scope} weather-${activeWeather.condition} intensity-${activeWeather.intensity} wind-${activeWeather.wind}${smoke ? " has-smoke" : ""}`}
      aria-hidden="true"
    >
      {clouds && <><span className="case-weather-cloud cloud-one" /><span className="case-weather-cloud cloud-two" /></>}
      {mist && <><span className="case-weather-mist mist-one" /><span className="case-weather-mist mist-two" /></>}
      {rain && <div className="case-weather-rain">{RAIN_DROPS.map(({ depth, style }, index) => <span key={index} className={`case-weather-drop is-${depth}`} style={style} />)}</div>}
      {snow && <div className="case-weather-snow">{RAIN_DROPS.map(({ depth, style }, index) => <span key={index} className={`case-weather-flake is-${depth}`} style={style} />)}</div>}
      {wind && <div className="case-weather-gusts"><span /><span /><span /></div>}
      {activeWeather.condition === "clear" && <span className="case-weather-sun" />}
      {activeWeather.condition === "slush" && <span className="case-weather-slush" />}
      {activeWeather.condition === "storm" && <span className="case-weather-lightning" />}
      {smoke && <span className="case-weather-smoke" />}
    </div>
  );
}
