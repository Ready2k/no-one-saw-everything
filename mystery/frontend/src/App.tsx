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
import LlmSettingsModal from "./views/LlmSettingsModal";
import { PlaytestPanel } from "./views/PlaytestPanel";
import AudioControls from "./components/AudioControls";
import CinematicsToggle from "./components/CinematicsToggle";
import RankBadge from "./components/RankBadge";
import { audioManager } from "./audio";
import { clearCaseStarted, markCaseStarted } from "./progress";
import { clearRewindBriefingSeen } from "./views/RewindIntro";

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
  { id: "overview", label: "Case File" },
  { id: "rewind", label: "Rewind" },
  { id: "map", label: "Map Replay" },
  { id: "places", label: "Places" },
  { id: "suspects", label: "Suspects" },
  { id: "board", label: "Case Board" },
] as const;

// "accuse" lives outside TABS: it renders as its own dramatic tab on the far
// right of the nav rail rather than in the routine investigation tabs.
type TabId = (typeof TABS)[number]["id"] | "accuse";

// The body-discovery intro plays once per case; the flag is cleared when a
// fresh investigation is started so a new session sees it again.
const introSeenKey = (caseId: string) => `mystery_intro_seen_${caseId}`;

export interface CaseMeta {
  case_id: string;
  title: string;
  case_type: string;
}

export default function App() {
  const [world, setWorld] = useState<World | null>(null);
  const [cases, setCases] = useState<CaseMeta[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("overview");
  const [showIntro, setShowIntro] = useState(false);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [showLlmSettingsModal, setShowLlmSettingsModal] = useState(false);
  const [mapJump, setMapJump] = useState<MapJump | null>(null);
  const [suspectFocus, setSuspectFocus] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.caseOverview(), api.agents(), api.locations(), api.cases()])
      .then(([caseOverview, agents, locations, availableCases]) => {
        setWorld({
          caseOverview,
          agents,
          locations,
          agentName: (id) =>
            agents.find((a) => a.agent_id === id)?.full_name ?? id,
          locationName: (id) =>
            locations.find((l) => l.location_id === id)?.name ?? id,
        });
        setCases(availableCases);
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
          <div className="masthead">
            <div className="brand">
              <span className="brand-eyebrow">Detective Bureau · Homicide Division</span>
              <span className="brand-title">No One Saw Everything</span>
            </div>
            <label className="case-docket" title="Open a different case file — current progress will be lost">
              <span className="docket-label">Case Nº</span>
              <select
                className="docket-select"
                value={world.caseOverview.case_id}
                onChange={async (e) => {
                  const newCaseId = e.target.value;
                  if (newCaseId === world.caseOverview.case_id) return;

                  const targetCase = cases.find((c) => c.case_id === newCaseId);
                  const caseTitle = targetCase ? targetCase.title : newCaseId;

                  if (confirm(`Switch to ${caseTitle}? Your current progress will be lost.`)) {
                    await api.activate(newCaseId);
                    localStorage.removeItem(introSeenKey(newCaseId));
                    clearRewindBriefingSeen(newCaseId);
                    clearCaseStarted(newCaseId);
                    location.reload();
                  }
                }}
              >
                {cases.map((c, index) => {
                  const prefix = c.case_id.startsWith("case_")
                    ? String(index + 1).padStart(3, "0")
                    : "Gen";
                  return (
                    <option key={c.case_id} value={c.case_id}>
                      {prefix} · {c.title}
                    </option>
                  );
                })}
              </select>
            </label>
            <div className="desk-tools">
              <RankBadge />
              <span className="tool-divider" />
              <CinematicsToggle />
              <AudioControls />
              <span className="tool-divider" />
              <button
                className="tool-btn"
                title="Wipe your notes and discoveries and work this case again from the start"
                onClick={async () => {
                  if (confirm("Start the investigation over? All notes and discoveries will be lost.")) {
                    await api.reset();
                    localStorage.removeItem(introSeenKey(world.caseOverview.case_id));
                    clearRewindBriefingSeen(world.caseOverview.case_id);
                    clearCaseStarted(world.caseOverview.case_id);
                    location.reload();
                  }
                }}
              >
                Reopen Case
              </button>
              <button
                className="tool-btn seal"
                title="Commission a brand-new case from the case writer"
                onClick={() => setShowGenerateModal(true)}
              >
                ✒ New Case
              </button>
              <button
                className="tool-btn icon-only"
                title="LLM settings — configure the model behind case generation and dialogue"
                aria-label="LLM settings"
                onClick={() => setShowLlmSettingsModal(true)}
              >
                ⚙
              </button>
            </div>
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
            <span className="tabs-case-note">{world.caseOverview.title}</span>
            <button
              className={tab === "accuse" ? "tab accuse active" : "tab accuse"}
              title="Name the killer — this closes the case"
              onClick={() => setTab("accuse")}
            >
              ⚖ Accuse
            </button>
          </nav>
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
      {showLlmSettingsModal && (
        <LlmSettingsModal onClose={() => setShowLlmSettingsModal(false)} />
      )}
      <PlaytestPanel />
      </UiNavContext.Provider>
    </WorldContext.Provider>
  );
}
