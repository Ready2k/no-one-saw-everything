import { useCallback, useEffect, useRef, useState } from "react";
import { api, minutes } from "../api";
import { useWorld } from "../App";
import type { Board, CluePublic, Note, HintsResponse, MarkerType, EventPublic } from "../types";
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

type BoardMode = "summary" | "evidence" | "timeline" | "connections" | "contradictions" | "theory" | "notebook" | "recall" | "workspace";
type TimelineLane = "before" | "during" | "after";

interface TimelineFact {
  id: string;
  label: string;
  detail: string;
  kind: "event" | "statement";
  time?: string | null;
  eventId?: string;
}

interface ConnectionEdge {
  id: string;
  fromId: string;
  toId: string;
  label: string;
  source: "statement" | "evidence" | "note";
}

interface RecallCard {
  id: string;
  prompt: string;
  answer: string;
  source: string;
}

const TIMELINE_LANES: Array<{ id: TimelineLane; label: string; description: string }> = [
  { id: "before", label: "Before", description: "Before the murder window" },
  { id: "during", label: "During", description: "Inside the murder window" },
  { id: "after", label: "After", description: "After the murder window" },
];

const EVIDENCE_GROUPS: Array<{ key: string; label: string; clueTypes: string[] }> = [
  { key: "physical", label: "Physical evidence", clueTypes: ["physical_evidence", "document", "object_trail"] },
  { key: "testimony", label: "Testimony", clueTypes: ["witness_statement", "confession"] },
  { key: "observation", label: "Observations", clueTypes: ["observation"] },
];

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
  const { agents, caseOverview, locations } = useWorld();
  const [board, setBoard] = useState<Board | null>(null);
  const [clues, setClues] = useState<CluePublic[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [noteType, setNoteType] = useState<Note["note_type"]>("manual");
  const [pinTo, setPinTo] = useState("");
  const [hints, setHints] = useState<HintsResponse | null>(null);
  const [strings, setStrings] = useState<BoardString[]>([]);
  const [boardMode, setBoardMode] = useState<BoardMode>("summary");
  const [theorySuspectId, setTheorySuspectId] = useState("");
  const [theoryClueId, setTheoryClueId] = useState("");
  const [theoryReason, setTheoryReason] = useState("");
  const [compareClaimId, setCompareClaimId] = useState("");
  const [compareClueId, setCompareClueId] = useState("");
  const [compareReason, setCompareReason] = useState("");
  const [noteComposerOpen, setNoteComposerOpen] = useState(false);
  const [timelineEvents, setTimelineEvents] = useState<EventPublic[]>([]);
  const [timelinePlacements, setTimelinePlacements] = useState<Record<string, TimelineLane>>({});
  const [selectedTimelineFactId, setSelectedTimelineFactId] = useState<string | null>(null);
  const [timelineNotice, setTimelineNotice] = useState<string | null>(null);
  const [activeConnectionAgentId, setActiveConnectionAgentId] = useState<string | null>(null);
  const [revealedRecallIds, setRevealedRecallIds] = useState<Set<string>>(new Set());

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

  useEffect(() => {
    api.events({ time_from: caseOverview.sim_start_time, time_to: caseOverview.discovery_time })
      .then(setTimelineEvents)
      .catch(console.error);
    setTimelinePlacements({});
    setSelectedTimelineFactId(null);
    setTimelineNotice(null);
  }, [caseOverview.case_id, caseOverview.sim_start_time, caseOverview.discovery_time]);

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

  const saveQuickThought = async () => {
    if (!title.trim()) return;
    sfx.pencilScratch();
    await api.createNote({
      note_type: "manual",
      title: title.trim(),
      body: body.trim(),
      pinned_to_agent_id: null,
      linked_agent_ids: [],
    });
    setTitle("");
    setBody("");
    setNoteComposerOpen(false);
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

  const saveStructuredTheory = async () => {
    const suspect = agents.find((agent) => agent.agent_id === theorySuspectId);
    const clue = clues.find((item) => item.clue_id === theoryClueId);
    if (!suspect || !clue) return;
    sfx.pencilScratch();
    await api.createNote({
      note_type: "theory",
      title: `Theory: ${suspect.full_name}`,
      body: `${clue.title} may connect ${suspect.full_name} to this case.${theoryReason.trim() ? ` ${theoryReason.trim()}` : ""}`,
      pinned_to_agent_id: suspect.agent_id,
      linked_agent_ids: [suspect.agent_id],
    });
    setTheoryReason("");
    refresh();
    setBoardMode("summary");
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
  const latestClue = clues[clues.length - 1];
  const linkedPeople = latestClue
    ? agents.filter((agent) => latestClue.linked_agent_ids.includes(agent.agent_id) && !agent.is_victim)
    : [];
  const linkedPlaces = latestClue?.linked_location_ids
    .map((locationId) => locations.find((location) => location.location_id === locationId)?.name)
    .filter((name): name is string => Boolean(name)) ?? [];
  const disputedClaims = board.suspects.flatMap((suspect) =>
    suspect.claims
      .filter((claim) => claim.player_known_status === "disputed")
      .map((claim) => ({ claim, suspect }))
  );
  const comparisonNotes = notes.filter((note) => note.player_tags?.includes("comparison"));
  const nextLead = disputedClaims[0]
    ? {
        heading: `Test ${disputedClaims[0].suspect.agent.full_name}'s disputed statement`,
        body: `“${disputedClaims[0].claim.claim_text}” is already in conflict with something you have found. Put the conflict to them before treating it as proof.`,
        action: "Review conflicts",
        mode: "contradictions" as BoardMode,
      }
    : comparisonNotes[0]
      ? {
          heading: "Test your recorded comparison",
          body: comparisonNotes[0].body,
          action: "Open comparison",
          mode: "contradictions" as BoardMode,
        }
      : latestClue
        ? {
            heading: "Follow the latest lead",
            body: `Your latest evidence is ${latestClue.title}. ${latestClue.description}`,
            action: "Review evidence",
            mode: "evidence" as BoardMode,
          }
        : {
            heading: "Find your first lead",
            body: "Search the discovery scene for your first physical clue, then return here to connect it to the case.",
            action: "Open investigation tools",
            mode: "workspace" as BoardMode,
          };
  const evidenceGroups = EVIDENCE_GROUPS.map((group) => ({
    ...group,
    clues: clues.filter((clue) => group.clueTypes.includes(clue.clue_type)),
  }));
  const ungroupedClues = clues.filter(
    (clue) => !EVIDENCE_GROUPS.some((group) => group.clueTypes.includes(clue.clue_type))
  );
  const theoryReady = Boolean(theorySuspectId && theoryClueId);
  const allClaims = board.suspects.flatMap((suspect) =>
    suspect.claims.map((claim) => ({ claim, suspect }))
  );
  const recallCards: RecallCard[] = [
    ...allClaims.map(({ claim, suspect }) => ({
      id: `claim:${claim.claim_id}`,
      prompt: `Who made this statement? “${claim.claim_text}”`,
      answer: suspect.agent.full_name,
      source: "Statement on record",
    })),
    ...clues.map((clue) => ({
      id: `clue:${clue.clue_id}`,
      prompt: `What did this evidence point you toward? “${clue.title}”`,
      answer: [
        ...clue.linked_agent_ids.map((id) => agents.find((agent) => agent.agent_id === id)?.full_name),
        ...clue.linked_location_ids.map((id) => locations.find((location) => location.location_id === id)?.name),
      ].filter(Boolean).join(" · ") || "No person or place link recorded yet",
      source: "Evidence catalogued",
    })),
  ].slice(0, 8);
  const connectionEdges = (() => {
    const edges = new Map<string, ConnectionEdge>();
    const add = (edge: ConnectionEdge) => edges.set(edge.id, edge);
    for (const { claim } of allClaims) {
      if (claim.speaker_agent_id !== claim.about_agent_id) {
        add({
          id: `claim:${claim.claim_id}`,
          fromId: claim.speaker_agent_id,
          toId: claim.about_agent_id,
          label: claim.claim_text,
          source: "statement",
        });
      }
    }
    for (const clue of clues) {
      for (let index = 0; index < clue.linked_agent_ids.length; index += 1) {
        for (let otherIndex = index + 1; otherIndex < clue.linked_agent_ids.length; otherIndex += 1) {
          const [fromId, toId] = [clue.linked_agent_ids[index], clue.linked_agent_ids[otherIndex]].sort();
          add({ id: `clue:${clue.clue_id}:${fromId}:${toId}`, fromId, toId, label: clue.title, source: "evidence" });
        }
      }
    }
    for (const note of notes) {
      for (let index = 0; index < note.linked_agent_ids.length; index += 1) {
        for (let otherIndex = index + 1; otherIndex < note.linked_agent_ids.length; otherIndex += 1) {
          const [fromId, toId] = [note.linked_agent_ids[index], note.linked_agent_ids[otherIndex]].sort();
          add({ id: `note:${note.note_id}:${fromId}:${toId}`, fromId, toId, label: note.title, source: "note" });
        }
      }
    }
    return [...edges.values()];
  })();
  const connectedAgentIds = new Set(connectionEdges.flatMap((edge) => [edge.fromId, edge.toId]));
  const connectionAgents = agents.filter((agent) => connectedAgentIds.has(agent.agent_id) && !agent.is_background);
  const selectedConnectionAgentId = activeConnectionAgentId && connectedAgentIds.has(activeConnectionAgentId)
    ? activeConnectionAgentId
    : connectionAgents[0]?.agent_id ?? null;
  const selectedConnectionEdges = selectedConnectionAgentId
    ? connectionEdges.filter((edge) => edge.fromId === selectedConnectionAgentId || edge.toId === selectedConnectionAgentId)
    : [];
  const timelineFacts: TimelineFact[] = [
    ...timelineEvents.map((event) => ({
      id: `event:${event.event_id}`,
      label: event.description,
      detail: `${event.time} · ${locations.find((location) => location.location_id === event.location_id)?.name ?? "Unknown location"}`,
      kind: "event" as const,
      time: event.time,
      eventId: event.event_id,
    })),
    ...allClaims.map(({ claim, suspect }) => ({
      id: `claim:${claim.claim_id}`,
      label: `${suspect.agent.full_name}: “${claim.claim_text}”`,
      detail: claim.time_reference ? `Statement time: ${claim.time_reference}` : "Statement with no specific time",
      kind: "statement" as const,
      time: null,
    })),
  ];
  const murderStart = minutes(caseOverview.murder_window[0]);
  const murderEnd = minutes(caseOverview.murder_window[1]);
  const expectedLane = (fact: TimelineFact): TimelineLane | null => {
    if (fact.kind !== "event" || !fact.time) return null;
    const time = minutes(fact.time);
    if (time < murderStart) return "before";
    if (time > murderEnd) return "after";
    return "during";
  };
  const placeTimelineFact = (factId: string, lane: TimelineLane) => {
    setTimelinePlacements((current) => ({ ...current, [factId]: lane }));
    setSelectedTimelineFactId(null);
    setTimelineNotice(null);
    sfx.paperSlide();
  };
  const clearTimelineFact = (factId: string) => {
    setTimelinePlacements((current) => {
      const next = { ...current };
      delete next[factId];
      return next;
    });
    setTimelineNotice(null);
  };
  const saveTimelineReconstruction = async () => {
    const placed = timelineFacts.filter((fact) => timelinePlacements[fact.id]);
    if (placed.length === 0) return;
    sfx.pencilScratch();
    await api.createNote({
      note_type: "question",
      title: "Timeline reconstruction",
      body: TIMELINE_LANES.map((lane) => {
        const facts = placed.filter((fact) => timelinePlacements[fact.id] === lane.id);
        return `${lane.label}: ${facts.length ? facts.map((fact) => fact.label).join(" | ") : "—"}`;
      }).join("\n"),
      linked_event_ids: placed.flatMap((fact) => fact.eventId ? [fact.eventId] : []),
      player_tags: ["timeline", "reconstruction"],
    });
    setTimelineNotice("Reconstruction saved to your notebook. Statements remain claims until you test them.");
    refresh();
  };
  const comparisonReady = Boolean(compareClaimId && compareClueId);
  const relevantSuspects = board.suspects.filter(
    (suspect) => suspect.claims.length > 0 || suspect.linked_clues.length > 0 || suspect.pinned_notes.length > 0
  );
  const backgroundSuspects = board.suspects.filter((suspect) => !relevantSuspects.includes(suspect));
  const recordComparison = async () => {
    const pair = allClaims.find(({ claim }) => claim.claim_id === compareClaimId);
    const clue = clues.find((item) => item.clue_id === compareClueId);
    if (!pair || !clue) return;
    sfx.pencilScratch();
    await api.createNote({
      note_type: "contradiction",
      title: `Possible conflict: ${pair.suspect.agent.full_name}`,
      body: `Statement: ${pair.claim.claim_text}\nEvidence: ${clue.title}\nQuestion: ${compareReason.trim() || "How can both be true?"}`,
      pinned_to_agent_id: pair.suspect.agent.agent_id,
      linked_agent_ids: [pair.suspect.agent.agent_id],
      linked_claim_ids: [pair.claim.claim_id],
      player_tags: ["comparison", "possible_conflict"],
    });
    setCompareReason("");
    setCompareClaimId("");
    setCompareClueId("");
    refresh();
    setBoardMode("summary");
  };

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

      <nav className="board-stage-nav" aria-label="Investigation board sections">
        {([
          ["summary", "Case summary"],
          ["evidence", `Evidence (${clues.length})`],
          ["timeline", "Reconstruct timeline"],
          ["connections", `Connections (${connectionEdges.length})`],
          ["contradictions", `Compare (${disputedClaims.length + comparisonNotes.length})`],
          ["theory", "Build theory"],
          ["notebook", `Notebook (${notes.length})`],
          ["recall", `Recall (${recallCards.length})`],
          ["workspace", "Full board"],
        ] as Array<[BoardMode, string]>).map(([mode, label]) => (
          <button
            key={mode}
            type="button"
            className={boardMode === mode ? "active" : ""}
            onClick={() => setBoardMode(mode)}
          >
            {label}
          </button>
        ))}
      </nav>

      {boardMode === "summary" && (
        <section className="board-guided-grid" aria-label="Case summary">
          <article className="board-next-action panel" aria-labelledby="next-action-heading">
            <span className="board-next-action-kicker">Investigation focus</span>
            <h2 id="next-action-heading">{nextLead.heading}</h2>
            {latestClue && nextLead.mode === "evidence" ? (
              <>
                <p>{nextLead.body}</p>
                {(linkedPeople.length > 0 || linkedPlaces.length > 0) && (
                  <p className="board-next-action-lead">
                    {linkedPeople.length > 0 && <>Follow up with {linkedPeople.map((person) => person.full_name).join(", ")}</>}
                    {linkedPeople.length > 0 && linkedPlaces.length > 0 && "; "}
                    {linkedPlaces.length > 0 && <>compare it against {linkedPlaces.join(", ")}</>}.
                  </p>
                )}
              </>
            ) : (
              <p>{nextLead.body}</p>
            )}
            <div className="board-summary-actions">
              <button type="button" onClick={() => setBoardMode(nextLead.mode)}>{nextLead.action}</button>
              {timelineFacts.length > 0 && <button type="button" onClick={() => setBoardMode("timeline")}>Reconstruct timeline</button>}
              {disputedClaims.length > 0 && <button type="button" onClick={() => setBoardMode("contradictions")}>Review conflicts</button>}
            </div>
          </article>
          <article className="board-proof-state panel">
            <span className="board-next-action-kicker">Case progress</span>
            <h2>What you have, and what is missing</h2>
            <ul>
              <li className={clues.length ? "complete" : ""}>Evidence catalogued: {clues.length}</li>
              <li className={board.suspects.some((suspect) => suspect.claims.length > 0) ? "complete" : ""}>Statements recorded: {board.suspects.reduce((count, suspect) => count + suspect.claims.length, 0)}</li>
              <li className={disputedClaims.length ? "complete" : ""}>Confirmed conflicts: {disputedClaims.length}</li>
              <li className={comparisonNotes.length ? "complete" : ""}>Comparisons to test: {comparisonNotes.length}</li>
              <li className={theoryNotesCount ? "complete" : ""}>Working theories: {theoryNotesCount}</li>
            </ul>
            {hints?.readiness_hints.slice(0, 2).map((hint, index) => <p className="readiness-hint" key={index}>🕵️ {hint}</p>)}
          </article>
        </section>
      )}

      {boardMode === "evidence" && (
        <section className="board-evidence-view" aria-label="Evidence grouped by source">
          <h2>Evidence, organised by source</h2>
          <p className="muted">Each card shows who and where it connects. Use those connections to decide what to test next.</p>
          {evidenceGroups.map((group) => group.clues.length > 0 && (
            <section className="board-evidence-group" key={group.key}><h3>{group.label}</h3>{group.clues.map((clue) => <ClueCard key={clue.clue_id} clue={clue} />)}</section>
          ))}
          {ungroupedClues.length > 0 && <section className="board-evidence-group"><h3>Other leads</h3>{ungroupedClues.map((clue) => <ClueCard key={clue.clue_id} clue={clue} />)}</section>}
          {clues.length === 0 && <p className="muted">No evidence yet. Start by searching the discovery scene.</p>}
        </section>
      )}

      {boardMode === "timeline" && (
        <section className="board-timeline-builder panel" aria-label="Timeline reconstruction">
          <span className="board-next-action-kicker">Timeline reconstruction</span>
          <h2>Put the known facts around the murder window</h2>
          <p className="muted">Drag a fact into a column, or select it then choose a column. Exact observed events can be checked against their recorded time; statements remain unverified until corroborated.</p>
          <div className="timeline-murder-window">Murder window · {caseOverview.murder_window[0]}–{caseOverview.murder_window[1]}</div>

          <div className="timeline-fact-tray" aria-label="Facts not yet placed">
            <h3>Known facts</h3>
            {timelineFacts.filter((fact) => !timelinePlacements[fact.id]).length === 0 ? (
              <p className="muted small">Every available fact is on your working timeline.</p>
            ) : timelineFacts.filter((fact) => !timelinePlacements[fact.id]).map((fact) => (
              <button
                type="button"
                draggable
                key={fact.id}
                className={`timeline-fact ${selectedTimelineFactId === fact.id ? "selected" : ""}`}
                onClick={() => setSelectedTimelineFactId((current) => current === fact.id ? null : fact.id)}
                onDragStart={(event) => event.dataTransfer.setData("text/plain", fact.id)}
              >
                <span className={`timeline-fact-kind ${fact.kind}`}>{fact.kind === "event" ? "Observed" : "Statement"}</span>
                <strong>{fact.label}</strong>
                <small>{fact.detail}</small>
              </button>
            ))}
          </div>

          <div className="timeline-lanes">
            {TIMELINE_LANES.map((lane) => {
              const facts = timelineFacts.filter((fact) => timelinePlacements[fact.id] === lane.id);
              return (
                <section
                  className="timeline-lane"
                  key={lane.id}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    const factId = event.dataTransfer.getData("text/plain");
                    if (timelineFacts.some((fact) => fact.id === factId)) placeTimelineFact(factId, lane.id);
                  }}
                >
                  <header><h3>{lane.label}</h3><p>{lane.description}</p></header>
                  {selectedTimelineFactId && !timelinePlacements[selectedTimelineFactId] && (
                    <button type="button" className="timeline-place-selected" onClick={() => placeTimelineFact(selectedTimelineFactId, lane.id)}>Place selected fact here</button>
                  )}
                  <div className="timeline-lane-facts">
                    {facts.map((fact) => {
                      const expected = expectedLane(fact);
                      const status = expected ? (expected === lane.id ? "verified" : "mismatch") : "unverified";
                      return (
                        <article className={`timeline-fact placed ${status}`} key={fact.id} draggable onDragStart={(event) => event.dataTransfer.setData("text/plain", fact.id)}>
                          <span className={`timeline-fact-kind ${fact.kind}`}>{fact.kind === "event" ? "Observed" : "Statement"}</span>
                          <strong>{fact.label}</strong>
                          <small>{fact.detail}</small>
                          {status === "verified" && <em>✓ Recorded time fits here</em>}
                          {status === "mismatch" && <em>↺ Recorded time puts this {expected} the window</em>}
                          {status === "unverified" && <em>◇ A statement, not a confirmed time</em>}
                          <button type="button" onClick={() => clearTimelineFact(fact.id)} aria-label={`Remove ${fact.label} from the timeline`}>×</button>
                        </article>
                      );
                    })}
                    {facts.length === 0 && <p className="muted small">Drop a known fact here.</p>}
                  </div>
                </section>
              );
            })}
          </div>
          <div className="timeline-builder-actions">
            <button type="button" className="primary" disabled={Object.keys(timelinePlacements).length === 0} onClick={saveTimelineReconstruction}>Save reconstruction</button>
            <button type="button" onClick={() => { setTimelinePlacements({}); setSelectedTimelineFactId(null); setTimelineNotice(null); }}>Clear working timeline</button>
            {timelineNotice && <p className="readiness-hint">🕵️ {timelineNotice}</p>}
          </div>
        </section>
      )}

      {boardMode === "connections" && (
        <section className="board-connections-view panel" aria-label="Discovered connections">
          <span className="board-next-action-kicker">Discovered connections</span>
          <h2>Only links you have actually uncovered</h2>
          <p className="muted">Statements about another person, shared evidence, and notes connecting two people appear here. It is a lead map—not proof of motive or guilt.</p>
          {connectionEdges.length === 0 ? (
            <p className="muted connection-empty">No direct person-to-person links have been discovered yet. Interview people about each other, or find evidence that connects more than one person.</p>
          ) : (
            <div className="connection-web">
              <div className="connection-people" aria-label="People with discovered connections">
                {connectionAgents.map((agent) => (
                  <button
                    key={agent.agent_id}
                    type="button"
                    className={selectedConnectionAgentId === agent.agent_id ? "active" : ""}
                    onClick={() => setActiveConnectionAgentId(agent.agent_id)}
                  >
                    <Portrait agent={agent} />
                    <span>{agent.full_name}</span>
                  </button>
                ))}
              </div>
              {selectedConnectionAgentId && (
                <div className="connection-links" aria-live="polite">
                  <h3>{agents.find((agent) => agent.agent_id === selectedConnectionAgentId)?.full_name}'s known links</h3>
                  {selectedConnectionEdges.map((edge) => {
                    const otherId = edge.fromId === selectedConnectionAgentId ? edge.toId : edge.fromId;
                    const other = agents.find((agent) => agent.agent_id === otherId);
                    return (
                      <article key={edge.id} className={`connection-link ${edge.source}`}>
                        <span className="connection-link-line" aria-hidden="true" />
                        <div><span className="connection-link-source">{edge.source}</span><strong>{other?.full_name ?? "Unknown person"}</strong><p>{edge.label}</p></div>
                      </article>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {boardMode === "contradictions" && (
        <section className="board-conflicts-view" aria-label="Claims in conflict">
          <h2>Claims that need testing</h2>
          <p className="muted">A conflict is not a conviction. Take the evidence back to the speaker and see how they answer.</p>
          {disputedClaims.length === 0 ? <p className="muted">No confirmed conflicts yet. Compare statements with timeline events and evidence.</p> : disputedClaims.map(({ claim, suspect }) => (
            <article className="board-conflict-card panel" key={claim.claim_id}><strong>{suspect.agent.full_name}</strong><p>“{claim.claim_text}”</p><span className="badge disputed">disputed</span><button type="button" onClick={() => setBoardMode("workspace")}>Open confrontation workspace</button></article>
          ))}
          {comparisonNotes.length > 0 && (
            <section className="board-player-comparisons" aria-label="Your comparisons to test">
              <h3>Your comparisons to test</h3>
              <p className="muted small">These are your working deductions. Test them in an interview; they are not confirmed contradictions yet.</p>
              {comparisonNotes.map((note) => <article className="board-conflict-card panel" key={note.note_id}><strong>{note.title}</strong><p>{note.body}</p><span className="badge ambiguous">needs testing</span></article>)}
            </section>
          )}
          {allClaims.length > 0 && clues.length > 0 && (
            <section className="board-comparison-builder panel" aria-label="Compare a statement with evidence">
              <span className="board-next-action-kicker">Compare two facts</span>
              <h3>What does not add up?</h3>
              <label>Statement<select value={compareClaimId} onChange={(event) => setCompareClaimId(event.target.value)}><option value="">Choose a statement</option>{allClaims.map(({ claim, suspect }) => <option value={claim.claim_id} key={claim.claim_id}>{suspect.agent.full_name}: {claim.claim_text}</option>)}</select></label>
              <label>Evidence<select value={compareClueId} onChange={(event) => setCompareClueId(event.target.value)}><option value="">Choose evidence</option>{clues.map((clue) => <option value={clue.clue_id} key={clue.clue_id}>{clue.title}</option>)}</select></label>
              <label>Why might they conflict?<textarea value={compareReason} onChange={(event) => setCompareReason(event.target.value)} placeholder="What cannot both be true?" /></label>
              <button type="button" className="primary" disabled={!comparisonReady} onClick={recordComparison}>Record possible conflict</button>
            </section>
          )}
        </section>
      )}

      {boardMode === "theory" && (
        <section className="board-theory-builder panel" aria-label="Build a working theory">
          <span className="board-next-action-kicker">Working theory</span>
          <h2>Make a claim you can test</h2>
          <p>A theory is provisional. Tie one person to one piece of evidence, then record what you still need to prove.</p>
          <label>Person<select value={theorySuspectId} onChange={(event) => setTheorySuspectId(event.target.value)}><option value="">Choose a person</option>{board.suspects.map((suspect) => <option value={suspect.agent.agent_id} key={suspect.agent.agent_id}>{suspect.agent.full_name}</option>)}</select></label>
          <label>Evidence<select value={theoryClueId} onChange={(event) => setTheoryClueId(event.target.value)}><option value="">Choose evidence</option>{clues.map((clue) => <option value={clue.clue_id} key={clue.clue_id}>{clue.title}</option>)}</select></label>
          <label>What might it explain?<textarea value={theoryReason} onChange={(event) => setTheoryReason(event.target.value)} placeholder="This could explain motive, opportunity, a lie, or another open question…" /></label>
          <button type="button" className="primary" disabled={!theoryReady} onClick={saveStructuredTheory}>Save working theory</button>
          {clues.length < 2 && <p className="muted small">Find at least one more lead before treating a theory as anything more than a hunch.</p>}
        </section>
      )}

      {boardMode === "notebook" && (
        <section className="board-notebook-launch panel" aria-label="Notebook">
          <span className="board-next-action-kicker">Notebook</span>
          <h2>What does not add up?</h2>
          <p>{notes.length ? `${notes.length} deduction card${notes.length === 1 ? "" : "s"} recorded. Capture a thought, compare two facts, or build a theory.` : "Capture a thought only when it gives you something to test."}</p>
          <div className="board-summary-actions">
            <button type="button" onClick={() => setNoteComposerOpen(true)}>Record a thought</button>
            <button type="button" onClick={() => setBoardMode("contradictions")}>Compare two facts</button>
            <button type="button" onClick={() => setBoardMode("theory")}>Build a theory</button>
          </div>
          {noteComposerOpen && <div className="deduction-thought-form"><input placeholder="Short thought" value={title} onChange={(event) => setTitle(event.target.value)} /><textarea placeholder="What does not add up, and what would test it?" value={body} onChange={(event) => setBody(event.target.value)} /><button type="button" className="primary" disabled={!title.trim()} onClick={saveQuickThought}>Save thought</button></div>}
          <button type="button" className="small-button" onClick={() => setBoardMode("workspace")}>Open full archive</button>
        </section>
      )}

      {boardMode === "recall" && (
        <section className="board-recall-deck panel" aria-label="Recall deck">
          <span className="board-next-action-kicker">Recall deck</span>
          <h2>Refresh what you already know</h2>
          <p className="muted">A quick return-to-case refresher. Click a card to turn it over; no new information is revealed.</p>
          {recallCards.length === 0 ? (
            <p className="muted">There is nothing to recall yet. Find a clue or record a statement first.</p>
          ) : (
            <div className="recall-card-grid">
              {recallCards.map((card) => {
                const revealed = revealedRecallIds.has(card.id);
                return (
                  <button
                    type="button"
                    key={card.id}
                    className={`recall-card ${revealed ? "revealed" : ""}`}
                    aria-pressed={revealed}
                    onClick={() => setRevealedRecallIds((current) => {
                      const next = new Set(current);
                      if (next.has(card.id)) next.delete(card.id); else next.add(card.id);
                      return next;
                    })}
                  >
                    <span>{revealed ? card.source : "Tap to recall"}</span>
                    <strong>{revealed ? card.answer : card.prompt}</strong>
                    <small>{revealed ? "Tap to hide the answer" : "Answer is already in your case file"}</small>
                  </button>
                );
              })}
            </div>
          )}
        </section>
      )}

      {boardMode === "workspace" && (

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

          {relevantSuspects.map((s) => {
            const leadCount = s.claims.length + s.linked_clues.length + s.pinned_notes.length;
            const maySetAside = leadCount >= 1;
            const mayNamePrime = leadCount >= 3 || s.claims.some((claim) => claim.player_known_status === "disputed");
            return (
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

              <details className="marker-toggles">
                <summary>Mark this lead</summary>
                <p className="muted small">Labels are your working judgement, not proof.</p>
                {maySetAside ? <label><input type="checkbox" checked={(board.case_board_markers?.[s.agent.agent_id] || []).includes("red_herring")} onChange={() => toggleMarker(s.agent.agent_id, "red_herring")} /> Set aside for now</label> : <p className="muted small">Find a linked clue or statement before categorising this person.</p>}
                {leadCount >= 2 && <label><input type="checkbox" checked={(board.case_board_markers?.[s.agent.agent_id] || []).includes("cleared")} onChange={() => toggleMarker(s.agent.agent_id, "cleared")} /> Tentatively cleared</label>}
                {mayNamePrime && <label><input type="checkbox" checked={(board.case_board_markers?.[s.agent.agent_id] || []).includes("prime_suspect")} onChange={() => toggleMarker(s.agent.agent_id, "prime_suspect")} /> Primary lead</label>}
              </details>

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
            );
          })}
          {backgroundSuspects.length > 0 && (
            <details className="board-other-residents">
              <summary>Other residents ({backgroundSuspects.length})</summary>
              <p className="muted small">No evidence, statements, or notes currently connect these people to your investigation.</p>
              <p>{backgroundSuspects.map((suspect) => suspect.agent.full_name).join(" · ")}</p>
            </details>
          )}
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
          <h2>Deduction archive</h2>
          <p className="muted small">Use the guided Compare and Theory views first. Manual notes are for ideas that do not fit either path.</p>

          {/* Notetaking Form */}
          <details className="manual-note-composer panel">
            <summary>Record a manual thought</summary>
            <div className="note-form">
            <div className="note-form-header">
              <span className="note-form-title">MANUAL THOUGHT</span>
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
              ✒️ Save thought
            </button>
            </div>
          </details>

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
      )}
    </div>
  );
}
