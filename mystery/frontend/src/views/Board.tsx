import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type { Board, CluePublic, Note, HintsResponse, MarkerType } from "../types";
import { ClaimRow, ClueCard } from "./shared";
import Portrait from "../components/Portrait";

// A red thread from a pinned note to its suspect card, with a pin at each end.
interface BoardString {
  id: string;
  d: string;
  ax: number;
  ay: number;
  bx: number;
  by: number;
}

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
  const [strings, setStrings] = useState<BoardString[]>([]);

  const boardRef = useRef<HTMLDivElement | null>(null);
  const suspectRefs = useRef(new Map<string, HTMLDivElement>());
  const noteRefs = useRef(new Map<string, HTMLDivElement>());

  const refresh = useCallback(() => {
    api.board().then(setBoard);
    api.clues().then(setClues);
    api.notes().then(setNotes);
    api.hints().then(setHints);
  }, []);

  useEffect(refresh, [refresh]);

  const measureStrings = useCallback(() => {
    const container = boardRef.current;
    if (!container) return;
    const cRect = container.getBoundingClientRect();
    const next: BoardString[] = [];
    for (const n of notes) {
      if (!n.pinned_to_agent_id) continue;
      const noteEl = noteRefs.current.get(n.note_id);
      const suspectEl = suspectRefs.current.get(n.pinned_to_agent_id);
      if (!noteEl || !suspectEl) continue;
      const sR = suspectEl.getBoundingClientRect();
      const nR = noteEl.getBoundingClientRect();
      // Thread runs from the suspect card's right shoulder to the note's left.
      const ax = sR.right - cRect.left - 7;
      const ay = sR.top - cRect.top + 24;
      const bx = nR.left - cRect.left + 7;
      const by = nR.top - cRect.top + 18;
      // Quadratic curve with a sag proportional to the span, so the thread
      // hangs like string rather than shooting straight across.
      const sag = Math.min(70, Math.hypot(bx - ax, by - ay) * 0.16);
      const mx = (ax + bx) / 2;
      const my = (ay + by) / 2 + sag;
      next.push({ id: n.note_id, d: `M ${ax} ${ay} Q ${mx} ${my} ${bx} ${by}`, ax, ay, bx, by });
    }
    setStrings(next);
  }, [notes]);

  // Re-measure after data-driven layout changes have painted.
  useEffect(() => {
    const raf = requestAnimationFrame(measureStrings);
    return () => cancelAnimationFrame(raf);
  }, [measureStrings, board, clues, hints]);

  // Column heights move when <details> toggle or the window resizes.
  useEffect(() => {
    const container = boardRef.current;
    if (!container) return;
    const ro = new ResizeObserver(measureStrings);
    ro.observe(container);
    for (const child of Array.from(container.children)) ro.observe(child);
    return () => ro.disconnect();
  }, [measureStrings]);

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
    <div className="board" ref={boardRef}>
      {strings.length > 0 && (
        <svg className="board-strings" aria-hidden="true">
          <defs>
            <radialGradient id="board-pin-grad" cx="35%" cy="30%" r="75%">
              <stop offset="0%" stopColor="#e8836f" />
              <stop offset="100%" stopColor="#8f2a1c" />
            </radialGradient>
          </defs>
          {strings.map((s) => (
            <g key={s.id}>
              <path className="string-shadow" d={s.d} />
              <path className="string-thread" d={s.d} />
              <circle className="string-pin" cx={s.ax} cy={s.ay} r={4.5} />
              <circle className="string-pin" cx={s.bx} cy={s.by} r={4.5} />
            </g>
          ))}
        </svg>
      )}
      <div className="board-col">
        <h2>
          Suspects{" "}
          <span className="muted small">
            {board.discovered_clue_count}/{board.total_discoverable_clues} clues found
          </span>
        </h2>
        {board.suspects.map((s) => (
          <div
            key={s.agent.agent_id}
            className={`suspect-card suspicion-${s.suspicion}`}
            ref={(el) => {
              if (el) suspectRefs.current.set(s.agent.agent_id, el);
              else suspectRefs.current.delete(s.agent.agent_id);
            }}
          >
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
          <div
            key={n.note_id}
            className={`note-card type-${n.note_type}`}
            ref={(el) => {
              if (el) noteRefs.current.set(n.note_id, el);
              else noteRefs.current.delete(n.note_id);
            }}
          >
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
