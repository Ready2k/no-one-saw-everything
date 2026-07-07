import { CaseMeta } from "../App";
import { api } from "../api";
import { clearCaseStarted } from "../progress";
import { clearRewindBriefingSeen } from "./RewindIntro";

interface NewCaseModalProps {
  cases: CaseMeta[];
  activeCaseId?: string;
  onClose: () => void;
}

const introSeenKey = (caseId: string) => `mystery_intro_seen_${caseId}`;

export default function NewCaseModal({ cases, activeCaseId, onClose }: NewCaseModalProps) {
  const handleSelectCase = async (newCaseId: string, caseTitle: string) => {
    if (newCaseId === activeCaseId) {
      alert("This case is already active.");
      return;
    }

    if (confirm(`Start investigation for ${caseTitle}? Your current progress on the active case will be lost.`)) {
      await api.activate(newCaseId);
      localStorage.removeItem(introSeenKey(newCaseId));
      clearRewindBriefingSeen(newCaseId);
      clearCaseStarted(newCaseId);
      location.reload();
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px', width: '90%', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #333", paddingBottom: "0.75rem", marginBottom: "1rem" }}>
          <h2 style={{ margin: 0 }}>Start a New Case</h2>
          <button type="button" className="btn-secondary" style={{ padding: "4px 8px", fontSize: "0.9rem" }} onClick={onClose}>Close</button>
        </div>
        <div style={{ padding: "0.5rem 0" }}>
          <p style={{ color: 'var(--muted)', marginBottom: '1.5rem' }}>
            Select a case file from the bureau archives. Standard cases are hand-crafted by the department, while GEN cases were commissioned from the AI Case Writer.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '50vh', overflowY: 'auto' }}>
            {cases.map((c, index) => {
              const isStandard = c.case_id.startsWith("case_");
              const prefix = isStandard
                ? `CASE Nº ${String(index + 1).padStart(3, "0")}`
                : "GEN CASE";

              return (
                <button
                  key={c.case_id}
                  onClick={() => handleSelectCase(c.case_id, c.title)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '1rem',
                    background: 'var(--panel)',
                    border: '1px solid var(--line)',
                    borderRadius: '4px',
                    textAlign: 'left'
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.7rem', color: isStandard ? 'var(--danger)' : 'var(--accent)', letterSpacing: '0.1em' }}>
                        {prefix}
                      </span>
                      {c.case_id === activeCaseId && (
                        <span style={{ fontSize: '0.7rem', color: 'var(--confirm)' }}>• ACTIVE</span>
                      )}
                    </div>
                    <span style={{ fontSize: '1.1rem', color: 'var(--text)', fontFamily: 'Copperplate' }}>{c.title}</span>
                  </div>
                  <span style={{ color: 'var(--muted)', fontSize: '1.2rem' }}>→</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
