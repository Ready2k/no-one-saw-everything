import { useWorld } from "../App";
import RankBadge from "./RankBadge";
import AudioControls from "./AudioControls";
import { sfx } from "../sfx";
import type { HintsResponse } from "../types";

const TABS = [
  { id: "overview", label: "Case File", cue: "Briefing" },
  { id: "rewind", label: "Rewind", cue: "Timeline" },
  { id: "map", label: "Map Replay", cue: "Movements" },
  { id: "places", label: "Places", cue: "Search" },
  { id: "suspects", label: "Suspects", cue: "Question" },
  { id: "board", label: "Case Board", cue: "Build Theory" },
] as const;

type TabId = (typeof TABS)[number]["id"] | "accuse";

interface TopBarProps {
  currentTab: TabId;
  onTabChange: (tab: TabId) => void;
  onReturnToHub: () => void;
  status: {
    discovered_clue_count: number;
    claim_count: number;
    challenge_count: number;
    accused: boolean;
  } | null;
  hints: HintsResponse | null;
}

const phaseCopy: Record<TabId, { label: string; text: string }> = {
  overview: {
    label: "Read the file",
    text: "Anchor the victim, place, discovery time, and murder window before chasing theories.",
  },
  rewind: {
    label: "Watch the window",
    text: "Filter the morning by time, place, and person. Pin movements that create opportunity or contradiction.",
  },
  map: {
    label: "Trace movement",
    text: "Follow routes across the village and look for impossible timing, blind spots, and suspicious detours.",
  },
  places: {
    label: "Search scenes",
    text: "Inspect relevant locations with the magnifier. Physical evidence turns hunches into leverage.",
  },
  suspects: {
    label: "Press testimony",
    text: "Ask free-form questions, compare claims, then confront lies with evidence or another witness's words.",
  },
  board: {
    label: "Assemble the case",
    text: "Mark suspects, pin notes, and check whether motive, method, and opportunity survive scrutiny.",
  },
  accuse: {
    label: "Make it count",
    text: "Only accuse when you can explain motive, method, opportunity, and the evidence tying them together.",
  },
};

function nextLead(
  currentTab: TabId,
  status: TopBarProps["status"],
  hints: HintsResponse | null
) {
  if (status?.accused) return "Case closed. Review the reveal or open another file from the hub.";
  const readiness = hints?.readiness_hints?.[0] ?? hints?.tutorial_hints?.[0];
  if (readiness) return readiness;
  if (!status || status.discovered_clue_count === 0) {
    return currentTab === "places"
      ? "Pick a location and sweep it for the first usable clue."
      : "Start by rewinding the murder window, then search the place where the trail feels warm.";
  }
  if (status.claim_count < 3) return "You have evidence. Question more suspects until their timelines start to overlap.";
  if (status.challenge_count === 0) return "You have claims on record. Look for one you can disprove with evidence or testimony.";
  return "Now test your theory on the board: motive, method, opportunity, and proof.";
}

export default function TopBar({
  currentTab,
  onTabChange,
  onReturnToHub,
  status,
  hints,
}: TopBarProps) {
  const world = useWorld();

  // Folder tabs slide a sheet of paper when a new one is opened
  const switchTab = (tab: TabId) => {
    if (tab !== currentTab) sfx.paperSlide();
    onTabChange(tab);
  };

  return (
    <header className="topbar">
      <div className="masthead" style={{ borderBottom: 'none', paddingBottom: '0' }}>
        <div className="masthead-case">
          <span className="masthead-case-no">
            {world.caseOverview.case_id.startsWith("case_")
              ? `Case Nº ${world.caseOverview.case_id.split('_')[1]}`
              : "Gen Case"}
          </span>
          <span className="masthead-case-title">{world.caseOverview.title}</span>
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
      
      <nav className="tabs investigation-rail">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={currentTab === t.id ? "tab active" : "tab"}
            onClick={() => switchTab(t.id)}
          >
            <span className="tab-label">{t.label}</span>
            <span className="tab-cue">{t.cue}</span>
          </button>
        ))}
        <section className="case-progress" aria-label="Investigation progress">
          <div className="case-progress-next">
            <span className="case-progress-kicker">{phaseCopy[currentTab].label}</span>
          </div>
          <div className="case-progress-stats">
            <span><strong>{status?.discovered_clue_count ?? 0}</strong> clues</span>
            <span><strong>{status?.claim_count ?? 0}</strong> claims</span>
            <span><strong>{status?.challenge_count ?? 0}</strong> contradictions</span>
          </div>
          <p className="case-progress-lead">{nextLead(currentTab, status, hints)}</p>
        </section>
        <button 
          className={currentTab === "accuse" ? "tab accuse active" : "tab accuse"}
          onClick={() => switchTab("accuse")}
        >
          <span className="tab-label">Accuse</span>
          <span className="tab-cue">Final Call</span>
        </button>
      </nav>
    </header>
  );
}
