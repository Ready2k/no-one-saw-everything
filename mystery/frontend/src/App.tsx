import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { AgentPublic, CaseOverview, LocationPublic } from "./types";
import Intro from "./views/Intro";
import Overview from "./views/Overview";
import Rewind from "./views/Rewind";
import MapReplay from "./views/MapReplay";
import Places from "./views/Places";
import Suspects from "./views/Suspects";
import BoardView from "./views/Board";
import Accuse from "./views/Accuse";
import GenerateCaseModal from "./views/GenerateCaseModal";
import { PlaytestPanel } from "./views/PlaytestPanel";
import AudioControls from "./components/AudioControls";
import CinematicsToggle from "./components/CinematicsToggle";
import RankBadge from "./components/RankBadge";
import { audioManager } from "./audio";
import { clearCaseStarted, markCaseStarted } from "./progress";

export interface World {
  caseOverview: CaseOverview;
  agents: AgentPublic[];
  locations: LocationPublic[];
  agentName: (id: string) => string;
  locationName: (id: string) => string;
}

const WorldContext = createContext<World | null>(null);

export function useWorld(): World {
  const world = useContext(WorldContext);
  if (!world) throw new Error("World not loaded");
  return world;
}

// Cross-view navigation: lets a case-board clue jump to the map, and the
// map open a suspect's profile.
export interface MapJump {
  locationId?: string;
  time?: string;
  eventId?: string;
}

interface UiNav {
  jumpToMap: (jump: MapJump) => void;
}

const UiNavContext = createContext<UiNav>({ jumpToMap: () => {} });

export function useUiNav(): UiNav {
  return useContext(UiNavContext);
}

const TABS = [
  { id: "overview", label: "Case" },
  { id: "rewind", label: "Rewind" },
  { id: "map", label: "Map Replay" },
  { id: "places", label: "Places" },
  { id: "suspects", label: "Suspects" },
  { id: "board", label: "Case Board" },
  { id: "accuse", label: "Accuse" },
] as const;

type TabId = (typeof TABS)[number]["id"];

// The body-discovery intro plays once per case; the flag is cleared when a
// fresh investigation is started so a new session sees it again.
const introSeenKey = (caseId: string) => `mystery_intro_seen_${caseId}`;

export default function App() {
  const [world, setWorld] = useState<World | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("overview");
  const [showIntro, setShowIntro] = useState(false);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [mapJump, setMapJump] = useState<MapJump | null>(null);
  const [suspectFocus, setSuspectFocus] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.caseOverview(), api.agents(), api.locations()])
      .then(([caseOverview, agents, locations]) => {
        setWorld({
          caseOverview,
          agents,
          locations,
          agentName: (id) =>
            agents.find((a) => a.agent_id === id)?.full_name ?? id,
          locationName: (id) =>
            locations.find((l) => l.location_id === id)?.name ?? id,
        });
        setShowIntro(!localStorage.getItem(introSeenKey(caseOverview.case_id)));
        markCaseStarted(caseOverview.case_id);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (tab !== "accuse") {
      audioManager.playAmbient("investigation");
    }
  }, [tab]);

  if (error)
    return (
      <div className="app-loading">
        <p>Could not reach the investigation server.</p>
        <p className="muted">{error}</p>
      </div>
    );
  if (!world) return <div className="app-loading">Opening the case file…</div>;

  if (showIntro) {
    return (
      <WorldContext.Provider value={world}>
        <Intro
          onBegin={() => {
            localStorage.setItem(introSeenKey(world.caseOverview.case_id), "1");
            setShowIntro(false);
            setTab("overview");
          }}
        />
      </WorldContext.Provider>
    );
  }

  return (
    <WorldContext.Provider value={world}>
      <UiNavContext.Provider
        value={{
          jumpToMap: (jump) => {
            setMapJump(jump);
            setTab("map");
          },
        }}
      >
      <div className="app">
        <header className="topbar">
          <div className="brand">
            <span className="brand-title">No One Saw Everything</span>
            <span className="brand-case">{world.caseOverview.title}</span>
          </div>
          <nav className="tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={tab === t.id ? "tab active" : "tab"}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </nav>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <RankBadge />
            <CinematicsToggle />
            <AudioControls />
            <select
              value={world.caseOverview.case_id}
              onChange={async (e) => {
                const newCaseId = e.target.value;
                if (newCaseId === world.caseOverview.case_id) return;
                
                const caseNames: Record<string, string> = {
                  case_001: "Case 1: The Storage Room Murder",
                  case_002: "Case 2: The Locked Bookshop",
                  case_003: "Case 3: The Clinic After Hours",
                  case_004: "Case 4: The Fountain at Midnight",
                  case_005: "Case 5: The Rear Alley Fire",
                  case_006: "Case 6: The Bell Estate",
                };
                
                if (confirm(`Switch to ${caseNames[newCaseId]}? Your current progress will be lost.`)) {
                  await api.activate(newCaseId);
                  localStorage.removeItem(introSeenKey(newCaseId));
                  clearCaseStarted(newCaseId);
                  location.reload();
                }
              }}
              style={{
                background: "var(--bg-panel)",
                color: "var(--text)",
                border: "1px solid var(--border)",
                borderRadius: "4px",
                padding: "4px 8px",
                cursor: "pointer",
                outline: "none"
              }}
            >
              <option value="case_001">Case 1: Storage Room Murder</option>
              <option value="case_002">Case 2: Locked Bookshop</option>
              <option value="case_003">Case 3: Clinic After Hours</option>
              <option value="case_004">Case 4: Fountain at Midnight</option>
              <option value="case_005">Case 5: Rear Alley Fire</option>
              <option value="case_006">Case 6: The Bell Estate</option>
            </select>
            <button
              className="reset"
              onClick={async () => {
                if (confirm("Start the investigation over? All notes and discoveries will be lost.")) {
                  await api.reset();
                  localStorage.removeItem(introSeenKey(world.caseOverview.case_id));
                  clearCaseStarted(world.caseOverview.case_id);
                  location.reload();
                }
              }}
            >
              New investigation
            </button>
            <button
              className="primary"
              onClick={() => setShowGenerateModal(true)}
            >
              Generate Case
            </button>
          </div>
        </header>
        <main className="content">
          {tab === "overview" && <Overview onBegin={() => setTab("rewind")} />}
          {tab === "rewind" && <Rewind />}
          {tab === "map" && (
            <MapReplay
              jump={mapJump}
              onConsumeJump={() => setMapJump(null)}
              onOpenSuspect={(agentId) => {
                setSuspectFocus(agentId);
                setTab("suspects");
              }}
            />
          )}
          {tab === "places" && <Places />}
          {tab === "suspects" && <Suspects focusAgentId={suspectFocus} />}
          {tab === "board" && <BoardView />}
          {tab === "accuse" && <Accuse />}
        </main>
      </div>
      {showGenerateModal && (
        <GenerateCaseModal
          onClose={() => setShowGenerateModal(false)}
          onSuccess={(fallbackUsed) => {
            setShowGenerateModal(false);
            // alert blocks until dismissed, so it is visible before the reload.
            if (fallbackUsed) {
              alert("Generated a validated case using safe deterministic fallback.");
            }
            location.reload();
          }}
        />
      )}
      <PlaytestPanel />
      </UiNavContext.Provider>
    </WorldContext.Provider>
  );
}
