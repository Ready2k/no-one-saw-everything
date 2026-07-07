import { useWorld } from "../App";
import RankBadge from "./RankBadge";
import AudioControls from "./AudioControls";

const TABS = [
  { id: "overview", label: "Case File" },
  { id: "rewind", label: "Rewind" },
  { id: "map", label: "Map Replay" },
  { id: "places", label: "Places" },
  { id: "suspects", label: "Suspects" },
  { id: "board", label: "Case Board" },
] as const;

type TabId = (typeof TABS)[number]["id"] | "accuse";

interface TopBarProps {
  currentTab: TabId;
  onTabChange: (tab: TabId) => void;
  onReturnToHub: () => void;
}

export default function TopBar({ currentTab, onTabChange, onReturnToHub }: TopBarProps) {
  const world = useWorld();

  return (
    <header className="topbar">
      <div className="masthead" style={{ borderBottom: 'none', paddingBottom: '0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span className="brand-eyebrow" style={{ color: 'var(--danger)' }}>
            {world.caseOverview.case_id.startsWith("case_") 
              ? `Case Nº ${world.caseOverview.case_id.split('_')[1]}` 
              : "Gen Case"}
          </span>
          <span style={{ color: 'var(--muted)' }}>-</span>
          <span style={{ fontStyle: 'italic', fontWeight: 'bold' }}>{world.caseOverview.title}</span>
        </div>

        <div className="desk-tools">
          <RankBadge />
          <span className="tool-divider" />
          <AudioControls />
          <span className="tool-divider" />
          
          <button 
            className="tool-btn" 
            title="Return to the Detective Bureau Hub"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            onClick={onReturnToHub}
          >
            <span>←</span>
            <span>Case Hub</span>
          </button>
        </div>
      </div>
      
      <nav className="tabs" style={{ marginTop: '0.5rem' }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            className={currentTab === t.id ? "tab active" : "tab"}
            onClick={() => onTabChange(t.id)}
          >
            {t.label}
          </button>
        ))}
        <span className="tabs-case-note"></span>
        <button 
          className={currentTab === "accuse" ? "tab accuse active" : "tab accuse"}
          onClick={() => onTabChange("accuse")}
        >
          ⚖ Accuse
        </button>
      </nav>
    </header>
  );
}
