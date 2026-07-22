/**
 * Player-safe environmental dressing for authored cases.  These effects are
 * deliberately cosmetic: no particle points at a clue, person, or route.
 */
export default function CaseAtmosphere({
  caseId,
  scope = "map",
  locationId,
}: {
  caseId: string;
  scope?: "map" | "place";
  locationId?: string;
}) {
  if (caseId !== "case_005" && caseId !== "case_010") return null;

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
  return (
    <div
      className={`case-atmosphere case-atmosphere-${scope}${smoke ? " has-smoke" : ""}`}
      aria-hidden="true"
    >
      <span className="case-weather-cloud cloud-one" />
      <span className="case-weather-cloud cloud-two" />
      <span className="case-weather-mist mist-one" />
      <span className="case-weather-mist mist-two" />
      <span className="case-weather-rain" />
      {smoke && <span className="case-weather-smoke" />}
    </div>
  );
}
