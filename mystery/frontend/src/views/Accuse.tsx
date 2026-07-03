import { useEffect, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type { AccusationResult, CluePublic, Note } from "../types";
import AccusationCeremony from "./AccusationCeremony";
import { audioManager } from "../audio";
import { recordCaseResult } from "../progress";

export default function Accuse() {
  const { agents, caseOverview } = useWorld();
  const living = agents.filter((a) => !a.is_victim);
  const [clues, setClues] = useState<CluePublic[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [result, setResult] = useState<AccusationResult | null>(null);
  const [busy, setBusy] = useState(false);

  // Persist to the local case-history log; duplicates (restored reveals,
  // re-renders) are deduped inside recordCaseResult by accusation id.
  useEffect(() => {
    if (result) recordCaseResult(result, caseOverview.title);
  }, [result, caseOverview.title]);

  const [accused, setAccused] = useState("");
  const [motive, setMotive] = useState("");
  const [method, setMethod] = useState("");
  const [opportunity, setOpportunity] = useState("");
  const [clueIds, setClueIds] = useState<Set<string>>(new Set());
  const [noteIds, setNoteIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    api.clues().then(setClues);
    api.notes().then(setNotes);
    // If an accusation was already made this session, show its reveal.
    api.status().then((s) => {
      if (s.accused) api.reveal().then(setResult);
    });
  }, []);

  const toggle = (set: Set<string>, id: string, setter: (s: Set<string>) => void) => {
    const next = new Set(set);
    next.has(id) ? next.delete(id) : next.add(id);
    setter(next);
  };

  const submit = async () => {
    setBusy(true);
    audioManager.playStinger("accusation_submitted");
    try {
      const res = await api.accuse({
        accused_agent_id: accused,
        motive_answer: motive,
        method_answer: method,
        opportunity_answer: opportunity,
        supporting_clue_ids: [...clueIds],
        supporting_note_ids: [...noteIds],
      });
      setResult(res);
    } finally {
      setBusy(false);
    }
  };

  if (result) return <AccusationCeremony result={result} onPlayAgain={async () => {
    await api.reset();
    location.reload();
  }} />;

  return (
    <div className="accuse">
      <div className="accuse-form panel">
        <h2>Name the killer</h2>
        <p className="muted">
          This is your final accusation. Once you submit, the truth is revealed and your
          reasoning is graded. Make it count.
        </p>

        <label className="field">
          <span>Who killed Marcus Bell?</span>
          <select value={accused} onChange={(e) => setAccused(e.target.value)}>
            <option value="">Choose a suspect…</option>
            {living.map((a) => (
              <option key={a.agent_id} value={a.agent_id}>
                {a.portrait} {a.full_name} — {a.occupation}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Motive — why did they do it?</span>
          <textarea value={motive} onChange={(e) => setMotive(e.target.value)} />
        </label>
        <label className="field">
          <span>Method — how was Marcus killed?</span>
          <textarea value={method} onChange={(e) => setMethod(e.target.value)} />
        </label>
        <label className="field">
          <span>Opportunity — how did they have the chance?</span>
          <textarea value={opportunity} onChange={(e) => setOpportunity(e.target.value)} />
        </label>

        <button className="primary accuse-submit" disabled={!accused || busy} onClick={submit}>
          {busy ? "Weighing the evidence…" : "Submit accusation"}
        </button>
      </div>

      <div className="accuse-evidence">
        <h3>Supporting evidence</h3>
        <p className="muted small">Cite the clues that prove your case.</p>
        {clues.length === 0 && <p className="muted">You haven't discovered any evidence yet.</p>}
        {clues.map((c) => (
          <label key={c.clue_id} className="evidence-check">
            <input
              type="checkbox"
              checked={clueIds.has(c.clue_id)}
              onChange={() => toggle(clueIds, c.clue_id, setClueIds)}
            />
            <span>
              <strong>{c.title}</strong>
              <span className="muted small"> {c.description.slice(0, 90)}…</span>
            </span>
          </label>
        ))}

        {notes.length > 0 && (
          <>
            <h3>Supporting notes</h3>
            {notes.map((n) => (
              <label key={n.note_id} className="evidence-check">
                <input
                  type="checkbox"
                  checked={noteIds.has(n.note_id)}
                  onChange={() => toggle(noteIds, n.note_id, setNoteIds)}
                />
                <span>
                  <span className="badge">{n.note_type}</span> {n.title}
                </span>
              </label>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

