import { useState } from 'react';
import RankBadge from '../components/RankBadge';
import AudioControls from '../components/AudioControls';
import { CaseMeta, World } from '../App';
import { clearCaseStarted } from '../progress';
import { clearRewindBriefingSeen } from './RewindIntro';
import { api } from '../api';
import Detective101Modal from './Detective101Modal';
import { sfx } from '../sfx';

interface LandingPageProps {
  world: World | null;
  cases: CaseMeta[];
  onContinue: () => void;
  onOpenNewCase: () => void;
  onOpenGenerateCase: () => void;
  onOpenLibrary: () => void;
  onOpenSettings: () => void;
}

const introSeenKey = (caseId: string) => `mystery_intro_seen_${caseId}`;

/** A quiet, ambiguous doorway — the mockup's polaroid. Deliberately generic and
 *  case-agnostic: it evokes the scene without ever displaying case truth, so the
 *  hub can never foreshadow a case the player hasn't opened. */
function PolaroidDoorway() {
  return (
    <svg viewBox="0 0 100 116" role="img" aria-label="A photograph of a doorway" preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id="dh-door-wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2b2620" />
          <stop offset="1" stopColor="#15120e" />
        </linearGradient>
        <linearGradient id="dh-door-panel" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#3a2f24" />
          <stop offset="0.5" stopColor="#241c14" />
          <stop offset="1" stopColor="#120d09" />
        </linearGradient>
        <radialGradient id="dh-door-vig" cx="0.5" cy="0.42" r="0.75">
          <stop offset="0.55" stopColor="rgba(0,0,0,0)" />
          <stop offset="1" stopColor="rgba(0,0,0,0.6)" />
        </radialGradient>
      </defs>
      <rect width="100" height="116" fill="url(#dh-door-wall)" />
      {/* door frame */}
      <rect x="24" y="10" width="52" height="106" fill="#1c160f" />
      <rect x="28" y="14" width="44" height="102" fill="url(#dh-door-panel)" />
      {/* panelling */}
      <rect x="34" y="22" width="14" height="34" fill="none" stroke="rgba(0,0,0,0.5)" strokeWidth="1.4" />
      <rect x="52" y="22" width="14" height="34" fill="none" stroke="rgba(0,0,0,0.5)" strokeWidth="1.4" />
      <rect x="34" y="64" width="14" height="42" fill="none" stroke="rgba(0,0,0,0.5)" strokeWidth="1.4" />
      <rect x="52" y="64" width="14" height="42" fill="none" stroke="rgba(0,0,0,0.5)" strokeWidth="1.4" />
      {/* brass handle catching the light */}
      <circle cx="63" cy="66" r="2.6" fill="#d8a24a" opacity="0.85" />
      <circle cx="63" cy="66" r="4.6" fill="none" stroke="rgba(216,162,74,0.35)" strokeWidth="1" />
      {/* a sliver of light under the door */}
      <rect x="28" y="113" width="44" height="3" fill="rgba(216,162,74,0.22)" />
      <rect width="100" height="116" fill="url(#dh-door-vig)" />
    </svg>
  );
}

export default function LandingPage({
  world,
  cases,
  onContinue,
  onOpenNewCase,
  onOpenGenerateCase,
  onOpenLibrary,
  onOpenSettings,
}: LandingPageProps) {
  const [showGuide, setShowGuide] = useState(false);
  const activeCase = world?.caseOverview;
  const activeCaseMeta = activeCase
    ? cases.find((c) => c.case_id === activeCase.case_id)
    : null;
  const hasMeaningfulProgress = Boolean(
    activeCaseMeta?.progress &&
      (activeCaseMeta.progress.clues_found > 0 ||
        activeCaseMeta.progress.suspects_interviewed > 0 ||
        activeCaseMeta.progress.notes > 0 ||
        activeCaseMeta.progress.hints_taken > 0 ||
        activeCaseMeta.progress.accused)
  );

  const residentCount = world?.agents.length ?? 0;
  const statusLabel = activeCaseMeta?.progress?.accused
    ? 'CLOSED'
    : hasMeaningfulProgress
    ? 'IN PROGRESS'
    : 'READY';

  const openFolder = () => {
    sfx.pageTurn();
    onContinue();
  };

  const restartActiveCase = async () => {
    if (!activeCase) return;
    if (
      !confirm(
        `Restart "${activeCase.title}" from the beginning? This will discard the current clues, notes, interviews, and accusation for this case.`
      )
    ) {
      return;
    }
    await api.activate(activeCase.case_id, true);
    localStorage.removeItem(introSeenKey(activeCase.case_id));
    clearRewindBriefingSeen(activeCase.case_id);
    clearCaseStarted(activeCase.case_id);
    location.reload();
  };

  /** Opening a case resumes it, and leaving one no longer destroys it — investigations are saved
   *  per case, so there is nothing to warn about and nothing to lose. */
  const handleOpenCase = async (newCaseId: string) => {
    if (activeCase && newCaseId === activeCase.case_id) {
      onContinue();
      return;
    }
    const { resumed } = await api.activate(newCaseId);
    // A resumed case should drop the player back into the investigation, not replay the intro.
    if (!resumed) {
      localStorage.removeItem(introSeenKey(newCaseId));
      clearRewindBriefingSeen(newCaseId);
      clearCaseStarted(newCaseId);
    }
    location.reload();
  };

  const railItems = [
    { key: 'new', label: 'New Case', glyph: NewCaseGlyph, onClick: onOpenNewCase },
    { key: 'generate', label: 'Generate', glyph: GenerateGlyph, onClick: onOpenGenerateCase },
    { key: 'library', label: 'Case Library', glyph: LibraryGlyph, onClick: onOpenLibrary },
    { key: 'settings', label: 'Settings', glyph: SettingsGlyph, onClick: onOpenSettings },
  ] as const;

  // The archive shows the four most recent cases as a stack of folder tabs.
  // Reversed so the topmost (first) tab sits in front of the stack.
  const recent = cases.slice(0, 5);

  return (
    <div className="dh">
      <div className="dh-lamp" aria-hidden="true" />
      <div className="dh-topo" aria-hidden="true" />

      {/* Left rail */}
      <nav className="dh-rail dh-in" aria-label="Case bureau">
        <div className="dh-rail-items">
          {railItems.map((item) => {
            const Glyph = item.glyph;
            return (
              <button
                key={item.key}
                className="dh-rail-btn"
                onClick={() => {
                  sfx.paperSlide();
                  item.onClick();
                }}
              >
                <Glyph />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
        <button className="dh-rail-btn dh-rail-foot" onClick={() => setShowGuide(true)}>
          <HelpGlyph />
          <span>How to Play</span>
        </button>
      </nav>

      {/* Centre desk */}
      <main className="dh-stage">
        <div className="dh-tools dh-in">
          <RankBadge />
          <span className="dh-tool-divider" />
          <AudioControls />
        </div>

        <header className="dh-masthead dh-in">
          <h1 className="dh-title">No One Saw Everything</h1>
          <p className="dh-tagline">Every perspective hides a lie</p>
        </header>

        <div className="dh-desk dh-in">
          <p className="dh-desk-label">On the Desk</p>

          {activeCase ? (
            <div className="dh-folder">
              <span className="dh-folder-tab">{activeCase.title}</span>

              <div className="dh-folder-body">
                <p className="dh-status">
                  RESIDENTS: {residentCount} <span className="dh-status-dot">·</span> STATUS: {statusLabel}
                </p>

                <figure className="dh-polaroid" aria-hidden="true">
                  <span className="dh-clip" />
                  <div className="dh-photo">
                    <PolaroidDoorway />
                  </div>
                </figure>

                <span className="dh-stamp">Classified</span>

                <p className="dh-flavour">{activeCase.overview_text}</p>
              </div>

              <div className="dh-folder-foot">
                <button className="primary dh-open" onClick={openFolder}>
                  {statusLabel === 'READY' ? 'Open Case' : 'Continue Case'}
                </button>
                <div className="dh-open-links">
                  <button className="dh-textlink" onClick={onOpenNewCase}>
                    Change case
                  </button>
                  {hasMeaningfulProgress && (
                    <button className="dh-textlink danger" onClick={restartActiveCase}>
                      Restart
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="dh-folder dh-folder-empty">
              <p>No active case file on the desk.</p>
              <button className="primary dh-open" onClick={onOpenNewCase}>
                Start a New Case
              </button>
            </div>
          )}
        </div>
      </main>

      {/* Right archive: a stack of recent-case folder tabs */}
      <aside className="dh-archive dh-in" aria-label="Recent cases">
        <div className="dh-archive-stack">
          {recent.length > 0 ? (
            recent.map((c, i) => (
              <button
                key={c.case_id}
                className={`dh-archive-tab${c.case_id === activeCase?.case_id ? ' is-active' : ''}`}
                style={{ ['--i' as string]: i }}
                onClick={() => handleOpenCase(c.case_id)}
                title={`Open ${c.title}`}
              >
                <span className="dh-archive-kicker">
                  {c.progress?.accused
                    ? 'Closed Case'
                    : c.progress && c.progress.clues_found > 0
                    ? 'Open Case'
                    : 'Recent Case'}
                </span>
                <span className="dh-archive-name">{c.title}</span>
              </button>
            ))
          ) : (
            <p className="dh-archive-empty">The archive is empty.</p>
          )}
        </div>
      </aside>

      {showGuide && <Detective101Modal onClose={() => setShowGuide(false)} />}
    </div>
  );
}

/* --- Rail glyphs: thin brass line icons, matched weight --- */
const GLYPH = {
  width: 20,
  height: 20,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

function NewCaseGlyph() {
  return (
    <svg {...GLYPH} aria-hidden="true">
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h3.7l1.6 2h7.7A1.5 1.5 0 0 1 20 7.5V18a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18z" />
      <path d="M12 10.5v5M9.5 13h5" />
    </svg>
  );
}
function GenerateGlyph() {
  return (
    <svg {...GLYPH} aria-hidden="true">
      <rect x="4.5" y="4.5" width="15" height="15" rx="2.5" />
      <circle cx="8.5" cy="8.5" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="15.5" cy="15.5" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none" />
    </svg>
  );
}
function LibraryGlyph() {
  return (
    <svg {...GLYPH} aria-hidden="true">
      <path d="M4 6.5A1.5 1.5 0 0 1 5.5 5h3.5l1.5 1.8h8A1.5 1.5 0 0 1 20 8.3V17a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17z" />
    </svg>
  );
}
function SettingsGlyph() {
  return (
    <svg {...GLYPH} aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v2.2M12 18.8V21M4.6 7.5l1.9 1.1M17.5 15.4l1.9 1.1M4.6 16.5l1.9-1.1M17.5 8.6l1.9-1.1" />
    </svg>
  );
}
function HelpGlyph() {
  return (
    <svg {...GLYPH} aria-hidden="true">
      <circle cx="12" cy="12" r="8.2" />
      <path d="M9.6 9.4a2.4 2.4 0 0 1 4.7.6c0 1.6-2.3 2-2.3 3.4" />
      <circle cx="12" cy="16.4" r="0.5" fill="currentColor" stroke="none" />
    </svg>
  );
}
