import RankBadge from '../components/RankBadge';
import AudioControls from '../components/AudioControls';
import { CaseMeta, World } from '../App';
import { clearCaseStarted } from '../progress';
import { clearRewindBriefingSeen } from './RewindIntro';
import { api } from '../api';

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
  onOpenSettings 
}: LandingPageProps) {

  const activeCase = world?.caseOverview;
  
  // Format the active case number
  const activeCasePrefix = activeCase?.case_id.startsWith("case_")
    ? `CASE Nº ${activeCase.case_id.split('_')[1]}`
    : "GEN CASE";

  const handleOpenCase = async (newCaseId: string, caseTitle: string) => {
    if (activeCase && newCaseId === activeCase.case_id) {
      onContinue();
      return;
    }
    
    if (confirm(`Switch to ${caseTitle}? Your current progress on the active case will be lost.`)) {
      await api.activate(newCaseId);
      localStorage.removeItem(introSeenKey(newCaseId));
      clearRewindBriefingSeen(newCaseId);
      clearCaseStarted(newCaseId);
      location.reload();
    }
  };

  return (
    <div className="app" style={{ 
      background: 'radial-gradient(130% 90% at 50% 0%, rgba(216, 162, 74, 0.045), transparent 55%), radial-gradient(120% 120% at 50% 100%, #0d0e13 0%, transparent 60%), var(--bg)',
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '3rem 2rem',
      position: 'relative',
      overflow: 'hidden'
    }}>
      
      {/* Background atmosphere elements */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
        backgroundImage: 'radial-gradient(rgba(216, 162, 74, 0.05) 1px, transparent 1px)',
        backgroundSize: '40px 40px',
        opacity: 0.5,
        pointerEvents: 'none'
      }} />
      <div style={{
        position: 'absolute', top: '-10%', right: '-10%',
        width: '600px', height: '600px',
        border: '1px solid rgba(216, 162, 74, 0.03)',
        borderRadius: '50%',
        pointerEvents: 'none'
      }} />

      <div style={{ maxWidth: '900px', width: '100%', position: 'relative', zIndex: 1 }}>
        
        {/* Header Section */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '3rem' }}>
          <div className="brand" style={{ textAlign: 'left' }}>
            <span className="brand-eyebrow" style={{ fontSize: '0.65rem', letterSpacing: '0.4em' }}>Detective Bureau · Homicide Division</span>
            <span className="brand-title" style={{ fontSize: '2rem', marginTop: '0.5rem', textShadow: '0 2px 10px rgba(216, 162, 74, 0.2)' }}>No One Saw Everything</span>
            <p style={{ color: 'var(--accent)', fontStyle: 'italic', marginTop: '0.5rem', opacity: 0.8, fontSize: '0.9rem' }}>
              Every minute. Every move. Someone knows something.
            </p>
          </div>

          <div style={{ 
            background: 'rgba(20, 22, 29, 0.8)', 
            padding: '12px 20px', 
            borderRadius: '4px',
            border: '1px solid var(--line)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-end',
            boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <RankBadge />
              <div style={{ height: '24px', width: '1px', background: 'var(--line)' }} />
              <AudioControls />
            </div>
            {/* Optional XP display could go here if added to state later */}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '2rem' }}>
          
          {/* Left Column: Actions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            
            {/* Feature Panel: Current Case */}
            <div style={{
              background: 'url("data:image/svg+xml,%3Csvg width=\'100%25\' height=\'100%25\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noise\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.8\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noise)\' opacity=\'0.04\'/%3E%3C/svg%3E"), linear-gradient(145deg, #1d2029 0%, #161820 100%)',
              border: '1px solid rgba(200, 80, 60, 0.3)',
              borderRadius: '6px',
              padding: '2rem',
              position: 'relative',
              overflow: 'hidden',
              boxShadow: '0 8px 24px rgba(0,0,0,0.4)'
            }}>
              {activeCase ? (
                <>
                  <div style={{
                    position: 'absolute', top: '1.5rem', right: '-2rem',
                    transform: 'rotate(15deg)',
                    color: 'rgba(200, 80, 60, 0.8)',
                    border: '2px solid rgba(200, 80, 60, 0.8)',
                    padding: '4px 12px',
                    fontFamily: 'Courier New, monospace',
                    fontSize: '0.8rem',
                    fontWeight: 'bold',
                    letterSpacing: '0.2em',
                    textTransform: 'uppercase'
                  }}>
                    Confidential
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                    <span style={{ color: 'var(--danger)', fontSize: '0.75rem', letterSpacing: '0.1em' }}>{activeCasePrefix}</span>
                    <span style={{ color: 'var(--muted)' }}>•</span>
                    <span style={{ color: 'var(--confirm)', fontSize: '0.75rem', letterSpacing: '0.1em' }}>IN PROGRESS</span>
                  </div>
                  
                  <h2 style={{ fontFamily: 'Copperplate', fontSize: '1.8rem', color: 'var(--text)', margin: '0 0 0.5rem 0' }}>
                    {activeCase.title}
                  </h2>
                  <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginBottom: '2rem', fontStyle: 'italic' }}>
                    Discovered: {activeCase.discovery_time}
                  </p>

                  <button className="primary" onClick={onContinue} style={{ padding: '0.8rem 2rem', fontSize: '1rem', letterSpacing: '0.05em' }}>
                    Continue Investigation
                  </button>
                </>
              ) : (
                <div style={{ textAlign: 'center', padding: '2rem 0', color: 'var(--muted)' }}>
                  <p style={{ marginBottom: '1.5rem', fontStyle: 'italic' }}>No active case file on the desk.</p>
                  <button className="primary" onClick={onOpenNewCase}>
                    Start a New Case
                  </button>
                </div>
              )}
            </div>

            {/* Grid for other actions */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <button onClick={onOpenNewCase} style={{ 
                display: 'flex', flexDirection: 'column', alignItems: 'flex-start', 
                padding: '1.5rem', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: '4px', textAlign: 'left'
              }}>
                <span style={{ fontSize: '1.5rem', marginBottom: '0.75rem' }}>📁</span>
                <strong style={{ color: 'var(--text)', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>New Case</strong>
                <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>Commission a brand-new case from the writer</span>
              </button>

              <button onClick={onOpenGenerateCase} style={{ 
                display: 'flex', flexDirection: 'column', alignItems: 'flex-start', 
                padding: '1.5rem', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: '4px', textAlign: 'left'
              }}>
                <span style={{ fontSize: '1.5rem', marginBottom: '0.75rem' }}>🎲</span>
                <strong style={{ color: 'var(--text)', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>Generate Case</strong>
                <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>Configure a custom AI-generated scenario</span>
              </button>

              <button onClick={onOpenLibrary} style={{ 
                display: 'flex', flexDirection: 'column', alignItems: 'flex-start', 
                padding: '1.5rem', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: '4px', textAlign: 'left'
              }}>
                <span style={{ fontSize: '1.5rem', marginBottom: '0.75rem' }}>📚</span>
                <strong style={{ color: 'var(--text)', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>Case Library</strong>
                <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>Browse and open your saved cases</span>
              </button>

              <button onClick={onOpenSettings} style={{ 
                display: 'flex', flexDirection: 'column', alignItems: 'flex-start', 
                padding: '1.5rem', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: '4px', textAlign: 'left'
              }}>
                <span style={{ fontSize: '1.5rem', marginBottom: '0.75rem' }}>⚙️</span>
                <strong style={{ color: 'var(--text)', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>Settings</strong>
                <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>Audio, LLM, generation, and display prefs</span>
              </button>
            </div>

          </div>

          {/* Right Column: Recent Cases & Extras */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            
            <div style={{ 
              background: 'var(--panel)', 
              border: '1px solid var(--line)', 
              borderRadius: '4px',
              padding: '1.5rem'
            }}>
              <h3 style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.15em', color: 'var(--accent)', margin: '0 0 1rem 0' }}>
                Recent Cases
              </h3>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {cases.length > 0 ? cases.slice(0, 4).map((c, i) => (
                  <div 
                    key={c.case_id} 
                    onClick={() => handleOpenCase(c.case_id, c.title)}
                    style={{ 
                      display: 'flex', flexDirection: 'column', gap: '0.25rem', paddingBottom: '1rem', 
                      borderBottom: i < Math.min(cases.length, 4) - 1 ? '1px solid var(--line)' : 'none',
                      cursor: 'pointer'
                    }}
                    title={`Open ${c.title}`}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ color: 'var(--text)', fontSize: '0.95rem' }}>{c.title}</span>
                      <button style={{ padding: '2px 8px', fontSize: '0.75rem' }} onClick={(e) => {
                        e.stopPropagation();
                        handleOpenCase(c.case_id, c.title);
                      }}>Open</button>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.75rem' }}>
                      <span style={{ color: 'var(--muted)' }}>{c.case_type}</span>
                      {activeCase?.case_id === c.case_id && (
                        <span style={{ color: 'var(--confirm)' }}>• Active</span>
                      )}
                    </div>
                  </div>
                )) : (
                  <div style={{ color: 'var(--muted)', fontSize: '0.85rem', fontStyle: 'italic', padding: '1rem 0' }}>
                    No recent cases found in the archive.
                  </div>
                )}
              </div>
            </div>

            <button style={{ 
              background: 'transparent',
              border: '1px dashed var(--line)',
              color: 'var(--muted)',
              padding: '1.5rem',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              textAlign: 'left'
            }}
            onClick={() => alert("Detective Procedures manual coming soon.")}
            >
              <span style={{ fontSize: '1.5rem', color: 'var(--accent)' }}>📖</span>
              <div>
                <strong style={{ display: 'block', marginBottom: '0.25rem', color: 'var(--text)' }}>How to Play</strong>
                <span style={{ fontSize: '0.8rem' }}>Review detective procedures</span>
              </div>
            </button>

          </div>
        </div>

      </div>
    </div>
  );
}
