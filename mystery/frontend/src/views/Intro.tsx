import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type { MapReplayData } from "../types";
import { getMapInfo } from "../map/mapInfo";
import MapCrop from "../components/MapCrop";
import Portrait from "../components/Portrait";
import { audioManager } from "../audio";
import { sfx } from "../sfx";

type ScenePhase = "initial" | "time" | "victim" | "scene" | "suspects" | "title" | "cta";

export default function Intro({ onBegin }: { onBegin: () => void }) {
  const { caseOverview: c, agents, locations } = useWorld();
  const [mapData, setMapData] = useState<MapReplayData | null>(null);
  const [witnessIds, setWitnessIds] = useState<string[]>([]);
  const [phase, setPhase] = useState<ScenePhase>("initial");
  const [visibleSuspects, setVisibleSuspects] = useState<number>(0);

  useEffect(() => {
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
  const locationArt =
    location.illustration ??
    location.building_art?.interior ??
    location.building_art?.exterior;

  useEffect(() => {
    audioManager.playAmbient("testimony");
    return () => audioManager.stopAmbient();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        sfx.click();
        onBegin();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onBegin]);

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
        const interval = setInterval(() => {
          if (count < suspects.length) {
            setVisibleSuspects(count + 1);
            sfx.pinPush();
            count++;
          } else {
            clearInterval(interval);
            setTimeout(() => {
              setPhase("title");
              audioManager.playStinger("intro_drama");
            }, 1500);
          }
        }, 600); 
        return () => clearInterval(interval);
      } else {
        const t = setTimeout(() => {
          setPhase("title");
          audioManager.playStinger("intro_drama");
        }, 1000);
        return () => clearTimeout(t);
      }
    }
  }, [phase, suspects.length]);

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
