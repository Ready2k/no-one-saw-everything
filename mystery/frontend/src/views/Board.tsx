import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type { Board, CluePublic, Note, HintsResponse, MarkerType } from "../types";
import { ClaimRow, ClueCard } from "./shared";
import Portrait from "../components/Portrait";
import { sfx } from "../sfx";

// A red thread from a pinned note to its suspect card, with a pin at each end.
interface BoardString {
  id: string;
  d: string;
  ax: number;
  ay: number;
  bx: number;
  by: number;
}

function caseLabel(caseId: string) {
  return caseId.startsWith("case_") ? `Case ${caseId.split("_")[1]}` : caseId;
}

function isBehaviourNote(note: Note) {
  if (note.player_tags?.includes("behaviour")) return true;
  if (note.note_type !== "interview") return false;
  return (
    /^Read on /.test(note.title) ||
    /\btell \((subtle|noticeable|strong)\)/.test(note.title) ||
    /\bchanged from earlier\b|\bsame as earlier\b|\bmanner noted\b|\bnothing like earlier\b/i.test(
      note.body
    )
  );
}

export default function BoardView() {
  const { agents, caseOverview } = useWorld();
  const [board, setBoard] = useState<Board | null>(null);
  const [clues, setClues] = useState<CluePublic[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [noteType, setNoteType] = useState<Note["note_type"]>("manual");
  const [pinTo, setPinTo] = useState("");
  const [hints, setHints] = useState<HintsResponse | null>(null);
  const [strings, setStrings] = useState<BoardString[]>([]);

  // Notetaking Toolbar States
  const [searchTerm, setSearchTerm] = useState("");
  const [activeFilter, setActiveFilter] = useState<
    "all" | "manual" | "contradiction" | "theory" | "question" | "behaviour" | "pinned"
  >("all");

  const boardRef = useRef<HTMLDivElement | null>(null);
  const suspectRefs = useRef(new Map<string, HTMLDivElement>());
  const noteRefs = useRef(new Map<string, HTMLDivElement>());

  const refresh = useCallback(() => {
    api.board().then(setBoard).catch(console.error);
    api.clues().then(setClues).catch(console.error);
    api.notes().then(setNotes).catch(console.error);
    api.hints().then(setHints).catch(console.error);
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
      // Quadratic curve with a sag proportional to the span
      const sag = Math.min(70, Math.hypot(bx - ax, by - ay) * 0.16);
      const mx = (ax + bx) / 2;
      const my = (ay + by) / 2 + sag;
      next.push({ id: n.note_id, d: `M ${ax} ${ay} Q ${mx} ${my} ${bx} ${by}`, ax, ay, bx, by });
    }
    setStrings(next);
  }, [notes]);

  useEffect(() => {
    const raf = requestAnimationFrame(measureStrings);
    return () => cancelAnimationFrame(raf);
  }, [measureStrings, board, clues, hints, notes, activeFilter, searchTerm]);

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
    sfx.pencilScratch();
    await api.createNote({
      note_type: noteType,
      title: title.trim(),
      body: body.trim(),
      pinned_to_agent_id: pinTo || null,
      linked_agent_ids: pinTo ? [pinTo] : [],
    });
    setTitle("");
    setBody("");
    refresh();
  };

  const applyStarterTemplate = (tmplTitle: string, tmplBody: string, defaultType: Note["note_type"]) => {
    sfx.click();
    setTitle(tmplTitle);
    setBody(tmplBody);
    setNoteType(defaultType);
  };

  const toggleMarker = async (agentId: string, marker: MarkerType) => {
    if (!board) return;
    sfx.pinPush();
    const currentMarkers = board.case_board_markers?.[agentId] || [];
    const hasMarker = currentMarkers.includes(marker);
    await api.updateMarkers({
      element_id: agentId,
      marker,
      action: hasMarker ? "remove" : "add",
    });
    refresh();
  };

  if (!board) return <p className="muted">Laying out the investigation board…</p>;

  // Filter notes based on activeFilter and searchTerm
  const filteredNotes = notes.filter((n) => {
    const matchesSearch =
      !searchTerm.trim() ||
      n.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      n.body.toLowerCase().includes(searchTerm.toLowerCase());

    if (!matchesSearch) return false;

    if (activeFilter === "all") return true;
    if (activeFilter === "pinned") return Boolean(n.pinned_to_agent_id);
    if (activeFilter === "behaviour") return isBehaviourNote(n);
    return n.note_type === activeFilter;
  });

  const pinnedNotesCount = notes.filter((n) => Boolean(n.pinned_to_agent_id)).length;
  const theoryNotesCount = notes.filter((n) => n.note_type === "theory").length;

  return (
    <div className="board-wrapper">
      {/* Master Top Header & Notetaking Toolbar */}
      <header className="board-master-header">
        <div className="board-header-top">
          <div className="board-header-titles">
            <div className="board-case-badge">
              <span className="case-no">{caseLabel(caseOverview.case_id)}</span>
              <span className="case-title">{caseOverview.title}</span>
            </div>
            <h1 className="board-page-title">Investigation Board & Notebook</h1>
          </div>

          <div className="board-summary-chips">
            <div className="summary-chip" title="Catalogued clues">
              <span className="chip-icon">🔎</span>
              <span className="chip-value">
                {board.discovered_clue_count}/{board.total_discoverable_clues}
              </span>
              <span className="chip-label">CLUES</span>
            </div>
            <div className="summary-chip" title="Total notebook entries">
              <span className="chip-icon">📓</span>
              <span className="chip-value">{notes.length}</span>
              <span className="chip-label">NOTES</span>
            </div>
            <div className="summary-chip" title="Notes pinned to suspects">
              <span className="chip-icon">📌</span>
              <span className="chip-value">{pinnedNotesCount}</span>
              <span className="chip-label">PINNED</span>
            </div>
            <div className="summary-chip" title="Active theories">
              <span className="chip-icon">💡</span>
              <span className="chip-value">{theoryNotesCount}</span>
              <span className="chip-label">THEORIES</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Corkboard Surface */}
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

        {/* Column 1: Suspect Roster & Thread Connections */}
        <div className="board-col">
          <h2>
            Suspect Pins{" "}
            <span className="muted small">
              {board.suspects.length} suspects
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
              {s.pinned_notes.length > 0 &&
                (() => {
                  const behaviourNotes = s.pinned_notes.filter(isBehaviourNote);
                  const evidenceNotes = s.pinned_notes.filter((n) => !isBehaviourNote(n));
                  return (
                    <>
                      {behaviourNotes.length > 0 && (
                        <details open className="behaviour-notes">
                          <summary>Behaviour ({behaviourNotes.length})</summary>
                          {behaviourNotes.map((n) => (
                            <p key={n.note_id} className="small behaviour-note-line">
                              <span>{n.title}</span>
                              {n.body && <em>{n.body.split("\n")[0]}</em>}
                            </p>
                          ))}
                        </details>
                      )}
                      {evidenceNotes.length > 0 && (
                        <details open>
                          <summary>Pinned evidence and notes ({evidenceNotes.length})</summary>
                          {evidenceNotes.map((n) => (
                            <p key={n.note_id} className="small">
                              {n.title}
                            </p>
                          ))}
                        </details>
                      )}
                    </>
                  );
                })()}
            </div>
          ))}
        </div>

        {/* Column 2: Guidance Briefing & Evidence Catalog */}
        <div className="board-col">
          <h2>Guidance Memo</h2>
          {hints && (hints.tutorial_hints.length > 0 || hints.readiness_hints.length > 0) ? (
            <div className="panel guidance-panel">
              <div className="guidance-head">
                <span className="guidance-stamp">CHIEF'S MEMO</span>
              </div>
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

          <h2>Evidence Catalog</h2>
          {clues.length === 0 && <p className="muted">Nothing catalogued yet.</p>}
          {clues.map((c) => (
            <ClueCard key={c.clue_id} clue={c} />
          ))}
        </div>

        {/* Column 3: Detective Notetaking Desk & Notebook Stream */}
        <div className="board-col">
          <h2>Notetaking Desk</h2>

          {/* Notetaking Form */}
          <div className="note-form panel">
            <div className="note-form-header">
              <span className="note-form-title">NEW NOTEBOOK ENTRY</span>
            </div>

            {/* Note Type Chip Selector */}
            <div className="note-type-chips">
              <button
                type="button"
                className={`type-chip ${noteType === "manual" ? "active" : ""}`}
                onClick={() => setNoteType("manual")}
              >
                📝 Note
              </button>
              <button
                type="button"
                className={`type-chip ${noteType === "contradiction" ? "active" : ""}`}
                onClick={() => setNoteType("contradiction")}
              >
                ⚡ Contradiction
              </button>
              <button
                type="button"
                className={`type-chip ${noteType === "theory" ? "active" : ""}`}
                onClick={() => setNoteType("theory")}
              >
                💡 Theory
              </button>
              <button
                type="button"
                className={`type-chip ${noteType === "question" ? "active" : ""}`}
                onClick={() => setNoteType("question")}
              >
                ❓ Question
              </button>
            </div>

            {/* Pin To Suspect Select */}
            <div className="note-form-row">
              <select value={pinTo} onChange={(e) => setPinTo(e.target.value)}>
                <option value="">No pin (General Note)</option>
                {agents
                  .filter((a) => !a.is_victim && !a.is_background)
                  .map((a) => (
                    <option key={a.agent_id} value={a.agent_id}>
                      📌 Pin to {a.full_name}
                    </option>
                  ))}
              </select>
            </div>

            {/* Quick Starter Templates */}
            <div className="note-form-templates">
              <span className="templates-label">Quick Prompts:</span>
              <button
                type="button"
                className="quick-template-chip"
                onClick={() =>
                  applyStarterTemplate(
                    "Alibi Discrepancy",
                    "Timeline at [Time] conflicts with witness testimony.",
                    "contradiction"
                  )
                }
              >
                + Alibi Discrepancy
              </button>
              <button
                type="button"
                className="quick-template-chip"
                onClick={() =>
                  applyStarterTemplate(
                    "Motive Theory",
                    "Has financial or personal reason regarding Clara.",
                    "theory"
                  )
                }
              >
                + Motive Theory
              </button>
              <button
                type="button"
                className="quick-template-chip"
                onClick={() =>
                  applyStarterTemplate(
                    "Witness Conflict",
                    "Statement contradicts physical evidence found at scene.",
                    "question"
                  )
                }
              >
                + Witness Conflict
              </button>
            </div>

            <input
              className="note-title-input"
              placeholder="Note title..."
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <textarea
              className="note-body-textarea"
              placeholder="What doesn't add up? Record your deduction..."
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
            <button
              type="button"
              className="primary add-note-btn"
              onClick={addNote}
              disabled={!title.trim()}
            >
              ✒️ Add Note to Notebook
            </button>
          </div>

          {/* Notebook Stream Toolbar & Filters */}
          <div className="notebook-stream-header">
            <h2>Notebook Entries</h2>

            <div className="notebook-toolbar">
              <input
                type="text"
                className="notebook-search-input"
                placeholder="🔍 Search notes..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />

              <div className="notebook-filter-bar">
                <button
                  type="button"
                  className={`notebook-filter-tab ${activeFilter === "all" ? "active" : ""}`}
                  onClick={() => setActiveFilter("all")}
                >
                  All ({notes.length})
                </button>
                <button
                  type="button"
                  className={`notebook-filter-tab ${activeFilter === "manual" ? "active" : ""}`}
                  onClick={() => setActiveFilter("manual")}
                >
                  Notes
                </button>
                <button
                  type="button"
                  className={`notebook-filter-tab ${activeFilter === "contradiction" ? "active" : ""}`}
                  onClick={() => setActiveFilter("contradiction")}
                >
                  Contradictions
                </button>
                <button
                  type="button"
                  className={`notebook-filter-tab ${activeFilter === "theory" ? "active" : ""}`}
                  onClick={() => setActiveFilter("theory")}
                >
                  Theories
                </button>
                <button
                  type="button"
                  className={`notebook-filter-tab ${activeFilter === "pinned" ? "active" : ""}`}
                  onClick={() => setActiveFilter("pinned")}
                >
                  Pinned ({pinnedNotesCount})
                </button>
              </div>
            </div>
          </div>

          {/* Filtered Notes List */}
          {filteredNotes.length === 0 ? (
            <p className="muted empty-notes-msg">
              {notes.length === 0
                ? "No entries written in your notebook yet."
                : "No notes matching your current filter."}
            </p>
          ) : (
            filteredNotes.map((n) => {
              const pinnedSuspect = agents.find((a) => a.agent_id === n.pinned_to_agent_id);
              return (
                <div
                  key={n.note_id}
                  className={`note-card type-${n.note_type}`}
                  ref={(el) => {
                    if (el) noteRefs.current.set(n.note_id, el);
                    else noteRefs.current.delete(n.note_id);
                  }}
                >
                  <div className="note-head">
                    <span className={`badge note-stamp type-${n.note_type}`}>
                      {isBehaviourNote(n) ? "BEHAVIOUR" : n.note_type.toUpperCase()}
                    </span>

                    {pinnedSuspect && (
                      <span className="pinned-suspect-tag" title={`Pinned to ${pinnedSuspect.full_name}`}>
                        📌 {pinnedSuspect.full_name.split(" ")[0]}
                      </span>
                    )}

                    <button
                      className="delete"
                      title="Delete note"
                      onClick={() => {
                        sfx.paperSlide();
                        api.deleteNote(n.note_id).then(refresh);
                      }}
                    >
                      ×
                    </button>
                  </div>

                  <strong className="note-card-title">{n.title}</strong>
                  {n.body && <p className="small note-card-body">{n.body}</p>}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
