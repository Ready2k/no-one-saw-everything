import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { AgentPublic, CaseOverview, LocationPublic } from "./types";
import Overview from "./views/Overview";
import Rewind from "./views/Rewind";
import Places from "./views/Places";
import Suspects from "./views/Suspects";
import BoardView from "./views/Board";
import Accuse from "./views/Accuse";

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

const TABS = [
  { id: "overview", label: "Case" },
  { id: "rewind", label: "Rewind" },
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
        </header>
        <main className="content">
          {tab === "overview" && <Overview onBegin={() => setTab("rewind")} />}
          {tab === "rewind" && <Rewind />}
          {tab === "places" && <Places />}
          {tab === "suspects" && <Suspects />}
          {tab === "board" && <BoardView />}
          {tab === "accuse" && <Accuse />}
        </main>
      </div>
    </WorldContext.Provider>
  );
}
