import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { api, minutes, timeOfDayLabel } from "../api";
import { useWorld } from "../App";
import type { EventPublic, LocationPublic, MapReplayData } from "../types";
import { getMapInfo } from "../map/mapInfo";
import MapCrop from "../components/MapCrop";
import Portrait from "../components/Portrait";
import { audioManager } from "../audio";

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
const CASE_004_ART = "/art/case_004";
const CASE_004_INTRO_ART = `${CASE_004_ART}/intro`;
const CASE_005_ART = "/art/case_005";
const CASE_010_ART = "/art/case_010";
const TOWN_INTERIORS = "/art/town/interiors_hd";
const TOWN_INTERIORS_INTRO = `${TOWN_INTERIORS}/intro`;
const TOWN_PLACES = "/art/town/places_hd";
const TOWN_PLACES_INTRO = `${TOWN_PLACES}/intro`;
const HOBBS_CAFE_EXTERIOR =
  "/art/town/buildings/generated_exteriors_v1/cafe_small_v1_exterior_canonical_alpha.png";
const BEN_FLAT_EXTERIOR =
  "/art/town/buildings/generated_exteriors_v1/ben_newsagent_flat_exterior_variant_alpha.png";
const PUB_EXTERIOR =
  "/art/town/buildings/generated_exteriors_v1/pub_small_v1_exterior_canonical_alpha.png";
const FLATS_EXTERIOR =
  "/art/town/buildings/generated_exteriors_v1/flats_two_storey_v1_exterior_canonical_alpha.png";
const HOUSE_YARD_EXTERIOR =
  "/art/town/buildings/generated_exteriors_v1/house_yard_workshop_v1_exterior_canonical_alpha.png";
const COTTAGE_EXTERIOR =
  "/art/town/buildings/generated_exteriors_v1/cottage_small_v1_exterior_canonical_alpha.png";
const CLINIC_EXTERIOR =
  "/art/town/buildings/generated_exteriors_v1/clinic_small_v1_exterior_canonical_alpha.png";

const INTRO_ART_OVERRIDES: Record<string, string> = {
  [`${CASE_001_ART}/village_square_dawn_hd.png`]: `${CASE_001_INTRO_ART}/village_square_dawn_intro.jpg`,
  [`${CASE_001_ART}/fountain_daylight_closeup_hd.png`]: `${CASE_001_INTRO_ART}/fountain_daylight_closeup_intro.jpg`,
  [`${CASE_001_ART}/hobbs_cafe_main_hd.png`]: `${CASE_001_INTRO_ART}/hobbs_cafe_main_intro.jpg`,
  [`${CASE_001_ART}/cafe_kitchen_hd.png`]: `${CASE_001_INTRO_ART}/cafe_kitchen_intro.jpg`,
  [`${CASE_001_ART}/cafe_storage_room_hd.png`]: `${CASE_001_INTRO_ART}/cafe_storage_room_intro.jpg`,
  [`${CASE_001_ART}/rear_alley_hd.png`]: `${CASE_001_INTRO_ART}/rear_alley_intro.jpg`,
  [`${CASE_001_ART}/reed_bell_bookshop_hd.png`]: `${CASE_001_INTRO_ART}/reed_bell_bookshop_intro.jpg`,
  [`${CASE_001_ART}/village_clinic_hd.png`]: `${CASE_001_INTRO_ART}/village_clinic_intro.jpg`,
  [`${CASE_001_ART}/marcus_study_hd.png`]: `${CASE_001_INTRO_ART}/marcus_study_intro.jpg`,
  [`${CASE_001_ART}/owen_house_yard_hd.png`]: `${CASE_001_INTRO_ART}/owen_house_yard_intro.jpg`,
  [`${CASE_001_ART}/clara_flat_hd.png`]: `${CASE_001_INTRO_ART}/clara_flat_intro.jpg`,
  [`${CASE_001_ART}/priya_flat_hd.png`]: `${CASE_001_INTRO_ART}/priya_flat_intro.jpg`,
  [`${CASE_001_ART}/nadia_flat_hd.png`]: `${CASE_001_INTRO_ART}/nadia_flat_intro.jpg`,
  [`${CASE_001_ART}/elias_house_hd.png`]: `${CASE_001_INTRO_ART}/elias_house_intro.jpg`,
  [`${CASE_002_ART}/village_square_lunchtime_hd.png`]: `${CASE_002_INTRO_ART}/village_square_lunchtime_intro.jpg`,
  [`${CASE_002_ART}/reed_bell_bookshop_front_hd.png`]: `${CASE_002_INTRO_ART}/reed_bell_bookshop_front_intro.jpg`,
  [`${CASE_002_ART}/bookshop_back_room_hd.png`]: `${CASE_002_INTRO_ART}/bookshop_back_room_intro.jpg`,
  [`${CASE_002_ART}/rear_alley_bookshop_hd.png`]: `${CASE_002_INTRO_ART}/rear_alley_bookshop_intro.jpg`,
  [`${CASE_002_ART}/hobbs_cafe_lunchtime_hd.png`]: `${CASE_002_INTRO_ART}/hobbs_cafe_lunchtime_intro.jpg`,
  [`${CASE_002_ART}/village_clinic_lunchtime_hd.png`]: `${CASE_002_INTRO_ART}/village_clinic_lunchtime_intro.jpg`,
  [`${CASE_002_ART}/owen_house_yard_lunchtime_hd.png`]: `${CASE_002_INTRO_ART}/owen_house_yard_lunchtime_intro.jpg`,
  [`${CASE_002_ART}/priya_flat_lunchtime_hd.png`]: `${CASE_002_INTRO_ART}/priya_flat_lunchtime_intro.jpg`,
  [`${CASE_002_ART}/fountain_lunchtime_closeup_hd.png`]: `${CASE_002_INTRO_ART}/fountain_lunchtime_closeup_intro.jpg`,
  [`${CASE_004_ART}/village_square_moonlight_hd.png`]: `${CASE_004_INTRO_ART}/village_square_moonlight_intro.jpg`,
  [`${CASE_004_ART}/fishery_moonlight_hd.png`]: `${CASE_004_INTRO_ART}/fishery_moonlight_intro.jpg`,
  [`${CASE_004_ART}/lovers_lake_moonlight_hd.png`]: `${CASE_004_INTRO_ART}/lovers_lake_moonlight_intro.jpg`,
  [`${CASE_004_ART}/whispering_woodland_moonlight_hd.png`]: `${CASE_004_INTRO_ART}/whispering_woodland_moonlight_intro.jpg`,
  [`${CASE_004_ART}/green_meadow_moonlight_hd.png`]: `${CASE_004_INTRO_ART}/green_meadow_moonlight_intro.jpg`,
  [`${TOWN_INTERIORS}/ben_flat_interior_hd.png`]: `${TOWN_INTERIORS_INTRO}/ben_flat_interior_intro.jpg`,
  [`${TOWN_INTERIORS}/elias_cottage_full_interior_hd.png`]: `${TOWN_INTERIORS_INTRO}/elias_cottage_full_interior_intro.jpg`,
  [`${TOWN_INTERIORS}/mallet_crown_pub_full_interior_hd.png`]: `${TOWN_INTERIORS_INTRO}/mallet_crown_pub_full_interior_intro.jpg`,
  [`${TOWN_INTERIORS}/owen_house_workshop_yard_hd.png`]: `${TOWN_INTERIORS_INTRO}/owen_house_workshop_yard_intro.jpg`,
  [`${TOWN_INTERIORS}/priya_flat_interior_hd.png`]: `${TOWN_INTERIORS_INTRO}/priya_flat_interior_intro.jpg`,
  [`${TOWN_INTERIORS}/village_clinic_full_interior_hd.png`]: `${TOWN_INTERIORS_INTRO}/village_clinic_full_interior_intro.jpg`,
  [`${TOWN_PLACES}/fishery_hd.png`]: `${TOWN_PLACES_INTRO}/fishery_intro.jpg`,
  [`${TOWN_PLACES}/green_meadow_hd.png`]: `${TOWN_PLACES_INTRO}/green_meadow_intro.jpg`,
  [`${TOWN_PLACES}/lovers_lake_hd.png`]: `${TOWN_PLACES_INTRO}/lovers_lake_intro.jpg`,
  [`${TOWN_PLACES}/village_square_hd.png`]: `${TOWN_PLACES_INTRO}/village_square_intro.jpg`,
  [`${TOWN_PLACES}/whispering_woodland_hd.png`]: `${TOWN_PLACES_INTRO}/whispering_woodland_intro.jpg`,
};

function introAsset(src: string): string {
  return INTRO_ART_OVERRIDES[src] ?? src;
}

function sceneArtwork(
  locationId: string,
  locations: LocationPublic[]
): SceneArtwork | null {
  const loc = locations.find((l) => l.location_id === locationId);
  const src = loc?.illustration ?? loc?.building_art?.interior ?? loc?.building_art?.exterior;
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
    exteriorSrc: HOBBS_CAFE_EXTERIOR,
    interiorSrc: `${CASE_001_INTRO_ART}/cafe_storage_room_intro.jpg`,
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
    exteriorSrc: BEN_FLAT_EXTERIOR,
    interiorSrc: `${TOWN_INTERIORS_INTRO}/ben_flat_interior_intro.jpg`,
    focus: { x: 16, y: 83 },
    description:
      "Shop dark, papers unsold. A separate stair climbs to the flat above — the only window on the square still lit past midnight.",
  },
  {
    id: "mallet-crown",
    displayName: "The Mallet & Crown",
    matchedLine: "The Mallet & Crown, locked up for the night.",
    exteriorSrc: PUB_EXTERIOR,
    interiorSrc: `${TOWN_INTERIORS_INTRO}/mallet_crown_pub_full_interior_intro.jpg`,
    focus: { x: 23, y: 49 },
    description:
      "Last orders came and went hours ago. The exterior locks to the room Fred Dunmore keeps behind the bar.",
  },
  {
    id: "priya-flat",
    displayName: "Priya's Flat",
    matchedLine: "Priya's flat, curtains drawn.",
    exteriorSrc: FLATS_EXTERIOR,
    interiorSrc: `${TOWN_INTERIORS_INTRO}/priya_flat_interior_intro.jpg`,
    focus: { x: 33, y: 80 },
    description:
      "Two-storey flats above the square. The reconstruction matches the stair and door witnesses described to the room behind them.",
  },
  {
    id: "owen-house",
    displayName: "Owen Price's House & Yard",
    matchedLine: "Owen's house and workshop yard.",
    exteriorSrc: HOUSE_YARD_EXTERIOR,
    interiorSrc: `${TOWN_INTERIORS_INTRO}/owen_house_workshop_yard_intro.jpg`,
    focus: { x: 91, y: 54 },
    description:
      "The builder's own yard, tools put away for the night. Nobody has said whether he made it home before the fountain.",
  },
  {
    id: "elias-cottage",
    displayName: "Elias's Cottage",
    matchedLine: "Elias's cottage, bedroom window overlooking the square.",
    exteriorSrc: COTTAGE_EXTERIOR,
    interiorSrc: `${TOWN_INTERIORS_INTRO}/elias_cottage_full_interior_intro.jpg`,
    focus: { x: 50, y: 80 },
    description:
      "The vantage point the body was found from. The exterior locks to the room with the window that looks straight onto the fountain.",
  },
  {
    id: "village-clinic",
    displayName: "Village Clinic",
    matchedLine: "The Village Clinic, dark until the call came in.",
    exteriorSrc: CLINIC_EXTERIOR,
    interiorSrc: `${TOWN_INTERIORS_INTRO}/village_clinic_full_interior_intro.jpg`,
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
    exteriorSrc: `${CASE_005_ART}/overhead/village_overhead_dawn.png`,
    interiorSrc: `${CASE_005_ART}/overhead/rear_alley_overhead_dawn.png`,
    focus: { x: 48, y: 55 },
    description:
      "A wet village waking slowly. Behind the cafe, one narrow service route holds the scene the square could not see.",
  },
];

const CASE_010_PLACES: PlaceReconstruction[] = [
  {
    id: "case-010-village-storage",
    displayName: "Hobbs Cafe & the Storage Room",
    matchedLine: "The same dawn village, with the cafe's rear room sealed off.",
    exteriorSrc: `${CASE_010_ART}/overhead/village_overhead_dawn.png`,
    interiorSrc: `${CASE_010_ART}/cafe_storage_dawn_hd.png`,
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
function pickGlimpses(
  events: EventPublic[],
  windowStart: number,
  windowEnd: number
): EventPublic[] {
  if (events.length === 0) return [];
  const sorted = [...events].sort((a, b) => minutes(a.time) - minutes(b.time));
  const picks = new Map<string, EventPublic>();
  const add = (e: EventPublic | undefined) => {
    if (e) picks.set(e.event_id, e);
  };
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
  return [...picks.values()]
    .sort((a, b) => minutes(a.time) - minutes(b.time))
    .slice(0, 4);
}

export default function RewindIntro({ onDone }: { onDone: () => void }) {
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
      .then((events) => setGlimpses(pickGlimpses(events, windowStart, windowEnd)))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, [c, windowStart, windowEnd]);

  useEffect(() => {
    const urls = new Set<string>();
    const places =
      c.case_id === "case_001"
        ? CASE_001_PLACES
        : c.case_id === "case_004"
          ? CASE_004_PLACES
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
      if (loc.illustration) urls.add(introAsset(loc.illustration));
      if (loc.building_art?.interior) urls.add(introAsset(loc.building_art.interior));
      if (loc.building_art?.exterior) urls.add(introAsset(loc.building_art.exterior));
    }
    for (const url of urls) preloadImage(url);
  }, [c.case_id, locations]);

  const beats = useMemo<Beat[]>(
    () => {
      const introBeats: Beat[] = [{ kind: "title" }];
      const places =
        c.case_id === "case_001"
          ? CASE_001_PLACES
          : c.case_id === "case_004"
            ? CASE_004_PLACES
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
    [c.case_id, glimpses]
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
          event={beat.event}
          locations={locations}
          mapData={mapData}
          locationName={locationName}
          inWindow={
            minutes(beat.event.time) >= windowStart &&
            minutes(beat.event.time) <= windowEnd
          }
          agents={agents}
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
  event,
  locations,
  mapData,
  locationName,
  inWindow,
  agents,
}: {
  event: EventPublic;
  locations: LocationPublic[];
  mapData: MapReplayData | null;
  locationName: (id: string) => string;
  inWindow: boolean;
  agents: ReturnType<typeof useWorld>["agents"];
}) {
  const present = event.agent_ids
    .map((id) => agents.find((a) => a.agent_id === id))
    .filter((a) => a != null);
  const obscured = event.visibility !== "public";
  const artwork = sceneArtwork(event.location_id, locations);

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
          {artwork ? (
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
