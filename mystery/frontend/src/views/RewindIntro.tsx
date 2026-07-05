import { useEffect, useMemo, useState } from "react";
import { api, minutes } from "../api";
import { useWorld } from "../App";
import type { EventPublic, MapReplayData } from "../types";
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

type Beat =
  | { kind: "title" }
  | { kind: "glimpse"; event: EventPublic }
  | { kind: "cast" }
  | { kind: "brief" };

// Auto-advance pacing (ms). Cast and brief wait for the player.
const TITLE_HOLD = 4200;
const GLIMPSE_HOLD = 4600;

/** Pick up to four real player-visible moments that tease the morning:
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
  const { caseOverview: c, agents, locationName } = useWorld();
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

  const beats = useMemo<Beat[]>(
    () => [
      { kind: "title" },
      ...glimpses.map((event): Beat => ({ kind: "glimpse", event })),
      { kind: "cast" },
      { kind: "brief" },
    ],
    [glimpses]
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
    const hold = beat.kind === "title" ? TITLE_HOLD : GLIMPSE_HOLD;
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
            The morning, reconstructed.
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
          mapData={mapData}
          locationName={locationName}
          inWindow={
            minutes(beat.event.time) >= windowStart &&
            minutes(beat.event.time) <= windowEnd
          }
          agents={agents}
        />
      )}

      {beat.kind === "cast" && (
        <div className="rw-beat rw-cast" key="cast">
          <p className="rw-eyebrow rw-in">The Village</p>
          <h2 className="rw-in" style={{ animationDelay: "0.15s" }}>
            Everyone who was there that morning.
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
                <strong>Scrub the morning.</strong> Drag the time window to
                replay any span of the day.
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

function GlimpseBeat({
  event,
  mapData,
  locationName,
  inWindow,
  agents,
}: {
  event: EventPublic;
  mapData: MapReplayData | null;
  locationName: (id: string) => string;
  inWindow: boolean;
  agents: ReturnType<typeof useWorld>["agents"];
}) {
  const present = event.agent_ids
    .map((id) => agents.find((a) => a.agent_id === id))
    .filter((a) => a != null);
  const obscured = event.visibility !== "public";

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
          {mapData && (
            <MapCrop
              data={mapData}
              locationId={event.location_id}
              width={520}
              height={260}
              className="rw-feed-crop"
            />
          )}
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
