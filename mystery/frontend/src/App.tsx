import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { AgentPublic, CaseOverview, LocationPublic } from "./types";
import Overview from "./views/Overview";
import Rewind from "./views/Rewind";
import MapReplay from "./views/MapReplay";
import Places from "./views/Places";
import Suspects from "./views/Suspects";
import BoardView from "./views/Board";
import Accuse from "./views/Accuse";
import GenerateCaseModal from "./views/GenerateCaseModal";
import { PlaytestPanel } from "./views/PlaytestPanel";

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

export default function App() {
  const [world, setWorld] = useState<World | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("overview");
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
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error)
    return (
      <div className="app-loading">
        <p>Could not reach the investigation server.</p>
        <p className="muted">{error}</p>
      </div>
    );
  if (!world) return <div className="app-loading">Opening the case file…</div>;

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
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              className="reset"
              onClick={async () => {
                if (confirm("Start the investigation over? All notes and discoveries will be lost.")) {
                  await api.reset();
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
