import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type { Board, CluePublic, Note, HintsResponse, MarkerType } from "../types";
import { ClaimRow, ClueCard } from "./shared";
import Portrait from "../components/Portrait";

export default function BoardView() {
  const { agents } = useWorld();
  const [board, setBoard] = useState<Board | null>(null);
  const [clues, setClues] = useState<CluePublic[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [noteType, setNoteType] = useState<Note["note_type"]>("manual");
  const [pinTo, setPinTo] = useState("");
  const [hints, setHints] = useState<HintsResponse | null>(null);

  const refresh = useCallback(() => {
    api.board().then(setBoard);
    api.clues().then(setClues);
    api.notes().then(setNotes);
    api.hints().then(setHints);
  }, []);

  useEffect(refresh, [refresh]);

  const addNote = async () => {
    if (!title.trim()) return;
    await api.createNote({
      note_type: noteType,
      title,
      body,
      pinned_to_agent_id: pinTo || null,
      linked_agent_ids: pinTo ? [pinTo] : [],
    });
    setTitle("");
    setBody("");
    refresh();
  };

  const toggleMarker = async (agentId: string, marker: MarkerType) => {
    if (!board) return;
    const currentMarkers = board.case_board_markers?.[agentId] || [];
    const hasMarker = currentMarkers.includes(marker);
    await api.updateMarkers({
      element_id: agentId,
      marker,
      action: hasMarker ? "remove" : "add"
    });
    refresh();
  };

  if (!board) return <p className="muted">Laying out the board…</p>;

  return (
    <div className="board">
      <div className="board-col">
        <h2>
          Suspects{" "}
          <span className="muted small">
            {board.discovered_clue_count}/{board.total_discoverable_clues} clues found
          </span>
        </h2>
        {board.suspects.map((s) => (
          <div key={s.agent.agent_id} className={`suspect-card suspicion-${s.suspicion}`}>
            <div className="suspect-card-head">
              <Portrait agent={s.agent} pressure={s.pressure ?? 0} />
              <div>
                <strong>{s.agent.full_name}</strong>
                <div className="muted small">{s.agent.occupation}</div>
              </div>
              <span className={`badge suspicion ${s.suspicion}`}>
                {s.suspicion.replace(/_/g, " ")}
              </span>
            </div>
            
            <div className="marker-toggles">
              <label>
                <input 
                  type="checkbox" 
                  checked={(board.case_board_markers?.[s.agent.agent_id] || []).includes("red_herring")}
                  onChange={() => toggleMarker(s.agent.agent_id, "red_herring")}
                />
                Red Herring
              </label>
              <label>
                <input 
                  type="checkbox" 
                  checked={(board.case_board_markers?.[s.agent.agent_id] || []).includes("cleared")}
                  onChange={() => toggleMarker(s.agent.agent_id, "cleared")}
                />
                Cleared
              </label>
              <label>
                <input 
                  type="checkbox" 
                  checked={(board.case_board_markers?.[s.agent.agent_id] || []).includes("prime_suspect")}
                  onChange={() => toggleMarker(s.agent.agent_id, "prime_suspect")}
                />
                Prime Suspect
              </label>
            </div>

            {s.claims.length > 0 && (
              <details>
                <summary>Claims ({s.claims.length})</summary>
                {s.claims.map((c) => (
                  <ClaimRow key={c.claim_id} claim={c} />
                ))}
              </details>
            )}
            {s.linked_clues.length > 0 && (
              <details>
                <summary>Linked evidence ({s.linked_clues.length})</summary>
                {s.linked_clues.map((c) => (
                  <p key={c.clue_id} className="small">
                    • {c.title}
                  </p>
                ))}
              </details>
            )}
            {s.pinned_notes.length > 0 && (
              <details open>
                <summary>Pinned notes ({s.pinned_notes.length})</summary>
                {s.pinned_notes.map((n) => (
                  <p key={n.note_id} className="small">
                    📌 {n.title}
                  </p>
                ))}
              </details>
            )}
          </div>
        ))}
      </div>

      <div className="board-col">
        <h2>Guidance</h2>
        {hints && (hints.tutorial_hints.length > 0 || hints.readiness_hints.length > 0) ? (
          <div className="panel guidance-panel">
            {hints.tutorial_hints.map((h, i) => (
              <p key={`tut-${i}`} className="tutorial-hint">💡 {h}</p>
            ))}
            {hints.readiness_hints.map((h, i) => (
              <p key={`read-${i}`} className="readiness-hint">🕵️ {h}</p>
            ))}
          </div>
        ) : (
          <p className="muted">You're doing great. Keep investigating.</p>
        )}

        <h2>Evidence</h2>
        {clues.length === 0 && <p className="muted">Nothing catalogued yet.</p>}
        {clues.map((c) => (
          <ClueCard key={c.clue_id} clue={c} />
        ))}
      </div>

      <div className="board-col">
        <h2>Notes</h2>
        <div className="note-form panel">
          <select value={noteType} onChange={(e) => setNoteType(e.target.value as Note["note_type"])}>
            <option value="manual">Note</option>
            <option value="contradiction">Contradiction</option>
            <option value="theory">Theory</option>
            <option value="question">Open question</option>
          </select>
          <select value={pinTo} onChange={(e) => setPinTo(e.target.value)}>
            <option value="">No pin</option>
            {agents
              .filter((a) => !a.is_victim)
              .map((a) => (
                <option key={a.agent_id} value={a.agent_id}>
                  Pin to {a.full_name}
                </option>
              ))}
          </select>
          <input
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <textarea
            placeholder="What doesn't add up?"
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <button className="primary" onClick={addNote} disabled={!title.trim()}>
            Add note
          </button>
        </div>
        {notes.map((n) => (
          <div key={n.note_id} className={`note-card type-${n.note_type}`}>
            <div className="note-head">
              <span className="badge">{n.note_type}</span>
              <button className="delete" onClick={() => api.deleteNote(n.note_id).then(refresh)}>
                ×
              </button>
            </div>
            <strong>{n.title}</strong>
            {n.body && <p className="small">{n.body}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
