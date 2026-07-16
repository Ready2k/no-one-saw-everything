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

const MENU_ITEMS = [
  { key: 'new', icon: '📁', label: 'New Case', desc: 'Commission a brand-new case from the writer' },
  { key: 'generate', icon: '🎲', label: 'Generate Case', desc: 'Configure a custom AI-generated scenario' },
  { key: 'library', icon: '📚', label: 'Case Library', desc: 'Browse and open your saved cases' },
  { key: 'settings', icon: '⚙️', label: 'Settings', desc: 'Audio, LLM, generation, and display prefs' },
] as const;

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

  const activeCasePrefix = activeCase?.case_id.startsWith('case_')
    ? `Case Nº ${activeCase.case_id.split('_')[1]}`
    : 'Gen Case';

  const menuHandlers: Record<(typeof MENU_ITEMS)[number]['key'], () => void> = {
    new: onOpenNewCase,
    generate: onOpenGenerateCase,
    library: onOpenLibrary,
    settings: onOpenSettings,
  };

  const openFolder = () => {
    sfx.pageTurn();
    onContinue();
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

  return (
    <div className="hub">
      <div className="hub-lamplight" aria-hidden="true" />

      <div className="hub-tools hub-in">
        <RankBadge />
        <span className="tool-divider" />
        <AudioControls />
      </div>

      <header className="hub-masthead">
        <p className="hub-eyebrow hub-in">Detective Bureau · Homicide Division</p>
        <h1 className="hub-title hub-in">
          No One Saw
          <br />
          Everything
        </h1>
        <div className="hub-rule hub-in" aria-hidden="true" />
        <p className="hub-tagline hub-in">Every minute. Every move. Someone knows something.</p>
      </header>

      <div className="hub-body hub-in">
        <section className="hub-desk">
          <div className="hub-folder">
            {activeCase ? (
              <>
                <span className="hub-folder-tab">On the desk</span>
                <span className="hub-stamp">Confidential</span>
                <div className="hub-folder-meta">
                  <span className="hub-case-no">{activeCasePrefix}</span>
                  <span className="hub-case-sep">•</span>
                  <span className="hub-case-status">In progress</span>
                </div>
                <h2 className="hub-case-title">{activeCase.title}</h2>
                <p className="hub-case-sub">Discovered {activeCase.discovery_time}</p>
                <button className="primary hub-continue" onClick={openFolder}>
                  Continue Investigation
                </button>
              </>
            ) : (
              <div className="hub-folder-empty">
                <p>No active case file on the desk.</p>
                <button className="primary" onClick={onOpenNewCase}>
                  Start a New Case
                </button>
              </div>
            )}
          </div>

          <nav className="hub-menu">
            {MENU_ITEMS.map((item) => (
              <button
                key={item.key}
                className="hub-menu-item"
                onClick={() => {
                  sfx.paperSlide();
                  menuHandlers[item.key]();
                }}
              >
                <span className="hub-menu-icon">{item.icon}</span>
                <span className="hub-menu-text">
                  <strong>{item.label}</strong>
                  <span>{item.desc}</span>
                </span>
                <span className="hub-menu-arrow" aria-hidden="true">
                  →
                </span>
              </button>
            ))}
          </nav>
        </section>

        <aside className="hub-archive">
          <h3 className="hub-archive-title">Recent Cases</h3>
          <div className="hub-archive-list">
            {cases.length > 0 ? (
              cases.slice(0, 4).map((c) => (
                <button
                  key={c.case_id}
                  className="hub-archive-row"
                  onClick={() => handleOpenCase(c.case_id)}
                  title={`Open ${c.title}`}
                >
                  <span className="hub-archive-name">{c.title}</span>
                  <span className="hub-archive-meta">
                    {c.case_type}
                    {c.progress?.accused ? (
                      <span className="hub-archive-progress"> • closed</span>
                    ) : c.progress && c.progress.clues_found > 0 ? (
                      <span className="hub-archive-progress">
                        {" "}
                        • in progress: {c.progress.clues_found}{" "}
                        {c.progress.clues_found === 1 ? "clue" : "clues"}
                      </span>
                    ) : null}
                    {activeCase?.case_id === c.case_id && (
                      <span className="hub-archive-active"> • Active</span>
                    )}
                  </span>
                </button>
              ))
            ) : (
              <p className="hub-archive-empty">No recent cases found in the archive.</p>
            )}
          </div>

          <button className="hub-howto" onClick={() => setShowGuide(true)}>
            <span className="hub-menu-icon">📖</span>
            <span className="hub-menu-text">
              <strong>How to Play</strong>
              <span>Review detective procedures</span>
            </span>
          </button>
        </aside>
      </div>

      {showGuide && <Detective101Modal onClose={() => setShowGuide(false)} />}
    </div>
  );
}
