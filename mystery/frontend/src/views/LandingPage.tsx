import { useEffect, useState } from 'react';
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
  const [isOpening, setIsOpening] = useState(false);
  const [devMapEditorEnabled, setDevMapEditorEnabled] = useState(false);

  useEffect(() => {
    let active = true;
    api.getConfig()
      .then((config) => {
        if (active) setDevMapEditorEnabled(config.dev_map_editor_enabled);
      })
      .catch(() => {
        if (active) setDevMapEditorEnabled(false);
      });
    return () => {
      active = false;
    };
  }, []);
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
  const reportLedger = activeCase
    ? [
        ['DISCOVERED', activeCase.discovery_time],
        ['LOCATION', activeCase.discovery_location.name],
        ['REPORTED BY', activeCase.discovered_by.full_name],
        ['MURDER WINDOW', `${activeCase.murder_window[0]} – ${activeCase.murder_window[1]}`],
      ]
    : [];
  const evidenceLabels = activeCase
    ? [
        `Scene · ${activeCase.discovery_location.name}`,
        `Filed · ${activeCase.discovered_by.full_name.split(' ')[0]}`,
        `Case · ${activeCase.case_id.replace(/^case_0?/, '')}`,
      ]
    : ['Scene detail', 'Witness record', 'Case note'];

  const openFolder = () => {
    if (isOpening) return;
    sfx.pageTurn();
    setIsOpening(true);
    window.setTimeout(onContinue, 170);
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

      {/* Bureau controls remain ordinary HTML controls, layered over the desk. */}
      <nav className="dh-rail dh-in" aria-label="Case bureau">
        <p className="dh-rail-label">On the desk</p>
        {activeCase && (
          <div className="dh-rail-case">
            <span>Case N° {activeCase.case_id.replace(/^case_0?/, '')}</span>
            <b>{statusLabel}</b>
          </div>
        )}
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
          {devMapEditorEnabled && (
            <a
              className="dh-rail-btn dh-map-editor"
              href="/dev/map-editor"
              onClick={() => sfx.paperSlide()}
            >
              <MapEditorGlyph />
              <span>Map Editor</span>
            </a>
          )}
        </div>
        <button className="dh-rail-btn dh-rail-foot" onClick={() => setShowGuide(true)}>
          <HelpGlyph />
          <span>How to Play</span>
        </button>
      </nav>

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
          {activeCase ? (
            <div className={`dh-folder${isOpening ? ' is-opening' : ''}`}>
              <div className="dh-document-slip" aria-hidden="true">
                <span>Evidence register</span>
                <i /><i /><i /><i />
              </div>
              <div className="dh-folder-body">
                <span className="dh-report-pin" aria-hidden="true" />
                <p className="dh-report-kicker">Field report · Case file</p>
                <h2 className="dh-report-title">{activeCase.title}</h2>
                <p className="dh-status">
                  RESIDENTS: {residentCount} <span className="dh-status-dot">·</span> STATUS: {statusLabel}
                </p>
                <p className="dh-flavour">{activeCase.overview_text}</p>
                <p className="dh-report-lead">Initial findings</p>
                <ul className="dh-report-findings" aria-label="Initial field notes">
                  <li>Scene evidence awaiting review</li>
                  <li>Statements require corroboration</li>
                  <li>A timeline has yet to be reconstructed</li>
                </ul>
                <span className="dh-report-name">Nadja Cole</span>
                <div className="dh-report-ledger" aria-label="Case details">
                  {reportLedger.map(([label, value]) => (
                    <p key={label}><b>{label}</b><span>{value}</span></p>
                  ))}
                </div>
              </div>

              <div className="dh-evidence-cluster" aria-label="Evidence photographs">
                <EvidencePhoto type="window" label={evidenceLabels[0]} />
                <EvidencePhoto type="door" label={evidenceLabels[1]} />
                <EvidencePhoto type="book" label={evidenceLabels[2]} />
              </div>
              <div className="dh-magnifier" aria-hidden="true" />

              <figure className="dh-character-photo" aria-label="Witness photograph, Nadja Cole">
                <span className="dh-photo-clip" aria-hidden="true" />
                <div className="dh-character-silhouette" />
                <figcaption>Nadja Cole</figcaption>
              </figure>
              <div className="dh-library-card" aria-hidden="true">
                <b>Reed &amp; Bell</b><span>Library card</span><em>Isabella Reed</em>
              </div>
              <div className="dh-receipt" aria-hidden="true">BOOKSHOP<br />13:15<br /><small>£2.75</small></div>
              <div className="dh-key" aria-hidden="true" />

              <div className="dh-folder-foot">
                <button className="primary dh-open" onClick={openFolder} disabled={isOpening}>
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

      <aside className="dh-archive dh-in" aria-label="Recent cases">
        <div className="dh-archive-stack">
          <div className="dh-archive-heading" aria-hidden="true">
            <span>Case Inbox</span>
            <i />
          </div>
          {recent.length > 0 ? (
            recent.map((c, i) => (
              <div
                key={c.case_id}
                className={`dh-archive-slot${c.case_id === activeCase?.case_id ? ' is-active' : ''}`}
                style={{ ['--i' as string]: i }}
              >
                <button
                  className="dh-archive-tab"
                  onClick={() => {
                    sfx.paperSlide();
                    handleOpenCase(c.case_id);
                  }}
                  title={`Open ${c.title}`}
                >
                  <span className="dh-archive-pin" aria-hidden="true" />
                  <span className="dh-archive-kicker">
                    {c.progress?.accused
                      ? 'Closed Case'
                      : c.progress && c.progress.clues_found > 0
                      ? 'Open Case'
                      : 'Recent Case'}
                  </span>
                  <span className="dh-archive-name">{c.title}</span>
                  <span className="dh-archive-tab-mark" aria-hidden="true" />
                </button>
              </div>
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

function EvidencePhoto({ type, label }: { type: 'window' | 'door' | 'book'; label: string }) {
  return (
    <figure className={`dh-evidence dh-evidence-${type}`} aria-label={label}>
      <span className="dh-evidence-image" aria-hidden="true" />
      <figcaption>{label}</figcaption>
    </figure>
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
function MapEditorGlyph() {
  return (
    <svg {...GLYPH} aria-hidden="true">
      <path d="M4.5 5.5 9 3.8l6 2.4 4.5-1.7v14L15 20.2 9 17.8l-4.5 1.7z" />
      <path d="M9 3.8v14M15 6.2v14" />
      <circle cx="12" cy="11.8" r="1.3" fill="currentColor" stroke="none" />
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
