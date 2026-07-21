import { useEffect, useState, useMemo } from "react";
import { api, minutes } from "../api";
import { useWorld } from "../App";
import type { AccusationResult, MapReplayData } from "../types";
import VisualMap from "../components/VisualMap";
import MapTimeline from "../components/MapTimeline";
import AccusationBreakdown from "./AccusationBreakdown";
import Portrait from "../components/Portrait";
import { markersAt } from "../map/mapProjection";
import { audioManager } from "../audio";

export type CeremonyStep =
  | "suspense"
  | "killer"
  | "timeline"
  | "score"
  | "breakdown"
  | "epilogues"
  | "complete";

export default function AccusationCeremony({
  result,
  onPlayAgain,
}: {
  result: AccusationResult;
  onPlayAgain: () => void;
}) {
  const { caseOverview, agents } = useWorld();
  const [step, setStep] = useState<CeremonyStep>("suspense");
  const [mapData, setMapData] = useState<MapReplayData | null>(null);
  
  // Timeline playback state
  const startMin = minutes(caseOverview.sim_start_time);
  const endMin = minutes(caseOverview.discovery_time);
  const [t, setT] = useState(startMin);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [displayScore, setDisplayScore] = useState(0);

  // Determine killer agent for portrait
  const killerAgent = agents.find((a) => a.agent_id === result.true_killer_id);

  useEffect(() => {
    // Fetch map data for truth replay
    api.mapReplay({ mode: "truth" }).then((d) => setMapData(d)).catch(console.error);
    audioManager.playAmbient("accusation");
  }, []);

  // Score count-up animation
  useEffect(() => {
    if (step === "score") {
      let current = 0;
      const target = result.score;
      if (target === 0) {
        setDisplayScore(0);
        return;
      }
      const interval = setInterval(() => {
        current += Math.max(1, Math.floor(target / 20));
        if (current >= target) {
          current = target;
          clearInterval(interval);
          if (target >= 70) {
            audioManager.playStinger("case_solved");
          } else {
            audioManager.playStinger("case_failed");
          }
        }
        setDisplayScore(current);
      }, 50);
      return () => clearInterval(interval);
    }
  }, [step, result.score]);

  // Map replay playback loop
  useEffect(() => {
    if (!playing || step !== "timeline") return;
    const TICK_MS = 600;
    const id = setInterval(() => {
      setT((prev) => {
        if (prev >= endMin) {
          setPlaying(false);
          return endMin;
        }
        return prev + 1;
      });
    }, TICK_MS / speed);
    return () => clearInterval(id);
  }, [playing, speed, endMin, step]);

  const steps: CeremonyStep[] = ["suspense"];
  if (result.killer_correct) {
    steps.push("killer", "timeline");
  }
  steps.push("score", "breakdown");
  if (result.epilogues.length > 0) {
    steps.push("epilogues");
  }
  steps.push("complete");

  const currentIndex = steps.indexOf(step);
  const nextStep = () => {
    if (currentIndex < steps.length - 1) {
      setStep(steps[currentIndex + 1]);
    }
  };
  const skip = () => {
    setStep("complete");
  };

  // The opening card deliberately fills the screen, so give it a few clear
  // ways forward instead of relying on the small controls in the corner.
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (step !== "suspense") return;
      if (event.key === "Escape") {
        event.preventDefault();
        skip();
      } else if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        nextStep();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentIndex, steps.length, step]);

  const markers = useMemo(() => {
    if (!mapData) return [];
    return markersAt(mapData.events, t);
  }, [mapData, t]);

  const pastEvents = useMemo(() => {
    if (!mapData) return [];
    return mapData.events.filter((e) => minutes(e.time) <= t);
  }, [mapData, t]);

  // Adapter for true_timeline mapping if mapData is available
  // VisualMap requires pins, which we can get from agentPinsAt, but for simplicity
  // we just show the markers. Wait, we should probably show pins too.
  // Actually, MapReplay uses buildTracks(data). For the ceremony, we can just show markers.

  if (step === "complete") {
    return <AccusationBreakdown result={result} onPlayAgain={onPlayAgain} />;
  }

  return (
    <div className="ceremony-container">
      <div className="ceremony-controls">
        <button className="primary" onClick={nextStep}>
          Next
        </button>
        <button onClick={skip}>
          Skip Reveal
        </button>
      </div>

      <div className={`ceremony-content step-${step}`}>
        {step === "suspense" && (
          <div className="ceremony-suspense fade-in" onClick={nextStep}>
            <div>
              <p className="ceremony-suspense-kicker">CASE CLOSED</p>
              <h1>The truth is revealed...</h1>
              <button
                className="primary ceremony-suspense-action"
                onClick={(event) => {
                  event.stopPropagation();
                  nextStep();
                }}
              >
                Reveal the case <span aria-hidden="true">▸</span>
              </button>
              <p className="ceremony-suspense-hint">Click anywhere to continue · Esc to skip</p>
            </div>
          </div>
        )}

        {step === "killer" && (
          <div className="ceremony-killer fade-in scale-in">
            <h2>The Killer Is</h2>
            {killerAgent ? (
              <Portrait agent={killerAgent} pressure={0} size="large" />
            ) : (
              <div className="portrait legacy-emoji">?</div>
            )}
            <h1>{result.true_killer_name}</h1>
          </div>
        )}

        {step === "timeline" && (
          <div className="ceremony-timeline fade-in">
            <h2>The True Timeline</h2>
            {mapData ? (
              <div className="ceremony-map-wrapper">
                <VisualMap
                  data={mapData}
                  pins={[]} // We could pass pins here if we rebuild tracks
                  markers={markers}
                  selectedEventId={null}
                  selectedLocationId={null}
                  currentMinutes={t}
                  onSelectEvent={() => {}}
                  onSelectLocation={() => {}}
                  onSelectAgent={() => {}}
                />
                <MapTimeline
                  startMin={startMin}
                  endMin={endMin}
                  current={t}
                  playing={playing}
                  speed={speed}
                  murderWindow={caseOverview.murder_window}
                  onScrub={(v) => {
                    setT(v);
                    setPlaying(false);
                  }}
                  onTogglePlay={() => {
                    if (!playing && t >= endMin) setT(startMin);
                    setPlaying(!playing);
                  }}
                  onSpeed={setSpeed}
                />
                <div className="timeline-text-feed">
                  {pastEvents.map((e) => (
                    <div key={e.event_id} className="ceremony-event">
                      <span className="event-time">{e.time}</span>
                      <span>{e.description}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="ceremony-text-timeline">
                {result.true_timeline.map((e, i) => (
                  <div key={i} className="truth-event">
                    <span className="event-time">{e.time}</span>
                    <span>
                      {e.description}
                      <span className="muted small"> · {e.location_name}</span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {step === "score" && (
          <div className="ceremony-score fade-in">
            <h2>Detective Rating</h2>
            <div className="score-number">{displayScore}</div>
            <div className="detective-rating">{result.detective_rating} Rating</div>
            <div className="score-verdict">{result.verdict}</div>
          </div>
        )}

        {step === "breakdown" && (
          <div className="ceremony-breakdown fade-in">
            <h2>Breakdown</h2>
            <div className="reveal-grid">
              <div className="reveal-col panel">
                <h3>Key Clues Missed</h3>
                {result.key_clues_missed.length > 0 ? (
                  result.key_clues_missed.map((c) => (
                    <p key={c} className="small clue-missed">✕ {c}</p>
                  ))
                ) : (
                  <p className="small">You found all key clues!</p>
                )}
                {result.false_assumptions.length > 0 && (
                  <>
                    <h3 style={{marginTop: '1rem'}}>False Assumptions</h3>
                    {result.false_assumptions.map((f, i) => (
                      <p key={i} className="small clue-missed">• {f}</p>
                    ))}
                  </>
                )}
              </div>
              {result.killer_correct && (
                <div className="reveal-col panel">
                  <h3>Red Herrings</h3>
                  {result.red_herring_explanations.map((h) => (
                    <div key={h.agent_id} className="herring-card">
                      <strong>{h.agent_name}</strong>
                      <p className="small"><em>Looked guilty:</em> {h.looked_suspicious_because}</p>
                      <p className="small"><em>But:</em> {h.actually_innocent_because}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {step === "epilogues" && (
          <div className="ceremony-epilogues fade-in">
            <h2>Epilogue</h2>
            <div className="epilogues-grid">
              {result.epilogues.map((ep) => (
                <div key={ep.agent_id} className="epilogue-card panel">
                  <h3>{ep.agent_name}</h3>
                  <p>{ep.text}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
