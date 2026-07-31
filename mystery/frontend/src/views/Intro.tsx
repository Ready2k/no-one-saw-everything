import { useCallback, useEffect, useMemo, useState } from "react";
import { api, minutes, timeOfDayLabel } from "../api";
import { useWorld } from "../App";
import type { AgentPublic, EventPublic, MapReplayData } from "../types";
import { getMapInfo } from "../map/mapInfo";
import MapCrop from "../components/MapCrop";
import Portrait from "../components/Portrait";
import { audioManager } from "../audio";
import { sfx } from "../sfx";
import { sceneArtFor } from "../sceneArt";
import { pickGlimpses } from "./RewindIntro";

type ScenePhase = "initial" | "time" | "victim" | "scene" | "suspects" | "incident" | "title" | "cta";

export default function Intro({ onBegin }: { onBegin: () => void }) {
  const { caseOverview: c, agents, locations } = useWorld();
  const [mapData, setMapData] = useState<MapReplayData | null>(null);
  const [witnessIds, setWitnessIds] = useState<string[]>([]);
  const [incidentEvents, setIncidentEvents] = useState<EventPublic[]>([]);
  const [incidentIndex, setIncidentIndex] = useState(0);
  const [incidentLoaded, setIncidentLoaded] = useState(false);
  const [phase, setPhase] = useState<ScenePhase>("initial");
  const [visibleSuspects, setVisibleSuspects] = useState<number>(0);

  useEffect(() => {
    setIncidentLoaded(false);
    setIncidentIndex(0);
    getMapInfo().then(setMapData).catch(() => {});
    api
      .events({
        location_id: c.discovery_location.location_id,
        time_from: c.murder_window[0],
        time_to: c.discovery_time,
      })
      .then((events) => {
        const ids = new Set<string>();
        for (const e of events) for (const id of e.agent_ids) ids.add(id);
        ids.delete(c.victim.agent_id);
        setWitnessIds([...ids]);
      })
      .catch(() => {});
    api
      .events({ time_from: c.sim_start_time, time_to: c.discovery_time })
      .then((events) => setIncidentEvents(pickGlimpses(
        events,
        minutes(c.murder_window[0]),
        minutes(c.murder_window[1])
      )))
      .catch(() => setIncidentEvents([]))
      .finally(() => setIncidentLoaded(true));
  }, [c]);

  const witnesses = witnessIds
    .map((id) => agents.find((a) => a.agent_id === id))
    .filter((a) => a != null);
  const suspects = useMemo(
    () => agents.filter((a) => !a.is_victim && !a.is_background).slice(0, 8),
    [agents]
  );
  const discoveredBy = agents.find(
    (a) => a.agent_id === c.discovered_by.agent_id
  ) ?? c.discovered_by;
  const location =
    locations.find((l) => l.location_id === c.discovery_location.location_id) ??
    c.discovery_location;
  const locationArt = sceneArtFor(c.case_id, location.location_id, location.illustration);

  const advanceIncident = useCallback(() => {
    if (phase !== "incident" || !incidentLoaded || incidentEvents.length === 0) return;
    if (incidentIndex < incidentEvents.length - 1) {
      setIncidentIndex((index) => index + 1);
      sfx.pageTurn();
    } else {
      setPhase("title");
      audioManager.playStinger("intro_drama");
    }
  }, [phase, incidentLoaded, incidentEvents.length, incidentIndex]);

  useEffect(() => {
    audioManager.playAmbient("testimony");
    return () => audioManager.stopAmbient();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        sfx.click();
        onBegin();
      } else if (phase === "incident" && [" ", "Enter", "ArrowRight"].includes(e.key)) {
        e.preventDefault();
        advanceIncident();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onBegin, phase, advanceIncident]);

  useEffect(() => {
    // Cinematic Timeline
    const t1 = setTimeout(() => {
      setPhase("time");
      audioManager.playStinger("intro_tension");
      sfx.stampThunk();
    }, 250);

    const t2 = setTimeout(() => {
      setPhase("victim");
    }, 2200);

    const t3 = setTimeout(() => {
      setPhase("scene");
      audioManager.playStinger("intro_discovery");
    }, 5800);

    const t4 = setTimeout(() => {
      setPhase("suspects");
    }, 9800);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
    };
  }, []);

  // Suspects flashing logic
  useEffect(() => {
    if (phase === "suspects") {
      if (suspects.length > 0) {
        let count = 0;
        let innerTimeout: number | undefined;
        const interval = setInterval(() => {
          if (count < suspects.length) {
            setVisibleSuspects(count + 1);
            sfx.pinPush();
            count++;
          } else {
            clearInterval(interval);
            innerTimeout = window.setTimeout(() => {
              setPhase("incident");
            }, 1500);
          }
        }, 600); 
        return () => {
          clearInterval(interval);
          if (innerTimeout !== undefined) window.clearTimeout(innerTimeout);
        };
      } else {
        const t = setTimeout(() => {
          setPhase("incident");
          audioManager.playStinger("intro_drama");
        }, 1000);
        return () => clearTimeout(t);
      }
    }
  }, [phase, suspects.length]);

  useEffect(() => {
    if (phase !== "incident") return;
    if (!incidentLoaded) return;
    if (incidentEvents.length === 0) {
      setPhase("title");
      audioManager.playStinger("intro_drama");
      return;
    }
    const timer = window.setTimeout(() => {
      advanceIncident();
    }, 4200);
    return () => window.clearTimeout(timer);
  }, [phase, incidentIndex, incidentEvents.length, incidentLoaded, advanceIncident]);

  useEffect(() => {
    if (phase === "title") {
      const t5 = setTimeout(() => {
        setPhase("cta");
      }, 4500);
      return () => clearTimeout(t5);
    }
  }, [phase]);

  return (
    <div className="intro-scene" data-phase={phase}>
      <button
        className="intro-skip"
        onClick={() => {
          sfx.click();
          onBegin();
        }}
        title="Skip (Esc)"
      >
        Skip ›
      </button>

      <div className="cinematic-backdrop" aria-hidden="true">
        {locationArt ? (
          <img src={locationArt} alt="" draggable={false} />
        ) : mapData ? (
          <MapCrop
            data={mapData}
            locationId={c.discovery_location.location_id}
            width={1200}
            height={720}
            className="cinematic-backdrop-map"
          />
        ) : null}
      </div>

      {/* Layer 1: Evidence location */}
      <div className={`cinematic-layer ${phase === "scene" || phase === "suspects" || phase === "title" || phase === "cta" ? "active" : ""}`}>
        <div className="cinematic-map-container">
          {locationArt ? (
            <img
              src={locationArt}
              alt={location.name}
              draggable={false}
            />
          ) : mapData ? (
            <MapCrop
              data={mapData}
              locationId={c.discovery_location.location_id}
              width={900}
              height={520}
              className="cinematic-map-crop"
            />
          ) : null}
        </div>
        {phase === "scene" && (
          <div className="cinematic-scene-brief">
            <p className="cinematic-kicker">Discovery Scene</p>
            <h2>{location.name}</h2>
            <p>{c.scene_description || c.overview_text}</p>
          </div>
        )}
      </div>

      {/* Layer 2: Time */}
      <div className={`cinematic-layer ${phase === "time" ? "active" : ""}`}>
        {phase === "time" && <p className="cinematic-time">{c.discovery_time}</p>}
      </div>

      {/* Layer 3: Victim */}
      <div className={`cinematic-layer ${phase === "victim" ? "active" : ""}`}>
        {phase === "victim" && (
          <div className="cinematic-victim">
            <div className="cinematic-victim-card">
              <Portrait agent={c.victim} size="large" />
            </div>
            <h1>{c.victim.full_name} is dead.</h1>
            <div className="cinematic-facts">
              <span>{c.discovery_time}</span>
              <span>{location.name}</span>
              <span>Found by {discoveredBy.full_name}</span>
            </div>
          </div>
        )}
      </div>

      {/* Layer 4: Suspects */}
      <div className={`cinematic-layer ${phase === "suspects" ? "active" : ""}`}>
        {phase === "suspects" && (
          <div className="cinematic-suspect-wall">
            <p className="cinematic-kicker">People In The Window</p>
            <div className="cinematic-suspects">
              {suspects.slice(0, visibleSuspects).map((w) => (
              <div 
                key={w.agent_id} 
                className="cinematic-suspect flash"
              >
                <Portrait agent={w} size="large" />
                <span>{w.full_name}</span>
              </div>
              ))}
            </div>
            {witnesses.length > 0 && (
              <p className="cinematic-witness-note">
                {witnesses.length} seen near the discovery scene. None saw enough.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Layer 5: Title & CTA */}
      <div className={`cinematic-layer ${phase === "incident" ? "active" : ""}`}>
        {phase === "incident" && (
          incidentEvents[incidentIndex] ? (
            <IncidentRecap
              event={incidentEvents[incidentIndex]}
              index={incidentIndex}
              total={incidentEvents.length}
              agents={agents}
              locations={locations}
              mapData={mapData}
              caseId={c.case_id}
              weather={c.weather}
              onAdvance={advanceIncident}
            />
          ) : (
            <p className="cinematic-incident-loading">Compiling the known observations…</p>
          )
        )}
      </div>

      {/* Layer 6: Title & CTA */}
      <div className={`cinematic-layer ${phase === "title" || phase === "cta" ? "active cinematic-cta-layer" : ""}`}>
        {(phase === "title" || phase === "cta") && (
          <div className="cinematic-title">
            No One Saw<br />Everything
            <span>{c.title}</span>
          </div>
        )}
        {phase === "cta" && (
          <button className="cinematic-cta" onClick={() => {
            sfx.click();
            onBegin();
          }} style={{ marginTop: '4rem' }}>
            Begin Investigation
          </button>
        )}
      </div>
    </div>
  );
}

function IncidentRecap({
  event,
  index,
  total,
  agents,
  locations,
  mapData,
  caseId,
  weather,
  onAdvance,
}: {
  event: EventPublic;
  index: number;
  total: number;
  agents: ReturnType<typeof useWorld>["agents"];
  locations: ReturnType<typeof useWorld>["locations"];
  mapData: MapReplayData | null;
  caseId: string;
  weather: ReturnType<typeof useWorld>["caseOverview"]["weather"];
  onAdvance: () => void;
}) {
  const location = locations.find((item) => item.location_id === event.location_id);
  const art = sceneArtFor(caseId, event.location_id, location?.illustration);
  const present = event.agent_ids
    .map((id) => agents.find((agent) => agent.agent_id === id))
    .filter((agent): agent is AgentPublic => agent != null);
  const unclear = event.visibility !== "public";
  const period = timeOfDayLabel(event.time);
  const cue = eventCue(event.event_type, unclear);
  const focus = eventFocus(event.event_id);

  return (
    <article
      className="cinematic-incident-card"
      key={event.event_id}
      onClick={onAdvance}
      onKeyDown={(e) => {
        if ([" ", "Enter", "ArrowRight"].includes(e.key)) {
          e.preventDefault();
          onAdvance();
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={`Known observation ${index + 1} of ${total}. ${cue.label}. Press Enter or Space to continue.`}
    >
      <header className="cinematic-incident-head">
        <span>What we know</span>
        <span>{index + 1} / {total}</span>
      </header>
      <div className={`cinematic-incident-frame incident-${period} weather-${weather}`}>
        {art ? (
          <img src={art} alt={location?.name ?? "Known location"} draggable={false} style={{ objectPosition: focus }} />
        ) : mapData ? (
          <MapCrop
            data={mapData}
            locationId={event.location_id}
            width={720}
            height={360}
            className="cinematic-incident-map"
          />
        ) : null}
        <div className="cinematic-incident-timewash" aria-hidden="true" />
        <div className="cinematic-incident-cue" aria-hidden="true">
          <span>{cue.mark}</span>{cue.label}
        </div>
        <div className="cinematic-incident-scanlines" />
        <div className="cinematic-incident-time">{event.time}</div>
      </div>
      <div className="cinematic-incident-copy">
        <p className="cinematic-kicker">{location?.name ?? "Recorded location"}{unclear && " · unclear sighting"}</p>
        <h2>{event.description}</h2>
        {present.length > 0 && (
          <div className="cinematic-incident-people">
            {present.slice(0, 4).map((person) => <span key={person.agent_id}><Portrait agent={person} /> {person.full_name}</span>)}
          </div>
        )}
        <p className="cinematic-incident-note">A recorded moment, not the whole story.</p>
        <p className="cinematic-incident-continue" aria-hidden="true">Click or press Space to continue ›</p>
      </div>
    </article>
  );
}

function eventCue(eventType: string, unclear: boolean) {
  if (unclear) return { mark: "◌", label: "Partial account" };
  if (eventType === "argument") return { mark: "!", label: "Tension recorded" };
  if (eventType === "movement") return { mark: "→", label: "Route recorded" };
  if (eventType === "discovery") return { mark: "✦", label: "Discovery record" };
  if (eventType === "routine") return { mark: "·", label: "Routine recorded" };
  return { mark: "◈", label: "Observation logged" };
}

function eventFocus(eventId: string): string {
  const seed = [...eventId].reduce((total, char) => total + char.charCodeAt(0), 0);
  return `${38 + (seed % 25)}% ${38 + (Math.floor(seed / 7) % 25)}%`;
}
