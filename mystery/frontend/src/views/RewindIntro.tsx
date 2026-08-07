import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { api, minutes, timeOfDayLabel } from "../api";
import { useWorld } from "../App";
import type { EventPublic, LocationPublic, MapReplayData } from "../types";
import { getMapInfo } from "../map/mapInfo";
import MapCrop from "../components/MapCrop";
import Portrait from "../components/Portrait";
import { audioManager } from "../audio";
import { sceneArtFor } from "../sceneArt";

// The rewind briefing plays once per case; cleared alongside the discovery
// intro when a case is reopened or switched (see App.tsx).
const briefingKey = (caseId: string) => `mystery_rewind_briefing_${caseId}`;

export function rewindBriefingSeen(caseId: string): boolean {
  return !!localStorage.getItem(briefingKey(caseId));
}

export function markRewindBriefingSeen(caseId: string): void {
  localStorage.setItem(briefingKey(caseId), "1");
}

export function clearRewindBriefingSeen(caseId: string): void {
  localStorage.removeItem(briefingKey(caseId));
}

// ---------------------------------------------------------------------------

interface PlaceReconstruction {
  id: string;
  displayName: string;
  matchedLine: string;
  exteriorSrc: string;
  interiorSrc: string;
  focus: { x: number; y: number };
  description: string;
}

interface SceneArtwork {
  src: string;
  position?: string;
}

interface WitnessReplay {
  frames: Array<{ src: string; label: string; position?: string }>;
  witness: string;
  observation: string;
  figureLabel: string;
  direction: "toward" | "away";
}

type Beat =
  | { kind: "title" }
  | { kind: "place-reconstruct"; place: PlaceReconstruction }
  | { kind: "glimpse"; event: EventPublic }
  | { kind: "cast" }
  | { kind: "brief" };

const CASE_001_ART = "/art/case_001";
const CASE_001_INTRO_ART = `${CASE_001_ART}/intro`;
const CASE_002_ART = "/art/case_002";
const CASE_002_INTRO_ART = `${CASE_002_ART}/intro`;
const CASE_003_ART = "/art/case_003";
const CASE_003_INTRO_ART = `${CASE_003_ART}/intro`;
const CASE_004_ART = "/art/case_004";
const CASE_004_INTRO_ART = `${CASE_004_ART}/intro`;
const CASE_005_ART = "/art/case_005";
const CASE_005_INTRO_ART = `${CASE_005_ART}/intro`;
const CASE_010_ART = "/art/case_010";
const UNIFIED_VILLAGE_ART = "/art/town/shared_hd/unified_village_dawn_v1.avif";
const CASE_003_MAP_ART = "/art/case_003/map/case_003_village_map_afternoon.avif";
const CASE_005_MAP_ART = "/art/case_005/map/case_005_village_map_dawn.avif";
const CASE_006_MAP_ART = "/art/case_006/map/case_006_village_map_night.avif";
const CASE_007_MAP_ART = "/art/case_007/map/case_007_village_map_lantern_fair.avif";
// These are cinematic reconstructions of player-visible witness moments, not
// hidden camera footage.  A figure stays anonymous unless the public event
// itself names them, and the motion is illustrative rather than a new clue.
const WITNESS_REPLAYS: Record<string, Record<string, WitnessReplay>> = {
  case_003: {
    ev_0705_nadia_checks_elias: {
      frames: [
        { src: `${CASE_001_ART}/village_clinic_investigation_v2.avif`, label: "the bench", position: "50% 8%" },
        { src: `${CASE_001_ART}/village_clinic_investigation_v2.avif`, label: "a navy sleeve", position: "50% 20%" },
        { src: `${CASE_001_ART}/village_clinic_investigation_v2.avif`, label: "the organiser", position: "50% 34%" },
        { src: `${CASE_001_ART}/village_clinic_investigation_v2.avif`, label: "a flask", position: "50% 48%" },
        { src: `${CASE_001_ART}/village_clinic_investigation_v2.avif`, label: "her hand withdraws", position: "50% 64%" },
        { src: `${CASE_001_ART}/village_clinic_investigation_v2.avif`, label: "rain on stone", position: "50% 82%" },
      ],
      witness: "Ruth's view across the square",
      observation: "She saw the nurse place something small in Elias's hand. The rest is only the shape the moment left behind.",
      figureLabel: "the clinic nurse",
      direction: "away",
    },
  },
  case_006: {
    ev_2000_priya_passes: {
      frames: [
        { src: `${CASE_001_ART}/marcus_house_investigation_v4.avif`, label: "the doorway", position: "50% 8%" },
        { src: `${CASE_001_ART}/marcus_house_investigation_v4.avif`, label: "a pale coat", position: "50% 23%" },
        { src: `${CASE_001_ART}/marcus_house_investigation_v4.avif`, label: "wet cobbles", position: "50% 39%" },
        { src: `${CASE_001_ART}/marcus_house_investigation_v4.avif`, label: "her turned shoulder", position: "50% 54%" },
        { src: `${CASE_001_ART}/marcus_house_investigation_v4.avif`, label: "the house light", position: "50% 69%" },
        { src: `${CASE_001_ART}/marcus_house_investigation_v4.avif`, label: "the empty square", position: "50% 84%" },
      ],
      witness: "Priya's pass through the square",
      observation: "Isabella leaves furious — a compelling sight, but two hours before Marcus's death. A memory can make a red herring feel decisive.",
      figureLabel: "a departing woman",
      direction: "away",
    },
  },
  case_007: {
    ev_2044_grey_coat: {
      frames: [
        { src: `${CASE_001_ART}/rear_alley_investigation_v2.avif`, label: "Ben's van", position: "50% 8%" },
        { src: `${CASE_001_ART}/rear_alley_investigation_v2.avif`, label: "kitchen light", position: "50% 22%" },
        { src: `${CASE_001_ART}/rear_alley_investigation_v2.avif`, label: "a grey coat", position: "50% 38%" },
        { src: `${CASE_001_ART}/rear_alley_investigation_v2.avif`, label: "the raised collar", position: "50% 53%" },
        { src: `${CASE_001_ART}/rear_alley_investigation_v2.avif`, label: "a hand at the door", position: "50% 69%" },
        { src: `${CASE_001_ART}/rear_alley_investigation_v2.avif`, label: "lanterns beyond", position: "50% 84%" },
      ],
      witness: "Ben's view from the delivery van",
      observation: "A long grey coat crossed from the cafe kitchen to the bookshop's rear door. Ben never saw a face.",
      figureLabel: "grey-coated figure",
      direction: "toward",
    },
  },
  case_005: {
    ev_0700_nadia_glance: {
      frames: [
        { src: `${CASE_005_ART}/rewind/nadia_alley_glance_empty_hd.avif`, label: "the square" },
        { src: `${CASE_005_ART}/rewind/grey_jacket_blur_hd.avif`, label: "a grey jacket" },
        { src: `${CASE_005_ART}/rewind/elias_tea_ripple_hd.avif`, label: "tea ripples" },
        { src: `${CASE_005_ART}/rewind/wet_crate_ember_hd.avif`, label: "an ember fails" },
        { src: `${CASE_005_ART}/rewind/yard_gate_dawn_hd.avif`, label: "the yard gate" },
        { src: `${CASE_005_ART}/back_lane_dawn_hd.avif`, label: "then nothing" },
      ],
      witness: "Nadia's line of sight",
      observation: "A passing figure turns into the alley. From the square, that is all she can make out.",
      figureLabel: "unidentified passer-by",
      direction: "away",
    },
  },
  case_010: {
    ev_0747_blue_coat: {
      frames: [
        { src: `${CASE_010_ART}/rewind/blue_coat_glimpse_empty_hd.avif`, label: "the rear passage" },
        { src: `${CASE_010_ART}/rewind/blue_coat_blur_hd.avif`, label: "blue at the window" },
        { src: `${CASE_010_ART}/rewind/rear_door_shadow_hd.avif`, label: "a shadow inside" },
        { src: `${CASE_010_ART}/rewind/mop_bucket_ripple_hd.avif`, label: "water trembles" },
        { src: `${CASE_010_ART}/rewind/rear_door_glint_hd.avif`, label: "a glint by the door" },
        { src: `${CASE_010_ART}/village_square_dawn_hd.avif`, label: "the empty fountain" },
      ],
      witness: "Ben's glimpse from the bookshop end",
      observation: "A blue-coated figure moves toward the cafe's rear door. The face never comes into view.",
      figureLabel: "blue-coated figure",
      direction: "toward",
    },
  },
};

export function hasWitnessReplay(caseId: string, eventId: string): boolean {
  return !!WITNESS_REPLAYS[caseId]?.[eventId];
}

const WITNESS_TESTIMONY: Record<string, Record<string, { clueId: string; eventId: string }>> = {
  case_003: {
    agent_ruth: { clueId: "clue_nadia_pill_handoff", eventId: "ev_0705_nadia_checks_elias" },
  },
  case_006: {
    agent_priya: { clueId: "clue_priya_sees_isabella", eventId: "ev_2000_priya_passes" },
  },
  case_007: {
    agent_ben: { clueId: "clue_ben_grey_coat", eventId: "ev_2044_grey_coat" },
  },
  case_005: {
    agent_nadia: { clueId: "clue_nadia_sees_owen_alley", eventId: "ev_0700_nadia_glance" },
  },
  case_010: {
    agent_ben: { clueId: "clue_ben_sighting", eventId: "ev_0747_blue_coat" },
  },
};

/** The reconstruction becomes available only once the witness has actually
 * shared the authored sighting in interview. */
export function witnessReplayForTestimony(
  caseId: string,
  agentId: string,
  revealedClueIds: string[]
): string | null {
  const testimony = WITNESS_TESTIMONY[caseId]?.[agentId];
  return testimony && revealedClueIds.includes(testimony.clueId) ? testimony.eventId : null;
}

const INTRO_ART_OVERRIDES: Record<string, string> = {
  [`${CASE_001_ART}/fountain_dawn_investigation_v5.avif`]: `${CASE_001_INTRO_ART}/fountain_dawn_investigation_v5_intro.avif`,
  [`${CASE_001_ART}/reed_bell_bookshop_investigation_v2.avif`]: `${CASE_001_INTRO_ART}/reed_bell_bookshop_investigation_v2_intro.avif`,
  [`${CASE_001_ART}/bookshop_back_room_investigation_v2.avif`]: `${CASE_001_INTRO_ART}/bookshop_back_room_investigation_v2_intro.avif`,
  [`${CASE_001_ART}/village_clinic_investigation_v2.avif`]: `${CASE_001_INTRO_ART}/village_clinic_investigation_v2_intro.avif`,
  [`${CASE_001_ART}/clinic_dispensary_investigation_v2.avif`]: `${CASE_001_INTRO_ART}/clinic_dispensary_investigation_v2_intro.avif`,
  [`${CASE_001_ART}/marcus_study_investigation_v2.avif`]: `${CASE_001_INTRO_ART}/marcus_study_investigation_v2_intro.avif`,
  [`${CASE_001_ART}/mallet_crown_pub_investigation_v2.avif`]: `${CASE_001_INTRO_ART}/mallet_crown_pub_investigation_v2_intro.avif`,
  [`${CASE_001_ART}/ben_flat_investigation_v2.avif`]: `${CASE_001_INTRO_ART}/ben_flat_investigation_v2_intro.avif`,
  [`${CASE_001_ART}/ruth_cottage_investigation_v2.avif`]: `${CASE_001_INTRO_ART}/ruth_cottage_investigation_v2_intro.avif`,
  [`${CASE_001_ART}/solicitors_office_investigation_v2.avif`]: `${CASE_001_INTRO_ART}/solicitors_office_investigation_v2_intro.avif`,
  [`${CASE_001_ART}/rear_alley_investigation_v2.avif`]: `${CASE_001_INTRO_ART}/rear_alley_investigation_v2_intro.avif`,
  [`${CASE_001_ART}/owen_house_yard_investigation_v2.avif`]: `${CASE_001_INTRO_ART}/owen_house_yard_investigation_v2_intro.avif`,
  [`${CASE_001_ART}/hobbs_cafe_investigation_v4.avif`]: `${CASE_001_INTRO_ART}/hobbs_cafe_investigation_v4_intro.avif`,
  [`${CASE_001_ART}/cafe_kitchen_investigation_v4.avif`]: `${CASE_001_INTRO_ART}/cafe_kitchen_investigation_v4_intro.avif`,
  [`${CASE_001_ART}/storage_room_interactive_wide_v1.avif`]: `${CASE_001_INTRO_ART}/storage_room_interactive_wide_v1_intro.avif`,
  [`${CASE_001_ART}/clara_flat_investigation_v4.avif`]: `${CASE_001_INTRO_ART}/clara_flat_investigation_v4_intro.avif`,
  [`${CASE_001_ART}/elias_bench_investigation_v4.avif`]: `${CASE_001_INTRO_ART}/elias_bench_investigation_v4_intro.avif`,
  [`${CASE_001_ART}/elias_house_investigation_v4.avif`]: `${CASE_001_INTRO_ART}/elias_house_investigation_v4_intro.avif`,
  [`${CASE_001_ART}/marcus_house_investigation_v4.avif`]: `${CASE_001_INTRO_ART}/marcus_house_investigation_v4_intro.avif`,
  [`${CASE_001_ART}/nadia_flat_investigation_v4.avif`]: `${CASE_001_INTRO_ART}/nadia_flat_investigation_v4_intro.avif`,
  [`${CASE_001_ART}/priya_flat_investigation_v4.avif`]: `${CASE_001_INTRO_ART}/priya_flat_investigation_v4_intro.avif`,
  [`${CASE_002_ART}/village_square_lunchtime_investigation_v2.avif`]: `${CASE_002_INTRO_ART}/village_square_lunchtime_investigation_v2_intro.avif`,
  [`${CASE_002_ART}/fountain_lunchtime_investigation_v2.avif`]: `${CASE_002_INTRO_ART}/fountain_lunchtime_investigation_v2_intro.avif`,
  [`${CASE_003_ART}/village_square_afternoon_investigation_v2.avif`]: `${CASE_003_INTRO_ART}/village_square_afternoon_investigation_v2_intro.avif`,
  [`${CASE_004_ART}/village_square_midnight_investigation_v2.avif`]: `${CASE_004_INTRO_ART}/village_square_midnight_investigation_v2_intro.avif`,
  [`${CASE_004_ART}/fountain_midnight_investigation_v2.avif`]: `${CASE_004_INTRO_ART}/fountain_midnight_investigation_v2_intro.avif`,
  [`${CASE_004_ART}/fishery_midnight_investigation_v2.avif`]: `${CASE_004_INTRO_ART}/fishery_midnight_investigation_v2_intro.avif`,
  [`${CASE_004_ART}/lovers_lake_midnight_investigation_v2.avif`]: `${CASE_004_INTRO_ART}/lovers_lake_midnight_investigation_v2_intro.avif`,
  [`${CASE_004_ART}/whispering_woodland_midnight_investigation_v2.avif`]: `${CASE_004_INTRO_ART}/whispering_woodland_midnight_investigation_v2_intro.avif`,
  [`${CASE_004_ART}/green_meadow_midnight_investigation_v2.avif`]: `${CASE_004_INTRO_ART}/green_meadow_midnight_investigation_v2_intro.avif`,
  [`${CASE_005_ART}/rear_alley_after_fire_investigation_v2.avif`]: `${CASE_005_INTRO_ART}/rear_alley_after_fire_investigation_v2_intro.avif`,
};

function introAsset(src: string): string {
  return INTRO_ART_OVERRIDES[src] ?? src;
}

function sceneArtwork(
  caseId: string,
  locationId: string,
  locations: LocationPublic[]
): SceneArtwork | null {
  const loc = locations.find((l) => l.location_id === locationId);
  const src = sceneArtFor(caseId, locationId, loc?.illustration);
  return src ? { src: introAsset(src) } : null;
}

function preloadImage(src: string): void {
  const img = new Image();
  img.src = src;
}

const CASE_001_PLACES: PlaceReconstruction[] = [
  {
    id: "hobbs-cafe",
    displayName: "Hobbs Cafe",
    matchedLine: "Hobbs Cafe, matched to the storage room.",
    exteriorSrc: UNIFIED_VILLAGE_ART,
    interiorSrc: `${CASE_001_ART}/storage_room_interactive_wide_v1.avif`,
    focus: { x: 72, y: 32 },
    description:
      "Teal front door, side stair, rear service route. The public cafe image locks to the room no witness could see from the square.",
  },
];

const CASE_004_PLACES: PlaceReconstruction[] = [
  {
    id: "ben-flat",
    displayName: "Ben's Flat",
    matchedLine: "Ben's flat, above the shuttered newsagent.",
    exteriorSrc: CASE_006_MAP_ART,
    interiorSrc: `${CASE_001_ART}/ben_flat_investigation_v2.avif`,
    focus: { x: 16, y: 83 },
    description:
      "Shop dark, papers unsold. A separate stair climbs to the flat above — the only window on the square still lit past midnight.",
  },
  {
    id: "mallet-crown",
    displayName: "The Mallet & Crown",
    matchedLine: "The Mallet & Crown, locked up for the night.",
    exteriorSrc: CASE_006_MAP_ART,
    interiorSrc: `${CASE_001_ART}/mallet_crown_pub_investigation_v2.avif`,
    focus: { x: 23, y: 49 },
    description:
      "Last orders came and went hours ago. The exterior locks to the room Fred Dunmore keeps behind the bar.",
  },
  {
    id: "priya-flat",
    displayName: "Priya's Flat",
    matchedLine: "Priya's flat, curtains drawn.",
    exteriorSrc: CASE_006_MAP_ART,
    interiorSrc: `${CASE_001_ART}/priya_flat_investigation_v4.avif`,
    focus: { x: 33, y: 80 },
    description:
      "Two-storey flats above the square. The reconstruction matches the stair and door witnesses described to the room behind them.",
  },
  {
    id: "owen-house",
    displayName: "Owen Price's House & Yard",
    matchedLine: "Owen's house and workshop yard.",
    exteriorSrc: CASE_006_MAP_ART,
    interiorSrc: `${CASE_001_ART}/owen_house_yard_investigation_v2.avif`,
    focus: { x: 91, y: 54 },
    description:
      "The builder's own yard, tools put away for the night. Nobody has said whether he made it home before the fountain.",
  },
  {
    id: "elias-cottage",
    displayName: "Elias's Cottage",
    matchedLine: "Elias's cottage, bedroom window overlooking the square.",
    exteriorSrc: CASE_006_MAP_ART,
    interiorSrc: `${CASE_001_ART}/elias_house_investigation_v4.avif`,
    focus: { x: 50, y: 80 },
    description:
      "The vantage point the body was found from. The exterior locks to the room with the window that looks straight onto the fountain.",
  },
  {
    id: "village-clinic",
    displayName: "Village Clinic",
    matchedLine: "The Village Clinic, dark until the call came in.",
    exteriorSrc: CASE_006_MAP_ART,
    interiorSrc: `${CASE_001_ART}/village_clinic_investigation_v2.avif`,
    focus: { x: 78, y: 45 },
    description:
      "Nadia Cole's clinic, shuttered for the night. The reconstruction matches the frontage to the reception and exam room within.",
  },
];

const CASE_005_PLACES: PlaceReconstruction[] = [
  {
    id: "case-005-village-alley",
    displayName: "The Village & Rear Alley",
    matchedLine: "Hobbs Cafe, the square, and the alley behind it.",
    exteriorSrc: CASE_005_MAP_ART,
    interiorSrc: `${CASE_005_ART}/rear_alley_after_fire_investigation_v2.avif`,
    focus: { x: 48, y: 55 },
    description:
      "A wet village waking slowly. Behind the cafe, one narrow service route holds the scene the square could not see.",
  },
];

const CASE_003_PLACES: PlaceReconstruction[] = [
  {
    id: "case-003-clinic-bench",
    displayName: "The Clinic & Elias's Bench",
    matchedLine: "The clinic frontage, matched to the bench by the fountain.",
    exteriorSrc: CASE_003_MAP_ART,
    interiorSrc: `${CASE_001_ART}/village_clinic_investigation_v2.avif`,
    focus: { x: 53, y: 38 },
    description:
      "Late afternoon closes around the square. From the clinic door, a short walk reaches the bench where a routine handoff became something else.",
  },
];

const CASE_006_PLACES: PlaceReconstruction[] = [
  {
    id: "case-006-bell-house",
    displayName: "Bell House & the Fireside Room",
    matchedLine: "Marcus Bell's house, matched to the chair by the fire.",
    exteriorSrc: CASE_006_MAP_ART,
    interiorSrc: `${CASE_001_ART}/marcus_house_investigation_v4.avif`,
    focus: { x: 38, y: 18 },
    description:
      "At night the house is one pool of warm light on the square. The public doorstep and the private fireside are one address, not one account.",
  },
];

const CASE_007_PLACES: PlaceReconstruction[] = [
  {
    id: "case-007-fair-alley",
    displayName: "The Lantern Fair & Rear Alley",
    matchedLine: "The lantern-lit square, matched to the unlit service route.",
    exteriorSrc: CASE_007_MAP_ART,
    interiorSrc: `${CASE_001_ART}/rear_alley_investigation_v2.avif`,
    focus: { x: 47, y: 43 },
    description:
      "The fair made the square bright and loud. One narrow alley behind the stalls remained just dark enough for a witness to lose a face.",
  },
];

const CASE_010_PLACES: PlaceReconstruction[] = [
  {
    id: "case-010-village-storage",
    displayName: "Hobbs Cafe & the Storage Room",
    matchedLine: "The same dawn village, with the cafe's rear room sealed off.",
    exteriorSrc: CASE_005_MAP_ART,
    interiorSrc: `${CASE_001_ART}/storage_room_interactive_wide_v1.avif`,
    focus: { x: 57, y: 61 },
    description:
      "Rain slicks the same square and the same cafe windows. Beyond the public room, a service door leads to the quiet storage room where nobody claims to have seen what happened.",
  },
];

// Auto-advance pacing (ms). Cast and brief wait for the player.
const TITLE_HOLD = 4200;
const GLIMPSE_HOLD = 4600;

/** Pick up to four real player-visible moments that tease the period:
 * how it began, something the village couldn't see clearly, the most
 * important visible moment inside the murder window, and the last thing
 * that happened before the body was found. */
export function pickGlimpses(
  events: EventPublic[],
  windowStart: number,
  windowEnd: number,
  preferredEventIds: string[] = []
): EventPublic[] {
  if (events.length === 0) return [];
  const sorted = [...events].sort((a, b) => minutes(a.time) - minutes(b.time));
  const picks = new Map<string, EventPublic>();
  const add = (e: EventPublic | undefined) => {
    if (e) picks.set(e.event_id, e);
  };
  // Optional caller-selected moments may be placed first; the opening rewind
  // does not use this. Witness reconstructions belong to testimony, not a
  // pre-investigation briefing.
  for (const eventId of preferredEventIds) add(sorted.find((e) => e.event_id === eventId));
  add(sorted[0]);
  add(
    [...sorted]
      .filter((e) => e.visibility !== "public")
      .sort((a, b) => b.importance - a.importance)[0]
  );
  add(
    sorted
      .filter((e) => {
        const m = minutes(e.time);
        return m >= windowStart && m <= windowEnd;
      })
      .sort((a, b) => b.importance - a.importance)[0]
  );
  add(sorted[sorted.length - 1]);
  const preferred = preferredEventIds
    .map((eventId) => picks.get(eventId))
    .filter((event): event is EventPublic => !!event);
  const remaining = [...picks.values()]
    .filter((event) => !preferredEventIds.includes(event.event_id))
    .sort((a, b) => minutes(a.time) - minutes(b.time));
  return [...preferred, ...remaining].slice(0, 4);
}

export default function RewindIntro({
  onDone,
  replayEventId,
}: {
  onDone: () => void;
  /** Plays one authored witness montage from the Rewind event list. */
  replayEventId?: string;
}) {
  const { caseOverview: c, agents, locations, locationName } = useWorld();
  const period = timeOfDayLabel(c.sim_start_time);
  const [beatIndex, setBeatIndex] = useState(0);
  const [glimpses, setGlimpses] = useState<EventPublic[]>([]);
  const [mapData, setMapData] = useState<MapReplayData | null>(null);
  const [loaded, setLoaded] = useState(false);

  const windowStart = minutes(c.murder_window[0]);
  const windowEnd = minutes(c.murder_window[1]);

  // The briefing gets its own score; the investigation theme resumes after.
  useEffect(() => {
    audioManager.playAmbient("testimony");
    return () => audioManager.playAmbient("investigation");
  }, []);

  // Fetch the day's visible events + map geometry. Both are cosmetic — if
  // either fails, the briefing simply plays with fewer visuals.
  useEffect(() => {
    getMapInfo().then(setMapData).catch(() => {});
    api
      .events({ time_from: c.sim_start_time, time_to: c.discovery_time })
      .then((events) => setGlimpses(pickGlimpses(
        events,
        windowStart,
        windowEnd,
        replayEventId ? [replayEventId] : []
      )))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, [c, windowStart, windowEnd, replayEventId]);

  useEffect(() => {
    const urls = new Set<string>();
    const places =
      c.case_id === "case_001"
        ? CASE_001_PLACES
        : c.case_id === "case_003"
          ? CASE_003_PLACES
        : c.case_id === "case_004"
          ? CASE_004_PLACES
          : c.case_id === "case_006"
            ? CASE_006_PLACES
          : c.case_id === "case_007"
            ? CASE_007_PLACES
          : c.case_id === "case_005"
            ? CASE_005_PLACES
            : c.case_id === "case_010"
              ? CASE_010_PLACES
            : [];
    for (const place of places) {
      urls.add(place.exteriorSrc);
      urls.add(place.interiorSrc);
    }
    for (const loc of locations) {
      const scene = sceneArtFor(c.case_id, loc.location_id, loc.illustration);
      if (scene) urls.add(introAsset(scene));
    }
    for (const url of urls) preloadImage(url);
  }, [c.case_id, locations]);

  const beats = useMemo<Beat[]>(
    () => {
      if (replayEventId) {
        const event = glimpses.find((candidate) => candidate.event_id === replayEventId);
        return event ? [{ kind: "glimpse", event }] : [{ kind: "title" }];
      }
      const introBeats: Beat[] = [{ kind: "title" }];
      const places =
        c.case_id === "case_001"
          ? CASE_001_PLACES
          : c.case_id === "case_003"
            ? CASE_003_PLACES
          : c.case_id === "case_004"
            ? CASE_004_PLACES
            : c.case_id === "case_006"
              ? CASE_006_PLACES
            : c.case_id === "case_007"
              ? CASE_007_PLACES
            : c.case_id === "case_005"
              ? CASE_005_PLACES
              : c.case_id === "case_010"
                ? CASE_010_PLACES
              : [];
      for (const place of places) {
        introBeats.push({ kind: "place-reconstruct", place });
      }
      return [
        ...introBeats,
        ...glimpses.map((event): Beat => ({ kind: "glimpse", event })),
        { kind: "cast" },
        { kind: "brief" },
      ];
    },
    [c.case_id, glimpses, replayEventId]
  );
  const beat = beats[Math.min(beatIndex, beats.length - 1)];

  const advance = () => {
    if (beatIndex >= beats.length - 1) onDone();
    else setBeatIndex((i) => i + 1);
  };

  // Auto-advance the paced beats; the cast wall and briefing wait for a click.
  useEffect(() => {
    if (!loaded) return;
    if (beat.kind === "cast" || beat.kind === "brief") return;
    const hold =
      beat.kind === "title"
        ? TITLE_HOLD
        : beat.kind === "place-reconstruct"
          ? 5600
          : WITNESS_REPLAYS[c.case_id]?.[beat.kind === "glimpse" ? beat.event.event_id : ""]
            ? 9800
            : GLIMPSE_HOLD;
    const timer = setTimeout(() => setBeatIndex((i) => i + 1), hold);
    return () => clearTimeout(timer);
  }, [loaded, beatIndex, beat.kind]);

  // Esc always skips the whole briefing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDone();
      if (e.key === " " || e.key === "Enter") advance();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const victim = agents.find((a) => a.is_victim);
  const residents = agents.filter((a) => !a.is_victim);

  return (
    <div className="rw-intro" onClick={advance}>
      <button
        type="button"
        className="intro-skip"
        onClick={(e) => {
          e.stopPropagation();
          onDone();
        }}
        title="Skip (Esc)"
      >
        Skip ›
      </button>

      {beat.kind === "title" && (
        <div className="rw-beat rw-title" key="title">
          <p className="rw-eyebrow rw-in" style={{ animationDelay: "0.2s" }}>
            Evidence Reconstruction · Rewind
          </p>
          <h1 className="rw-in" style={{ animationDelay: "0.9s" }}>
            The {period}, reconstructed.
          </h1>
          <p className="rw-lede rw-in" style={{ animationDelay: "1.9s" }}>
            Every witness account, every open window, every rumor — stitched
            into one replay of {c.sim_start_time} to {c.discovery_time}.
          </p>
          <p className="rw-lede rw-accent rw-in" style={{ animationDelay: "3.0s" }}>
            But no one saw everything.
          </p>
        </div>
      )}

      {beat.kind === "glimpse" && (
      <GlimpseBeat
        key={beat.event.event_id}
        caseId={c.case_id}
        event={beat.event}
          locations={locations}
          mapData={mapData}
          locationName={locationName}
          inWindow={
            minutes(beat.event.time) >= windowStart &&
            minutes(beat.event.time) <= windowEnd
          }
          agents={agents}
          witnessReplay={replayEventId ? WITNESS_REPLAYS[c.case_id]?.[beat.event.event_id] : undefined}
        />
      )}

      {beat.kind === "place-reconstruct" && (
        <PlaceReconstructionBeat key={beat.place.id} place={beat.place} />
      )}

      {beat.kind === "cast" && (
        <div className="rw-beat rw-cast" key="cast">
          <p className="rw-eyebrow rw-in">The Village</p>
          <h2 className="rw-in" style={{ animationDelay: "0.15s" }}>
            Everyone who was there that {period}.
          </h2>
          <div className="rw-cast-grid">
            {victim && <CastCard agent={victim} index={0} isVictim />}
            {residents.map((a, i) => (
              <CastCard key={a.agent_id} agent={a} index={i + 1} />
            ))}
          </div>
          <p className="rw-continue rw-in" style={{ animationDelay: "1.6s" }}>
            One of them is lying. Click to continue.
          </p>
        </div>
      )}

      {beat.kind === "brief" && (
        <div className="rw-beat rw-brief" key="brief">
          <p className="rw-eyebrow rw-in">Detective's Briefing</p>
          <h2 className="rw-in" style={{ animationDelay: "0.15s" }}>
            Your move, Detective.
          </h2>
          <ul className="rw-steps">
            <li className="rw-in" style={{ animationDelay: "0.5s" }}>
              <span className="rw-step-icon">⏱</span>
              <div>
                <strong>Scrub the {period}.</strong> Drag the time window to
                replay any span of the {period}.
              </div>
            </li>
            <li className="rw-in" style={{ animationDelay: "1.0s" }}>
              <span className="rw-step-icon">👁</span>
              <div>
                <strong>Follow anyone.</strong> Filter by place or person and
                watch where they really went.
              </div>
            </li>
            <li className="rw-in" style={{ animationDelay: "1.5s" }}>
              <span className="rw-step-icon">📌</span>
              <div>
                <strong>Pin what doesn't add up.</strong> Pinned moments become
                evidence on your case board.
              </div>
            </li>
          </ul>
          <p className="rw-window-callout rw-in" style={{ animationDelay: "2.1s" }}>
            Estimated murder window:{" "}
            <strong>
              {c.murder_window[0]} – {c.murder_window[1]}
            </strong>
            . Watch it closely.
          </p>
          <button
            type="button"
            className="primary rw-cta rw-in"
            style={{ animationDelay: "2.5s" }}
            onClick={(e) => {
              e.stopPropagation();
              onDone();
            }}
          >
            Enter the Rewind ▸
          </button>
        </div>
      )}

      <div className="rw-dots" aria-hidden>
        {beats.map((_, i) => (
          <span key={i} className={i === beatIndex ? "rw-dot active" : "rw-dot"} />
        ))}
      </div>
    </div>
  );
}

function PlaceReconstructionBeat({ place }: { place: PlaceReconstruction }) {
  const focusStyle = {
    "--rw-focus-x": `${place.focus.x}%`,
    "--rw-focus-y": `${place.focus.y}%`,
  } as CSSProperties;

  return (
    <div className="rw-beat rw-place-reconstruct">
      <p className="rw-eyebrow rw-in">Evidence Reconstruction · Location Match</p>
      <div
        className="rw-place-frame"
        aria-label={`${place.displayName} exterior zooming into interior`}
        style={focusStyle}
      >
        <img
          className="rw-place-exterior"
          src={place.exteriorSrc}
          alt={`${place.displayName} exterior`}
          draggable={false}
        />
        <img
          className="rw-place-interior"
          src={place.interiorSrc}
          alt={`${place.displayName} interior reconstruction`}
          draggable={false}
        />
        <div className="rw-place-aperture" />
        <div className="rw-place-reticle">
          <span />
          <span />
          <span />
          <span />
        </div>
        <div className="rw-feed-scanlines" />
      </div>
      <h2 className="rw-in" style={{ animationDelay: "0.35s" }}>
        {place.matchedLine}
      </h2>
      <p className="rw-lede rw-in" style={{ animationDelay: "0.8s" }}>
        {place.description}
      </p>
    </div>
  );
}

function GlimpseBeat({
  caseId,
  event,
  locations,
  mapData,
  locationName,
  inWindow,
  agents,
  witnessReplay,
}: {
  caseId: string;
  event: EventPublic;
  locations: LocationPublic[];
  mapData: MapReplayData | null;
  locationName: (id: string) => string;
  inWindow: boolean;
  agents: ReturnType<typeof useWorld>["agents"];
  witnessReplay?: WitnessReplay;
}) {
  const present = event.agent_ids
    .map((id) => agents.find((a) => a.agent_id === id))
    .filter((a) => a != null);
  const obscured = event.visibility !== "public";
  const artwork = sceneArtwork(caseId, event.location_id, locations);

  return (
    <div className={`rw-beat rw-glimpse ${obscured ? "obscured" : ""}`}>
      <div className="rw-feed">
        <div className="rw-feed-head">
          <span className="rw-rec">
            <span className="rw-rec-dot" /> REPLAY
          </span>
          <span className="rw-feed-time">{event.time}</span>
          <span className="rw-feed-loc">{locationName(event.location_id)}</span>
        </div>
        <div className="rw-feed-frame">
          {witnessReplay ? (
            <WitnessReplayScene replay={witnessReplay} />
          ) : artwork ? (
            <img
              className="rw-feed-scene"
              src={artwork.src}
              alt={locationName(event.location_id)}
              draggable={false}
              style={{ objectPosition: artwork.position ?? "50% 50%" }}
            />
          ) : mapData ? (
            <MapCrop
              data={mapData}
              locationId={event.location_id}
              width={520}
              height={260}
              className="rw-feed-crop"
            />
          ) : null}
          <div className="rw-feed-scanlines" />
          {obscured && <div className="rw-feed-static" />}
        </div>
        <p className="rw-feed-desc rw-in" style={{ animationDelay: "0.7s" }}>
          {event.description}
        </p>
        <div className="rw-feed-meta rw-in" style={{ animationDelay: "1.2s" }}>
          {present.slice(0, 4).map((a) => (
            <span key={a.agent_id} className="rw-feed-agent">
              <Portrait agent={a} /> {a.full_name}
            </span>
          ))}
          {present.length > 4 && (
            <span className="muted small">+{present.length - 4} more</span>
          )}
          {obscured && (
            <span className="badge ambiguous">
              {event.visibility === "public_partial" ? "unclear" : "obscured"}
            </span>
          )}
          {inWindow && <span className="badge window">murder window</span>}
        </div>
      </div>
    </div>
  );
}

function WitnessReplayScene({ replay }: { replay: WitnessReplay }) {
  return (
    <div className={`rw-witness-scene ${replay.direction}`}>
      {replay.frames.map((frame, index) => (
        <img
          key={frame.src}
          className={`rw-feed-scene rw-witness-art rw-witness-flash flash-${index + 1}`}
          src={frame.src}
          alt={`${frame.label} — ${replay.observation}`}
          draggable={false}
          style={{ objectPosition: frame.position ?? "50% 50%" }}
        />
      ))}
      <div className="rw-witness-vignette" />
      <div className="rw-witness-track" aria-hidden="true">
        <span className="rw-witness-footstep step-one" />
        <span className="rw-witness-footstep step-two" />
        <span className="rw-witness-footstep step-three" />
        <span className="rw-witness-figure" />
      </div>
      <div className="rw-witness-caption">
        <span>WITNESS VIEW · {replay.witness}</span>
        <strong>{replay.figureLabel}</strong>
      </div>
      <div className="rw-witness-frame-count" aria-hidden>
        {replay.frames.map((frame, index) => <span key={frame.src}>{String(index + 1).padStart(2, "0")} · {frame.label}</span>)}
      </div>
      <p className="rw-witness-observation">{replay.observation}</p>
    </div>
  );
}

function CastCard({
  agent,
  index,
  isVictim = false,
}: {
  agent: ReturnType<typeof useWorld>["agents"][number];
  index: number;
  isVictim?: boolean;
}) {
  return (
    <div
      className={`rw-cast-card rw-in ${isVictim ? "victim" : ""}`}
      style={{ animationDelay: `${0.3 + index * 0.12}s` }}
    >
      <Portrait agent={agent} size="large" />
      <div className="rw-cast-name">{agent.full_name}</div>
      <div className="rw-cast-role">
        {isVictim ? "The Victim" : `${agent.age} · ${agent.occupation}`}
      </div>
      {!isVictim && agent.traits.length > 0 && (
        <div className="rw-cast-traits">
          {agent.traits.slice(0, 3).map((t) => (
            <span key={t} className="rw-trait">
              {t}
            </span>
          ))}
        </div>
      )}
      <p className="rw-cast-routine">{agent.routine_summary}</p>
    </div>
  );
}
