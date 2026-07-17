import { useEffect, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type { MapReplayData } from "../types";
import { getMapInfo } from "../map/mapInfo";
import MapCrop from "../components/MapCrop";
import Portrait from "../components/Portrait";
import { audioManager } from "../audio";
import { sfx } from "../sfx";

type ScenePhase = "initial" | "time" | "victim" | "map" | "suspects" | "title" | "cta";

export default function Intro({ onBegin }: { onBegin: () => void }) {
  const { caseOverview: c, agents } = useWorld();
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

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        audioManager.playStinger("ui_click");
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
      audioManager.playStinger("tension");
      sfx.stampThunk();
    }, 1000);

    const t2 = setTimeout(() => {
      setPhase("victim");
    }, 4500);

    const t3 = setTimeout(() => {
      setPhase("map");
      audioManager.playStinger("discovery");
    }, 9500);

    const t4 = setTimeout(() => {
      setPhase("suspects");
    }, 15000);

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
      if (witnesses.length > 0) {
        let count = 0;
        const interval = setInterval(() => {
          if (count < witnesses.length) {
            setVisibleSuspects(count + 1);
            sfx.pinPush();
            count++;
          } else {
            clearInterval(interval);
            setTimeout(() => {
              setPhase("title");
              audioManager.playStinger("drama");
            }, 1500);
          }
        }, 600); 
        return () => clearInterval(interval);
      } else {
        const t = setTimeout(() => {
          setPhase("title");
          audioManager.playStinger("drama");
        }, 1000);
        return () => clearTimeout(t);
      }
    }
  }, [phase, witnesses.length]);

  useEffect(() => {
    if (phase === "title") {
      const t5 = setTimeout(() => {
        setPhase("cta");
      }, 4500);
      return () => clearTimeout(t5);
    }
  }, [phase]);

  return (
    <div className="intro-scene">
      <button className="intro-skip" onClick={onBegin} title="Skip (Esc)">
        Skip ›
      </button>

      {/* Layer 1: Map/Location (Ken Burns) */}
      <div className={`cinematic-layer ${phase === "map" || phase === "suspects" || phase === "title" || phase === "cta" ? "active" : ""}`}>
        <div className="cinematic-map-container">
          {mapData ? (
            <MapCrop data={mapData} locationId={c.discovery_location.location_id} />
          ) : c.discovery_location.illustration ? (
            <img
              src={c.discovery_location.illustration}
              alt={c.discovery_location.name}
              draggable={false}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : null}
        </div>
      </div>

      {/* Layer 2: Time */}
      <div className={`cinematic-layer ${phase === "time" ? "active" : ""}`}>
        {phase === "time" && <p className="cinematic-time">{c.discovery_time}</p>}
      </div>

      {/* Layer 3: Victim */}
      <div className={`cinematic-layer ${phase === "victim" ? "active" : ""}`}>
        {phase === "victim" && (
          <div className="cinematic-victim">
            <Portrait agent={c.victim} />
            <h1>{c.victim.full_name} is dead.</h1>
          </div>
        )}
      </div>

      {/* Layer 4: Suspects */}
      <div className={`cinematic-layer ${phase === "suspects" ? "active" : ""}`}>
        {phase === "suspects" && (
          <div className="cinematic-suspects">
            {witnesses.map((w, idx) => (
              <div 
                key={w.agent_id} 
                className={`cinematic-suspect ${idx < visibleSuspects ? 'flash persist' : ''}`}
              >
                <Portrait agent={w} />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Layer 5: Title & CTA */}
      <div className={`cinematic-layer ${phase === "title" || phase === "cta" ? "active cinematic-cta-layer" : ""}`}>
        {(phase === "title" || phase === "cta") && (
          <div className="cinematic-title">
            No One Saw<br />Everything
            <span>A Generative Mystery</span>
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
