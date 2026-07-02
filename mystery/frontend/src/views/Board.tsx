import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type { Board, CluePublic, Note } from "../types";
import { ClaimRow, ClueCard } from "./shared";

export default function BoardView() {
  const { agents } = useWorld();
  const [board, setBoard] = useState<Board | null>(null);
  const [clues, setClues] = useState<CluePublic[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [noteType, setNoteType] = useState<Note["note_type"]>("manual");
  const [pinTo, setPinTo] = useState("");

  const refresh = useCallback(() => {
    api.board().then(setBoard);
    api.clues().then(setClues);
    api.notes().then(setNotes);
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
              <span className="portrait">{s.agent.portrait}</span>
              <div>
                <strong>{s.agent.full_name}</strong>
                <div className="muted small">{s.agent.occupation}</div>
              </div>
              <span className={`badge suspicion ${s.suspicion}`}>
                {s.suspicion.replace(/_/g, " ")}
              </span>
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
