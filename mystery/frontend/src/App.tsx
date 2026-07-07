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
import NewCaseModal from "./views/NewCaseModal";
import CaseLibraryModal from "./views/CaseLibraryModal";
import LlmSettingsModal from "./views/LlmSettingsModal";
import { PlaytestPanel } from "./views/PlaytestPanel";
import LandingPage from "./views/LandingPage";
import TopBar from "./components/TopBar";
import { useToast } from "./components/Toast";
import { audioManager } from "./audio";
import { markCaseStarted } from "./progress";

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
  const [mode, setMode] = useState<"hub" | "investigation">("hub");
  const [tab, setTab] = useState<TabId>("overview");
  const [showIntro, setShowIntro] = useState(false);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [showNewCaseModal, setShowNewCaseModal] = useState(false);
  const [showLibraryModal, setShowLibraryModal] = useState(false);
  const [duplicateRecipe, setDuplicateRecipe] = useState<any>(null);
  const [showLlmSettingsModal, setShowLlmSettingsModal] = useState(false);
  const [mapJump, setMapJump] = useState<MapJump | null>(null);
  const [suspectFocus, setSuspectFocus] = useState<string | null>(null);
  const { showToast } = useToast();

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
    
  // While fetching initial world/cases state, show loading
  if (!world && !error) return <div className="app-loading">Loading Detective Bureau…</div>;

  const renderModals = () => (
    <>
      {showGenerateModal && (
        <GenerateCaseModal
          initialRecipe={duplicateRecipe}
          onClose={() => setShowGenerateModal(false)}
          onSuccess={(fallbackUsed) => {
            setShowGenerateModal(false);
            if (fallbackUsed) {
              showToast("Generated a validated case using safe deterministic fallback.", "info");
              setTimeout(() => location.reload(), 1200);
            } else {
              location.reload();
            }
          }}
        />
      )}
      {showNewCaseModal && (
        <NewCaseModal
          cases={cases}
          activeCaseId={world?.caseOverview.case_id}
          onClose={() => setShowNewCaseModal(false)}
        />
      )}
      {showLibraryModal && (
        <CaseLibraryModal
          onClose={() => setShowLibraryModal(false)}
          activeCaseId={world?.caseOverview.case_id ?? ""}
          onDuplicate={(recipe) => {
            setDuplicateRecipe(recipe);
            setShowLibraryModal(false);
            setShowGenerateModal(true);
          }}
        />
      )}
      {showLlmSettingsModal && (
        <LlmSettingsModal onClose={() => setShowLlmSettingsModal(false)} />
      )}
      <PlaytestPanel />
    </>
  );

  if (mode === "hub") {
    return (
      <>
        <LandingPage
          world={world}
          cases={cases}
          onContinue={() => setMode("investigation")}
          onOpenNewCase={() => setShowNewCaseModal(true)}
          onOpenGenerateCase={() => {
            setDuplicateRecipe(null);
            setShowGenerateModal(true);
          }}
          onOpenLibrary={() => setShowLibraryModal(true)}
          onOpenSettings={() => setShowLlmSettingsModal(true)}
        />
        {renderModals()}
      </>
    );
  }

  // The rest of the app requires world to be loaded
  if (!world) return null;

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
        <TopBar 
          currentTab={tab} 
          onTabChange={setTab} 
          onReturnToHub={() => setMode("hub")} 
        />
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
      {renderModals()}
      </UiNavContext.Provider>
    </WorldContext.Provider>
  );
}
