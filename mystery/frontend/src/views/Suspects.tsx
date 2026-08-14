import { useCallback, useEffect, useRef, useState } from "react";
import { api, hhmm, minutes } from "../api";
import { useWorld } from "../App";
import type {
  AgentPublic,
  AskResult,
  BoardSuspect,
  ChallengeResult,
  ChallengeSuggestion,
  ClaimPublic,
  CluePublic,
  InspectResult,
  ObservableTell,
  ObservationRead,
  QuestionType,
  SuspicionLevel,
  TranscriptMessage,
} from "../types";
import { MagnifyingSearch } from "../components/MagnifyingSearch";
import { ClueCard } from "./shared";
import Portrait, {
  DEFENSIVE_THRESHOLD,
  CRACKING_THRESHOLD,
} from "../components/Portrait";
import ContradictionBeat from "../components/ContradictionBeat";
import NotebookNotification from "../components/NotebookNotification";
import { audioManager } from "../audio";
import { cinematicsEnabled } from "../settings";
import { sfx } from "../sfx";
import RewindIntro, { witnessReplayForTestimony } from "./RewindIntro";
import { lifelikeCalmPortrait, lifelikeDeceasedPortrait } from "../characterArt";

interface BeatData {
  claimText: string;
  evidenceText: string;
  outcomeText: string;
  outcomeLabel: string;
}

// Existing engine outcomes that represent a caught contradiction (both also
// create a contradiction note backend-side); purely a frontend selection.
const beatOutcome = (o: ChallengeResult["outcome"]) =>
  o === "contradiction_locked" || o === "partial_admission";

function tellClass(tell?: ObservableTell) {
  return tell ? `mugshot-tell mugshot-tell-${tell.category} mugshot-tell-${tell.intensity}` : "";
}

const SUSPICION_LEVELS: { value: SuspicionLevel; label: string }[] = [
  { value: "unknown", label: "Unmarked" },
  { value: "person_of_interest", label: "Person of interest" },
  { value: "suspect", label: "Suspect" },
  { value: "prime_suspect", label: "Prime suspect" },
  { value: "likely_innocent", label: "Likely innocent" },
  { value: "cleared", label: "Cleared" },
];

function BehaviouralRead({
  tells,
  onPin,
}: {
  tells?: ObservableTell[];
  /** When set, noticeable/strong reads grow a pin — the useful ones deserve a
   *  place in the notebook, not just a moment in the transcript. */
  onPin?: (tell: ObservableTell) => void;
}) {
  if (!tells || tells.length === 0) return null;
  return (
    <div className="behavioural-read">
      <span className="behavioural-title">Behavioural read</span>
      {tells.map((tell) => (
        <p key={tell.tell_id} className={`tell tell-${tell.intensity} tell-${tell.category}`}>
          <span className="tell-tags">
            <span>{tell.category}</span>
            <span>{tell.intensity}</span>
          </span>
          {tell.cue}
          {onPin && tell.intensity !== "subtle" && (
            <button
              type="button"
              className="tell-pin"
              title="Pin this read to the notebook"
              onClick={() => onPin(tell)}
            >
              📌
            </button>
          )}
        </p>
      ))}
    </div>
  );
}

/** Diegetic labels for how a considered read sits against the remembered calm
 *  baseline — "changed from earlier", never "lying". */
const BASELINE_LABEL: Record<string, string> = {
  noted: "manner noted",
  consistent: "same as earlier",
  shifted: "changed from earlier",
  broken: "nothing like earlier",
};

const SUSPICION_LABEL = Object.fromEntries(
  SUSPICION_LEVELS.map((s) => [s.value, s.label])
) as Record<SuspicionLevel, string>;

function caseLabel(caseId: string) {
  return caseId.startsWith("case_") ? `Case ${caseId.split("_")[1]}` : caseId;
}

/** Demeanour derived from the interview so far — cosmetic, never feeds game logic. */
function interviewState(
  transcriptLen: number,
  suspicion: SuspicionLevel,
  pressure: number,
  contradicted: boolean
): { label: string; tone: string } {
  if (suspicion === "cleared") return { label: "Cleared", tone: "cleared" };
  if (transcriptLen === 0) return { label: "Unquestioned", tone: "unquestioned" };
  if (contradicted) return { label: "Contradicted", tone: "contradicted" };
  if (pressure >= DEFENSIVE_THRESHOLD) return { label: "Evasive", tone: "evasive" };
  return { label: "Cooperative", tone: "cooperative" };
}

export default function Suspects({ focusAgentId }: { focusAgentId?: string | null }) {
  const { agents, locations } = useWorld();
  const [boardState, setBoardState] = useState<Record<string, BoardSuspect>>({});
  const [flashcardId, setFlashcardId] = useState<string | null>(null);
  // The victim's examination is useful, but it is not the action implied by
  // opening “Suspects”. Start on someone the player can actually question.
  const firstQuestionableAgent = agents.find((a) => !a.is_victim && !a.is_background);
  const [selectedId, setSelectedId] = useState(
    (focusAgentId && agents.some((a) => a.agent_id === focusAgentId)
      ? focusAgentId
      : firstQuestionableAgent?.agent_id ?? agents.find((a) => !a.is_background)?.agent_id) ?? ""
  );
  useEffect(() => {
    if (focusAgentId && agents.some((a) => a.agent_id === focusAgentId)) {
      setSelectedId(focusAgentId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusAgentId]);
  useEffect(() => {
    // World data can change when a player opens a different case. Preserve an
    // explicit selection, including the optional post-mortem, but never leave
    // the screen blank or default it back to the victim.
    if (!agents.some((a) => a.agent_id === selectedId)) {
      setSelectedId(firstQuestionableAgent?.agent_id ?? agents.find((a) => !a.is_background)?.agent_id ?? "");
    }
  }, [agents, firstQuestionableAgent, selectedId]);
  const selected = agents.find((a) => a.agent_id === selectedId);
  const flashcardAgent = agents.find((a) => a.agent_id === flashcardId);
  const livingAgents = agents.filter((a) => !a.is_victim && !a.is_background);
  const victim = agents.find((a) => a.is_victim && !a.is_background);

  const onBoardState = useCallback((suspects: BoardSuspect[]) => {
    setBoardState(
      Object.fromEntries(
        suspects.map((s) => [
          s.agent.agent_id,
          s,
        ])
      )
    );
  }, []);

  return (
    <div className="suspects">
      <aside className="suspect-list panel">
        <p className="roster-title">People to question</p>
        <p className="roster-guidance">Choose a resident, then start with their alibi during the murder window.</p>
        {livingAgents.map((a) => {
          const info = boardState[a.agent_id];
          return (
            <div
              key={a.agent_id}
              className={`suspect ${selectedId === a.agent_id ? "active" : ""}`}
            >
              <button
                type="button"
                className="suspect-portrait-button"
                onClick={() => {
                  sfx.evidenceInspect();
                  setFlashcardId(a.agent_id);
                }}
                aria-label={`Open dossier for ${a.full_name}`}
                title={`Open ${a.full_name}'s dossier`}
              >
                <Portrait agent={a} pressure={info?.pressure ?? 0} />
              </button>
              <button
                type="button"
                className="suspect-select-button"
                onClick={() => {
                  if (a.agent_id !== selectedId) sfx.paperSlide();
                  setSelectedId(a.agent_id);
                }}
              >
                <span className="suspect-name">{a.full_name}</span>
                <span className="muted small">{a.occupation}</span>
                {info &&
                  info.suspicion !== "unknown" && (
                    <span className={`list-suspicion suspicion-${info.suspicion}`}>
                      {SUSPICION_LABEL[info.suspicion]}
                    </span>
                  )}
              </button>
            </div>
          );
        })}
        {victim && (
          <>
            <p className="roster-section-title">Optional case examination</p>
            <div
              className={`suspect victim ${selectedId === victim.agent_id ? "active" : ""}`}
            >
              <button
                type="button"
                className="suspect-portrait-button"
                onClick={() => {
                  sfx.evidenceInspect();
                  setFlashcardId(victim.agent_id);
                }}
                aria-label={`Open dossier for ${victim.full_name}`}
                title={`Open ${victim.full_name}'s dossier`}
              >
                <Portrait agent={victim} pressure={boardState[victim.agent_id]?.pressure ?? 0} />
              </button>
              <button
                type="button"
                className="suspect-select-button"
                onClick={() => {
                  if (victim.agent_id !== selectedId) sfx.paperSlide();
                  setSelectedId(victim.agent_id);
                }}
              >
                <span className="suspect-name">{victim.full_name}</span>
                <span className="muted small">{victim.occupation}</span>
                <span className="list-victim">✝ Victim · post-mortem examination</span>
              </button>
            </div>
          </>
        )}
      </aside>
      {selected && (
        selected.is_victim ? (
          <AutopsyPanel
            key={selected.agent_id}
            agentId={selected.agent_id}
            onBoardState={onBoardState}
          />
        ) : (
          <InterviewPanel
            key={selected.agent_id}
            agentId={selected.agent_id}
            pressure={boardState[selected.agent_id]?.pressure ?? 0}
            onBoardState={onBoardState}
            onOpenDossier={() => {
              sfx.evidenceInspect();
              setFlashcardId(selected.agent_id);
            }}
          />
        )
      )}
      {flashcardAgent && (
        <SuspectFlashcard
          agent={flashcardAgent}
          boardState={boardState[flashcardAgent.agent_id]}
          locations={locations}
          onClose={() => setFlashcardId(null)}
          onInterview={() => {
            if (flashcardAgent.agent_id !== selectedId) sfx.paperSlide();
            setSelectedId(flashcardAgent.agent_id);
            setFlashcardId(null);
          }}
        />
      )}
    </div>
  );
}

function SuspectFlashcard({
  agent,
  boardState,
  locations,
  onClose,
  onInterview,
}: {
  agent: AgentPublic;
  boardState?: BoardSuspect;
  locations: { location_id: string; name: string }[];
  onClose: () => void;
  onInterview: () => void;
}) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const firstName = agent.full_name.split(" ")[0];
  const locationName = (locationId: string | null) =>
    locations.find((location) => location.location_id === locationId)?.name ?? null;
  const knownPlaces = [
    agent.home_location_id ? `Lives: ${locationName(agent.home_location_id)}` : null,
    agent.work_location_id ? `Works: ${locationName(agent.work_location_id)}` : null,
  ].filter(Boolean);
  const claims = boardState?.claims ?? [];
  const clues = boardState?.linked_clues ?? [];
  const notes = boardState?.pinned_notes ?? [];
  const suspicion = boardState?.suspicion ?? "unknown";

  return (
    <div className="modal-overlay suspect-flashcard-overlay" onClick={onClose}>
      <section
        className="suspect-flashcard"
        role="dialog"
        aria-modal="true"
        aria-labelledby="suspect-flashcard-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="suspect-flashcard-head">
          <span className="suspect-flashcard-kicker">Detective's file · known so far</span>
          <button type="button" className="suspect-flashcard-close" onClick={onClose} autoFocus>
            Close
          </button>
        </header>

        <div className="suspect-flashcard-identity">
          <div className="suspect-flashcard-portrait">
            <Portrait agent={agent} pressure={boardState?.pressure ?? 0} size="large" />
          </div>
          <div>
            <div className="dossier-name-row">
              <h2 id="suspect-flashcard-title">{agent.full_name}</h2>
              {suspicion !== "unknown" && (
                <span className={`badge suspicion-${suspicion}`}>{SUSPICION_LABEL[suspicion]}</span>
              )}
            </div>
            <p className="suspect-flashcard-meta">{agent.occupation} · {agent.age}</p>
            <div className="trait-chips">
              {agent.traits.map((trait) => <span key={trait} className="trait-chip">{trait}</span>)}
            </div>
            {knownPlaces.length > 0 && <p className="suspect-flashcard-places">{knownPlaces.join(" · ")}</p>}
          </div>
        </div>

        <div className="suspect-flashcard-summary" aria-label="Known-facts summary">
          <span><strong>{claims.length}</strong> statement{claims.length === 1 ? "" : "s"}</span>
          <span><strong>{clues.length}</strong> evidence link{clues.length === 1 ? "" : "s"}</span>
          <span><strong>{notes.length}</strong> saved note{notes.length === 1 ? "" : "s"}</span>
        </div>

        <div className="suspect-flashcard-facts">
          <section>
            <h3>Statements on record</h3>
            {claims.length > 0 ? (
              <ul className="suspect-fact-list">
                {claims.map((claim) => (
                  <li key={claim.claim_id}>
                    <span className={`badge status-${claim.player_known_status}`}>{claim.player_known_status}</span>
                    <span>{claim.claim_text}</span>
                    {(claim.time_reference || claim.location_reference_id) && (
                      <small>{[claim.time_reference, locationName(claim.location_reference_id)].filter(Boolean).join(" · ")}</small>
                    )}
                  </li>
                ))}
              </ul>
            ) : <p className="muted">No statement from {firstName} is on record yet.</p>}
          </section>
          <section>
            <h3>Connected evidence</h3>
            {clues.length > 0 ? (
              <ul className="suspect-fact-list evidence-list">
                {clues.map((clue) => (
                  <li key={clue.clue_id}>
                    <span><strong>{clue.title}</strong> <small>{clue.description}</small></span>
                    <span className={`badge strength-${clue.strength}`}>{clue.strength}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">No discovered evidence connects to {firstName} yet.</p>}
          </section>
          <section>
            <h3>Your notes</h3>
            {notes.length > 0 ? (
              <ul className="suspect-fact-list note-list">
                {notes.map((note) => <li key={note.note_id}><strong>{note.title}</strong><small>{note.body}</small></li>)}
              </ul>
            ) : <p className="muted">Nothing has been saved to {firstName}'s file yet.</p>}
          </section>
        </div>

        <footer className="suspect-flashcard-actions">
          <p>Only facts you have discovered are shown here.</p>
          <button type="button" className="btn-primary" onClick={onInterview}>
            {agent.is_victim ? "Open examination" : `Interview ${firstName}`}
          </button>
        </footer>
      </section>
    </div>
  );
}

function RadialComposureAvatar({
  agent,
  pressure,
  stateLabel,
  activeTellClass,
  onOpenDossier,
}: {
  agent: AgentPublic;
  pressure: number;
  stateLabel: string;
  activeTellClass?: string;
  onOpenDossier: () => void;
}) {
  const composurePct = Math.max(0, Math.min(100, Math.round((1 - pressure) * 100)));
  const radius = 42;
  const strokeWidth = 5;
  const circ = 2 * Math.PI * radius;
  const strokeDashoffset = circ - (composurePct / 100) * circ;

  return (
    <button
      type="button"
      className={`radial-avatar-wrap radial-avatar-button ${activeTellClass || ""}`}
      onClick={onOpenDossier}
      aria-label={`Open dossier for ${agent.full_name}`}
      title={`Open ${agent.full_name}'s dossier`}
    >
      <div className="radial-avatar-frame">
        <svg className="radial-avatar-svg" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r={radius}
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth={strokeWidth}
            fill="none"
          />
          <circle
            cx="50"
            cy="50"
            r={radius}
            stroke={composurePct > 50 ? "#d8a24a" : composurePct > 25 ? "#e67e22" : "#e74c3c"}
            strokeWidth={strokeWidth}
            fill="none"
            strokeDasharray={circ}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            transform="rotate(-90 50 50)"
            style={{ transition: "stroke-dashoffset 0.5s ease, stroke 0.5s ease" }}
          />
        </svg>
        <div className="radial-avatar-img">
          <Portrait agent={agent} pressure={pressure} size="large" />
        </div>
      </div>
      <div className="radial-avatar-badge">
        <span className="composure-pct">{composurePct}%</span>
        <span className="composure-state-tag">{stateLabel.toUpperCase()}</span>
      </div>
    </button>
  );
}

function InterviewPanel({
  agentId,
  pressure,
  onBoardState,
  onOpenDossier,
}: {
  agentId: string;
  pressure: number;
  onBoardState: (suspects: BoardSuspect[]) => void;
  onOpenDossier: () => void;
}) {
  const { agents, locations, caseOverview } = useWorld();
  const agent = agents.find((a) => a.agent_id === agentId)!;
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [lastResult, setLastResult] = useState<AskResult | null>(null);
  const [clues, setClues] = useState<CluePublic[]>([]);
  const [claims, setClaims] = useState<ClaimPublic[]>([]);
  const [suspicion, setSuspicion] = useState<SuspicionLevel>("unknown");
  const [contradictionCount, setContradictionCount] = useState(0);
  const [hintsTaken, setHintsTaken] = useState(0);
  const [suggestions, setSuggestions] = useState<ChallengeSuggestion[]>([]);
  const [confrontClaim, setConfrontClaim] = useState("");
  const [confrontEvidence, setConfrontEvidence] = useState<string[]>([]);
  const [confrontTestimony, setConfrontTestimony] = useState<string[]>([]);
  const [allClaims, setAllClaims] = useState<ClaimPublic[]>([]);
  const [lastChallenge, setLastChallenge] = useState<ChallengeResult | null>(null);
  const [observation, setObservation] = useState<ObservationRead | null>(null);
  const [observeMsg, setObserveMsg] = useState<string | null>(null);
  const [observedExchangeToken, setObservedExchangeToken] = useState<string | null>(null);
  const [observeNudgeSeen, setObserveNudgeSeen] = useState(() =>
    localStorage.getItem(`observe-nudge-seen:${caseOverview.case_id}`) === "1"
  );
  const latestTell = lastChallenge?.observable_tells?.[0] ?? lastResult?.observable_tells?.[0];
  const [activeTellClass, setActiveTellClass] = useState("");
  const [beat, setBeat] = useState<BeatData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [notebookNote, setNotebookNote] = useState<string | null>(null);
  const [witnessReplayEventId, setWitnessReplayEventId] = useState<string | null>(null);

  const murderWindowMidpoint = () =>
    hhmm(Math.round((minutes(caseOverview.murder_window[0]) + minutes(caseOverview.murder_window[1])) / 2));
  const [timeRef, setTimeRef] = useState(murderWindowMidpoint);
  const [clueTopic, setClueTopic] = useState("");
  const [locationTopic, setLocationTopic] = useState("");
  const [freeText, setFreeText] = useState("");
  const [fallbackMsg, setFallbackMsg] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [clearLogic, setClearLogic] = useState(true);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const [stallLine, setStallLine] = useState<string | null>(null);
  const stallTimer = useRef<number | null>(null);
  const lastStall = useRef<string | null>(null);

  /* A suspect covering the pause while their answer is generated.
   *
   * Held back by STALL_DELAY_MS rather than shown immediately: prefetch means a
   * predicted question usually returns in ~10ms, and a filler that appeared and
   * vanished inside a frame would read as a glitch rather than a breath. So the
   * stall only appears once the wait is long enough to actually need covering.
   *
   * These lines are affect-neutral by construction (see Agent.stall_fillers) —
   * hesitation is real evidence in this game, and a stall that sounded evasive
   * would be a tell invented by a slow GPU. */
  const STALL_DELAY_MS = 400;

  const beginStall = () => {
    const pool = agent.stall_fillers ?? [];
    if (pool.length === 0) return;
    // Avoid repeating the previous line back-to-back: the same tic twice reads
    // as a loop, which is the one thing that breaks the illusion outright.
    const choices = pool.length > 1 ? pool.filter((l) => l !== lastStall.current) : pool;
    const line = choices[Math.floor(Math.random() * choices.length)];
    stallTimer.current = window.setTimeout(() => {
      lastStall.current = line;
      setStallLine(line);
    }, STALL_DELAY_MS);
  };

  const endStall = () => {
    if (stallTimer.current !== null) {
      window.clearTimeout(stallTimer.current);
      stallTimer.current = null;
    }
    setStallLine(null);
  };

  useEffect(() => endStall, []);

  const firstName = agent.full_name.split(" ")[0];
  const victimName = caseOverview.victim.full_name.split(" ")[0];
  const isVictim = agent.is_victim;
  const placeholder = isVictim 
    ? `Examine body (e.g. search pockets, check wounds, cause of death…)`
    : `Ask ${firstName} about Clara, the timeline, a place, or discovered evidence…`;

  const otherTestimony = allClaims.filter((c) => c.speaker_agent_id !== agentId);

  // Keep the shorthand question anchored to the active case when the player
  // changes cases, while still letting them type a more specific time.
  useEffect(() => {
    setTimeRef(murderWindowMidpoint());
  }, [caseOverview.case_id]);

  const caughtInContradiction = claims.some((c) => c.player_known_status === "disputed");
  const state = interviewState(transcript.length, suspicion, pressure, caughtInContradiction);
  const latestAgentExchange = [...transcript].reverse().find((m) => m.speaker === "agent");
  const freshExchangeToken = [
    transcript.length,
    latestAgentExchange?.text ?? "",
    lastChallenge?.challenge_id ?? "",
  ].join(":");
  const hasFreshAnswer = Boolean(latestAgentExchange);
  const calmFreshObserveAvailable =
    !isVictim &&
    pressure < DEFENSIVE_THRESHOLD &&
    hasFreshAnswer &&
    observedExchangeToken !== freshExchangeToken;
  const showObserveNudge = calmFreshObserveAvailable && !observeNudgeSeen && !observeMsg;

  const refresh = useCallback(async () => {
    try {
      const [t, , , r, b] = await Promise.all([
        api.transcript(agentId),
        api.clues().then(setClues).catch(console.error),
        api.claims().then(setAllClaims).catch(console.error),
        api.challengeSuggestions(agentId).catch(() => ({
          contradiction_count: 0,
          hints_taken: 0,
          suggestions: [],
        })),
        api.board().catch(() => null),
      ]);
      setTranscript(t);
      if (r) {
        setContradictionCount(r.contradiction_count);
        setHintsTaken(r.hints_taken);
      }
      if (b) {
        const me = b.suspects.find((s) => s.agent.agent_id === agentId);
        if (me) {
          setSuspicion(me.suspicion);
          setClaims(me.claims);
        }
        onBoardState(b.suspects);
      }
    } catch (e) {
      console.error("Failed to refresh transcript:", e);
    }
  }, [agentId, onBoardState]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [transcript, lastResult, lastChallenge, busy]);

  useEffect(() => {
    const nextClass = tellClass(latestTell);
    setActiveTellClass(nextClass);
    if (!nextClass) return;
    const t = setTimeout(() => setActiveTellClass(""), 1150);
    return () => clearTimeout(t);
  }, [latestTell?.tell_id]);

  useEffect(() => {
    if (lastChallenge && lastChallenge.outcome === "contradiction_locked") {
      audioManager.playStinger("contradiction_locked");
    }
  }, [lastChallenge]);

  const prevPressureRef = useRef(pressure);
  useEffect(() => {
    const prev = prevPressureRef.current;
    if (prev < DEFENSIVE_THRESHOLD && pressure >= DEFENSIVE_THRESHOLD) {
      audioManager.playStinger("pressure_defensive");
    } else if (prev < CRACKING_THRESHOLD && pressure >= CRACKING_THRESHOLD) {
      audioManager.playStinger("pressure_cracking");
    }
    prevPressureRef.current = pressure;
  }, [pressure]);

  const ask = async (
    questionType: QuestionType,
    extra: Record<string, string> = {},
    questionText?: string
  ) => {
    sfx.questionSend();
    setBusy(true);
    setError(null);
    setPendingQuestion(questionText ?? null);
    setObserveMsg(null);
    beginStall();
    try {
      const result = await api.ask({
        agent_id: agentId,
        question_type: questionType,
        ...extra,
      });
      setLastResult(result);
      setLastChallenge(null);
      setFallbackMsg(null);
      await refresh();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      endStall();
      setPendingQuestion(null);
      setBusy(false);
    }
  };

  const submitFreeText = async () => {
    if (!freeText.trim()) return;
    const questionText = freeText.trim();
    sfx.questionSend();
    setBusy(true);
    setError(null);
    setFallbackMsg(null);
    setPendingQuestion(questionText);
    setObserveMsg(null);
    beginStall();
    try {
      const result = await api.freeTextAsk({
        agent_id: agentId,
        question: questionText,
      });
      if (result.answer) {
        setLastResult(result.answer);
        setLastChallenge(null);
      } else if (result.challenge_result) {
        const cr = result.challenge_result as ChallengeResult;
        setLastChallenge(cr);
        setLastResult(null);
        if (beatOutcome(cr.outcome) && cinematicsEnabled()) {
          const claims = await api.claims(agentId).catch(() => [] as ClaimPublic[]);
          const claimText =
            claims.find((c) => c.claim_id === cr.challenged_claim_id)?.claim_text ??
            "Their story";
          const evidenceText =
            clues
              .filter((c) => cr.evidence_clue_ids.includes(c.clue_id))
              .map((c) => c.title)
              .join(", ") || "the evidence you hold";
          setBeat({
            claimText,
            evidenceText,
            outcomeText: cr.response_text,
            outcomeLabel: cr.outcome.replace(/_/g, " "),
          });
        }
      } else if (result.challenge_suggestion) {
        setLastResult(null);
        setLastChallenge(null);
      } else if (result.fallback_message) {
        setFallbackMsg(result.fallback_message);
      }
      setFreeText("");
      await refresh();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      endStall();
      setPendingQuestion(null);
      setBusy(false);
    }
  };

  const observeThem = async () => {
    sfx.evidenceInspect();
    setBusy(true);
    setObserveMsg(null);
    localStorage.setItem(`observe-nudge-seen:${caseOverview.case_id}`, "1");
    setObserveNudgeSeen(true);
    try {
      const obs = await api.observe(agentId);
      setObservation(obs);
      setObservedExchangeToken(freshExchangeToken);
    } catch (e) {
      setObserveMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const pinObservation = async () => {
    if (!observation) return;
    sfx.pencilScratch();
    await api.createNote({
      note_type: "interview",
      title: `Read on ${firstName}`,
      body: observation.text,
      linked_agent_ids: [agentId],
      pinned_to_agent_id: agentId,
      player_tags: ["behaviour", "observe", observation.baseline_state ?? "manner"],
    });
    setNotebookNote(`Read on ${firstName}: ${observation.text.slice(0, 90)}…`);
  };

  const pinTell = async (tell: ObservableTell, context?: string) => {
    sfx.pencilScratch();
    await api.createNote({
      note_type: "interview",
      title: `${firstName}: ${tell.category} tell (${tell.intensity})`,
      body: context ? `${tell.cue}\n— watching ${firstName} ${context}` : tell.cue,
      linked_agent_ids: [agentId],
      pinned_to_agent_id: agentId,
      player_tags: ["behaviour", "tell", tell.category, tell.intensity],
    });
    setNotebookNote(`Pinned a read on ${firstName}`);
  };

  const noteFromAnswer = async () => {
    if (!lastResult) return;
    const primaryClaim = lastResult.new_claims[0];
    sfx.pencilScratch();
    await api.createNote({
      note_type: "interview",
      // Preserve the thing a detective needs to test, not an arbitrary first
      // fragment of dialogue. The full answer remains available in the
      // transcript; the board receives a compact statement card.
      title: `${firstName}'s statement${primaryClaim ? `: ${primaryClaim.claim_text.slice(0, 56)}…` : ""}`,
      body: `${primaryClaim ? `Claim: ${primaryClaim.claim_text}\n` : ""}Asked: ${lastResult.question_text}\nAnswer: ${lastResult.answer_text}`,
      linked_agent_ids: [agentId],
      linked_claim_ids: lastResult.new_claims.map((c) => c.claim_id),
      pinned_to_agent_id: agentId,
      player_tags: ["statement"],
    });
    setNotebookNote(
      `${agent.full_name}: ${lastResult.answer_text.slice(0, 100)}…`
    );
  };

  const revealHint = async () => {
    sfx.evidenceInspect();
    setBusy(true);
    try {
      const r = await api.challengeSuggestions(agentId, true);
      setSuggestions(r.suggestions);
      setHintsTaken(r.hints_taken);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const putItToThem = async () => {
    const claim = claims.find((c) => c.claim_id === confrontClaim);
    if (!claim || (confrontEvidence.length === 0 && confrontTestimony.length === 0)) return;
    const titles = [
      ...confrontEvidence.map((id) => clues.find((c) => c.clue_id === id)?.title ?? id),
      ...confrontTestimony.map((id) => {
        const t = allClaims.find((c) => c.claim_id === id);
        const who = agents.find((a) => a.agent_id === t?.speaker_agent_id)?.full_name.split(" ")[0];
        return t ? `${who} says: “${t.claim_text}”` : id;
      }),
    ].join("; ");
    await runChallenge(
      {
        target_agent_id: agentId,
        challenged_claim_id: claim.claim_id,
        claim_text: claim.claim_text,
        claim_status: claim.player_known_status,
        evidence_clue_id: confrontEvidence[0] ?? "",
        evidence_claim_id: confrontTestimony[0] ?? "",
        evidence_title: titles,
      },
      confrontEvidence,
      confrontTestimony
    );
    setConfrontEvidence([]);
    setConfrontTestimony([]);
  };

  const runChallenge = async (
    s: ChallengeSuggestion,
    evidenceIds?: string[],
    testimonyIds?: string[]
  ) => {
    sfx.questionSend();
    setBusy(true);
    setError(null);
    setFallbackMsg(null);
    setObserveMsg(null);
    setPendingQuestion(`You claimed: "${s.claim_text}" — but ${s.evidence_title}.`);
    try {
      const result = await api.challenge({
        target_agent_id: agentId,
        challenged_claim_id: s.challenged_claim_id,
        evidence_clue_ids: evidenceIds ?? (s.evidence_clue_id ? [s.evidence_clue_id] : []),
        evidence_claim_ids: testimonyIds ?? (s.evidence_claim_id ? [s.evidence_claim_id] : []),
        player_statement: `You claimed: "${s.claim_text}" — but ${s.evidence_title}.`,
      });
      setLastChallenge(result);
      setLastResult(null);
      if (beatOutcome(result.outcome) && cinematicsEnabled()) {
        setBeat({
          claimText: s.claim_text,
          evidenceText: s.evidence_title,
          outcomeText: result.response_text,
          outcomeLabel: result.outcome.replace(/_/g, " "),
        });
      }
      await refresh();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      endStall();
      setPendingQuestion(null);
      setBusy(false);
    }
  };

  return (
    <>
      {witnessReplayEventId && (
        <RewindIntro
          replayEventId={witnessReplayEventId}
          onDone={() => setWitnessReplayEventId(null)}
        />
      )}
      {notebookNote && (
        <NotebookNotification
          noteText={notebookNote}
          onDone={() => setNotebookNote(null)}
        />
      )}
      {beat && (
        <ContradictionBeat
          claimText={beat.claimText}
          evidenceText={beat.evidenceText}
          outcomeText={beat.outcomeText}
          outcomeLabel={beat.outcomeLabel}
          onDone={() => setBeat(null)}
        />
      )}

      {/* Main Middle Area: Interview Dossier */}
      <div className="interview-dossier-main">
        <div className="dossier-header-row">
          <div>
            <h1 className="dossier-page-title">Interview Dossier</h1>
            <p className="interview-direction">Start with {firstName}'s alibi, then test it against what you find.</p>
          </div>
        </div>

        {/* Dossier Header Card */}
        <div className="dossier-card panel">
          <RadialComposureAvatar
            agent={agent}
            pressure={pressure}
            stateLabel={state.label}
            activeTellClass={activeTellClass}
            onOpenDossier={onOpenDossier}
          />
          <div className="dossier-card-info">
            <div className="dossier-case-meta">
              {caseOverview.title.toUpperCase()} - {caseLabel(caseOverview.case_id).toUpperCase()}
            </div>
            <div className="dossier-name-row">
              <h2>{agent.full_name}</h2>
              <span className={`badge suspect-state state-${state.tone}`}>
                {state.label.toUpperCase()}
              </span>
            </div>
            <p className="dossier-subtitle">
              {agent.occupation} · {agent.age}
            </p>
            <div className="trait-chips">
              {agent.traits.map((t) => (
                <span key={t} className="trait-chip">
                  {t}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Middle Dual Split Area */}
        <div className="dossier-middle-split">
          {/* Left Sub-Column: Transcript Panel */}
          <div className={`transcript-card panel ${isExpanded ? "expanded" : ""}`}>
            <div className="transcript-head">
              <span className="transcript-title">TRANSCRIPT</span>
              <span className="muted small transcript-count">
                {transcript.length === 0
                  ? "not started"
                  : `${transcript.length} exchange${transcript.length === 1 ? "" : "s"}`}
              </span>
              <button
                type="button"
                className="transcript-expand-btn"
                title={isExpanded ? "Collapse transcript" : "Expand transcript"}
                onClick={() => setIsExpanded(!isExpanded)}
              >
                ⤢
              </button>
            </div>
            <div className="transcript-stream" ref={transcriptRef}>
              {transcript.length === 0 && !pendingQuestion && (
                <p className="muted transcript-empty">
                  You haven't questioned {firstName} yet. Begin with their alibi during the murder window, then follow up on anything that does not fit.
                </p>
              )}
              {transcript.map((m, i) => {
                const replayEventId = m.speaker === "agent"
                  ? witnessReplayForTestimony(caseOverview.case_id, agentId, m.revealed_clue_ids)
                  : null;
                return (
                <div
                  key={i}
                  className={`transcript-node bubble ${m.speaker} ${
                    m.revealed_clue_ids.length > 0 ? "important" : ""
                  } ${
                    m.speaker === "agent" &&
                    claims.some((c) => c.claim_text === m.text && c.claim_id === confrontClaim)
                      ? "selected-for-challenge"
                      : ""
                  }`}
                >
                  <span className="bubble-speaker">
                    {m.speaker === "player" ? "YOU" : firstName.toUpperCase()}
                  </span>
                  <p>
                    {m.text}
                    {m.deterministic_text && m.deterministic_text !== m.text && (
                      <span
                        className="muted small"
                        title={m.deterministic_text}
                        style={{ cursor: "help", marginLeft: "8px" }}
                      >
                        ✨
                      </span>
                    )}
                  </p>
                  {m.revealed_clue_ids.length > 0 && (
                    <p className="small badge new">
                      revealed: {m.revealed_clue_ids.join(", ")}
                    </p>
                  )}
                  <BehaviouralRead
                    tells={m.observable_tells}
                    onPin={(tell) =>
                      pinTell(
                        tell,
                        transcript[i - 1]?.speaker === "player"
                          ? `after being asked: “${transcript[i - 1].text}”`
                          : undefined
                      )
                    }
                  />
                  {replayEventId && (
                    <div className="witness-replay-offer">
                      <span>Witness account recorded</span>
                      <button
                        type="button"
                        className="small-button witness-replay-button"
                        onClick={() => setWitnessReplayEventId(replayEventId)}
                      >
                        Visualise {firstName}'s account
                      </button>
                    </div>
                  )}
                </div>
                );
              })}
              {pendingQuestion && (
                <div className="transcript-node bubble player pending">
                  <span className="bubble-speaker">YOU</span>
                  <p>{pendingQuestion}</p>
                </div>
              )}
              {stallLine && (
                <div className="transcript-node bubble agent stall-bubble">
                  <span className="bubble-speaker">{firstName.toUpperCase()}</span>
                  <p>{stallLine}</p>
                </div>
              )}
              {busy && !stallLine && (
                <p className="muted small emotional">{firstName} is considering their answer…</p>
              )}
              {lastResult?.emotional_shift && (
                <p className="muted small emotional">
                  {firstName} seems {lastResult.emotional_shift}.
                </p>
              )}
              {lastResult && lastResult.suggested_followups.length > 0 && (
                <div className="followups">
                  {lastResult.suggested_followups.map((f, i) => (
                    <button
                      key={i}
                      type="button"
                      className="followup-chip"
                      onClick={() => setFreeText(f)}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              )}
              {lastResult && (
                <button className="small-button" onClick={noteFromAnswer}>
                  Save answer as note
                </button>
              )}
              {lastChallenge && (
                <div className={`challenge-response outcome-${lastChallenge.outcome}`}>
                  <span className="badge outcome">
                    {lastChallenge.outcome.replace(/_/g, " ")}
                  </span>
                  {lastChallenge.testimony_conflict && (
                    <p className="testimony-conflict">
                      <strong>These cannot both be true.</strong>{" "}
                      {lastChallenge.testimony_conflict}
                    </p>
                  )}
                  {lastChallenge.emotional_shift && (
                    <span className="muted small">
                      {" "}
                      {firstName} seems {lastChallenge.emotional_shift}.
                    </span>
                  )}
                  {lastChallenge.pressure_delta > 0 && (
                    <span className="muted small pressure-up"> — composure slips</span>
                  )}
                  {lastChallenge.revealed_memories.map((m) => (
                    <p key={m.memory_id} className="small revealed-memory">
                      🗝️ {m.summary}
                    </p>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Sub-Column: Inspector & Contradiction Cards */}
          <div className="connected-inspector-cards">
            {/* Live Observation Card */}
            <div className="inspector-card observation-card panel">
              <div className="connector-elbow-line" />
              <div className="inspector-card-head">
                <span className="inspector-title">LIVE OBSERVATION</span>
                <span className="info-icon" title="Considered read of suspect baseline">ⓘ</span>
              </div>
              <div className="inspector-card-body">
                {observation ? (
                  <>
                    <p className="observation-text">“{observation.text}”</p>
                    <div className="observation-meta">
                      <span className="obs-tag">({observation.intensity})</span>
                      {observation.baseline_state && (
                        <span className="obs-tag">({BASELINE_LABEL[observation.baseline_state]})</span>
                      )}
                    </div>
                    <button
                      type="button"
                      className="small-button pin-note-btn"
                      onClick={pinObservation}
                    >
                      Pin behaviour note
                    </button>
                  </>
                ) : (
                  <>
                    <p className="observation-placeholder muted small">
                      Observe {firstName}'s posture and speech patterns to establish a baseline read.
                    </p>
                    <button
                      type="button"
                      className="small-button observe-action-btn"
                      onClick={observeThem}
                      disabled={busy}
                    >
                      Observe manner
                    </button>
                    {showObserveNudge && (
                      <span className="observe-nudge">
                        Calm reads set a baseline.
                      </span>
                    )}
                    {observeMsg && <p className="muted small observe-msg">{observeMsg}</p>}
                  </>
                )}
              </div>
            </div>

            {/* Put To [Suspect] Contradiction Card */}
            {!isVictim && claims.length > 0 && (
              <div className="inspector-card contradiction-card panel">
                <div className="connector-elbow-line" />
                <div className="inspector-card-head">
                  <span className="inspector-title">PUT TO [{firstName.toUpperCase()} {agent.full_name.split(" ")[1]?.toUpperCase() ?? ""}]</span>
                  <button
                    type="button"
                    className="clear-selection-btn"
                    title="Clear selection"
                    onClick={() => {
                      setConfrontClaim("");
                      setConfrontEvidence([]);
                      setConfrontTestimony([]);
                    }}
                  >
                    🗑
                  </button>
                </div>

                <div className="inspector-card-body">
                  <div className="confront-claims-group">
                    <span className="group-label">STATEMENTS BY {firstName.toUpperCase()}:</span>
                    {claims.map((c) => (
                      <label key={c.claim_id} className="confront-radio-item">
                        <input
                          type="radio"
                          name="confront-claim"
                          value={c.claim_id}
                          checked={confrontClaim === c.claim_id}
                          onChange={() => setConfrontClaim(c.claim_id)}
                        />
                        <span className="radio-text">
                          <span className={`badge status-${c.player_known_status}`}>
                            {c.player_known_status.toUpperCase()}
                          </span>{" "}
                          “{c.claim_text}”
                        </span>
                      </label>
                    ))}
                  </div>

                  <div className="confront-evidence-group">
                    <span className="group-label">CONTRADICTING EVIDENCE:</span>
                    {clues.map((c) => (
                      <label key={c.clue_id} className="confront-check-item">
                        <input
                          type="checkbox"
                          checked={confrontEvidence.includes(c.clue_id)}
                          onChange={(e) =>
                            setConfrontEvidence((prev) =>
                              e.target.checked
                                ? [...prev, c.clue_id]
                                : prev.filter((id) => id !== c.clue_id)
                            )
                          }
                        />
                        <span>{c.title}</span>
                      </label>
                    ))}
                    {otherTestimony.map((t) => {
                      const who =
                        agents.find((a) => a.agent_id === t.speaker_agent_id)?.full_name.split(" ")[0] ??
                        "Someone";
                      return (
                        <label key={t.claim_id} className="confront-check-item">
                          <input
                            type="checkbox"
                            checked={confrontTestimony.includes(t.claim_id)}
                            onChange={(e) =>
                              setConfrontTestimony((prev) =>
                                e.target.checked
                                  ? [...prev, t.claim_id]
                                  : prev.filter((id) => id !== t.claim_id)
                              )
                            }
                          />
                          <span>
                            <strong>{who}:</strong> “{t.claim_text}”
                          </span>
                        </label>
                      );
                    })}
                  </div>

                  {contradictionCount > 0 && (
                    <div className="contradiction-alert-banner">
                      <strong>CONTRADICTION FOUND</strong>
                      <p className="small">
                        You are holding evidence that contradicts{" "}
                        {contradictionCount === 1 ? "1 statement" : `${contradictionCount} statements`}{" "}
                        {firstName} has said. Which?
                      </p>
                    </div>
                  )}

                  <div className="confront-card-footer">
                    <label className="clear-logic-check">
                      <input
                        type="checkbox"
                        checked={clearLogic}
                        onChange={(e) => setClearLogic(e.target.checked)}
                      />
                      <span>Clear logic</span>
                    </label>

                    <button
                      type="button"
                      className="primary put-to-suspect-btn"
                      disabled={
                        busy ||
                        !confrontClaim ||
                        (confrontEvidence.length === 0 && confrontTestimony.length === 0)
                      }
                      onClick={putItToThem}
                    >
                      PUT TO [{firstName.toUpperCase()}]
                    </button>
                  </div>

                  {contradictionCount > 0 && suggestions.length === 0 && (
                    <button
                      type="button"
                      className="small-button hint-button"
                      disabled={busy}
                      onClick={revealHint}
                    >
                      Stuck? Show me what contradicts what
                      {hintsTaken > 0 && <span> ({hintsTaken} hints taken)</span>}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {error && <p className="error">{error}</p>}
        {fallbackMsg && <p className="error fallback-message">{fallbackMsg}</p>}
      </div>

      {/* Right Sidebar Column */}
      <aside className="dossier-right-sidebar">
        {/* Judgement Card */}
        <div className="judgement-card panel">
          <h3 className="sidebar-card-title">JUDGEMENT</h3>
          <label className="suspicion-select">
            <select
              value={suspicion}
              onChange={async (e) => {
                const level = e.target.value as SuspicionLevel;
                setSuspicion(level);
                await api.setSuspicion(agentId, level);
              }}
            >
              {SUSPICION_LEVELS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <p className="muted small judgement-note">
            Your judgement is private until you are ready to accuse.
          </p>
        </div>

        {/* Quick Tools Card */}
        <div className="quick-tools-card panel">
          <h3 className="sidebar-card-title">QUICK TOOLS</h3>

          {!isVictim && (
            <div className="quick-topic-buttons">
              <button
                type="button"
                className="quick-topic-btn active-gold"
                disabled={busy}
                onClick={() =>
                  ask(
                    "alibi",
                    {},
                    `Ask Alibi (${caseOverview.murder_window[0]}–${caseOverview.murder_window[1]})`
                  )
                }
              >
                Ask Alibi ({caseOverview.murder_window[0]}–{caseOverview.murder_window[1]})
              </button>
              <button
                type="button"
                className="quick-topic-btn"
                disabled={busy}
                onClick={() => ask("last_seen_victim", {}, `Last saw ${victimName}?`)}
              >
                Last saw {victimName}?
              </button>
              <button
                type="button"
                className="quick-topic-btn"
                disabled={busy}
                onClick={() => ask("relationship", {}, "Relationship with victim")}
              >
                Relationship with victim
              </button>
              <div className="quick-time-row">
                <input
                  type="time"
                  className="quick-time-input"
                  value={timeRef}
                  min={caseOverview.sim_start_time}
                  max={caseOverview.discovery_time}
                  onChange={(e) => setTimeRef(e.target.value)}
                />
                <button
                  type="button"
                  className="quick-topic-btn flex-1"
                  disabled={busy}
                  onClick={() =>
                    ask(
                      "timeline",
                      { time_reference: timeRef },
                      `What were you doing at ${timeRef}?`
                    )
                  }
                >
                  Doing at {timeRef}?
                </button>
              </div>
            </div>
          )}

          {/* Custom Ask Box */}
          <div className="quick-ask-box">
            <input
              type="text"
              className="quick-ask-input"
              placeholder={placeholder}
              value={freeText}
              onChange={(e) => {
                setFreeText(e.target.value);
                setFallbackMsg(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitFreeText();
              }}
              disabled={busy}
            />
            <button
              type="button"
              className="quick-ask-submit-btn"
              disabled={busy || !freeText.trim()}
              onClick={submitFreeText}
            >
              {busy ? "ASKING…" : "ASK"}
            </button>
          </div>

          {/* Dynamic Dropdowns for Place & Evidence */}
          {!isVictim && (
            <div className="quick-dropdowns-group">
              <select
                className="quick-select-dropdown"
                value={locationTopic}
                onChange={(e) => {
                  const val = e.target.value;
                  setLocationTopic(val);
                  if (val) {
                    ask(
                      "location",
                      { topic_location_id: val },
                      `Ask about ${locations.find((l) => l.location_id === val)?.name ?? "this place"}`
                    );
                  }
                }}
              >
                <option value="">Place ˅</option>
                {locations.map((l) => (
                  <option key={l.location_id} value={l.location_id}>
                    {l.name}
                  </option>
                ))}
              </select>

              <select
                className="quick-select-dropdown"
                value={clueTopic}
                onChange={(e) => {
                  const val = e.target.value;
                  setClueTopic(val);
                  if (val) {
                    ask(
                      "evidence",
                      { topic_clue_id: val },
                      `Confront with ${clues.find((c) => c.clue_id === val)?.title ?? "this evidence"}`
                    );
                  }
                }}
              >
                <option value="">Discovered Evidence ˅</option>
                {clues.map((c) => (
                  <option key={c.clue_id} value={c.clue_id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

function AutopsyPanel({
  agentId,
  onBoardState,
}: {
  agentId: string;
  onBoardState: (suspects: BoardSuspect[]) => void;
}) {
  const { agents } = useWorld();
  const agent = agents.find((a) => a.agent_id === agentId)!;
  const [result, setResult] = useState<InspectResult | null>(null);
  // The subject arrives covered; the sheet must be folded back before the
  // magnifier can find anything.
  const [sheetFolded, setSheetFolded] = useState(false);

  const toggleSheet = () => {
    sfx.sheetPull();
    setSheetFolded((f) => !f);
  };

  const refresh = useCallback(() => {
    api.examineBody(agentId).then(setResult);
    api.board().then((b) => {
      onBoardState(b.suspects);
    });
  }, [agentId, onBoardState]);

  useEffect(refresh, [refresh]);

  const handleDiscover = async (clueId: string) => {
    try {
      await api.discoverClue(clueId);
      sfx.evidenceFound();
      refresh();
    } catch (err: any) {
      console.error(err);
    }
  };

  if (!result) {
    return <div className="interview-panel loading panel">Loading forensic details...</div>;
  }

  const { location, hidden_clues, known_clues } = result;
  const found = known_clues?.length || 0;
  const total = found + (hidden_clues?.length || 0);
  const pct = total > 0 ? Math.round((found / total) * 100) : 0;
  const postMortemPortrait =
    lifelikeDeceasedPortrait(agent) || lifelikeCalmPortrait(agent) || undefined;

  return (
    <div className="interview-panel panel autopsy-panel">
      <header className="morgue-masthead">
        <p className="morgue-eyebrow">Homicide Division · Post-Mortem Examination</p>
        <div className="morgue-name-row">
          <h2 className="morgue-name">{agent.full_name}</h2>
          <span className="morgue-chip">Deceased</span>
        </div>
      </header>

      <div className="autopsy-room">
        <aside className="autopsy-tray" aria-label="Instrument tray">
          <span className="tray-label">Instruments</span>
          <button
            type="button"
            className={`tray-tool sheet-tool ${sheetFolded ? "" : "attention"}`}
            onClick={toggleSheet}
            title={sheetFolded ? "Replace the sheet" : "Gloves — fold back the sheet"}
          >
            🧤
          </button>
          <button
            type="button"
            className={`tray-tool ${sheetFolded ? "active" : ""}`}
            disabled={!sheetFolded}
            title={
              sheetFolded
                ? "Field magnifier — sweep it over the body"
                : "Fold back the sheet first"
            }
          >
            🔍
          </button>
          <button type="button" className="tray-tool" disabled title="Scalpel — coroner's use only">🔪</button>
          <button type="button" className="tray-tool" disabled title="Shears — coroner's use only">✂️</button>
          <button type="button" className="tray-tool" disabled title="Syringe — coroner's use only">💉</button>
          <span className="tray-note">
            {sheetFolded
              ? "Only your field magnifier is cleared for use."
              : "The subject is covered. Fold back the sheet to begin."}
          </span>
        </aside>

        <div className="autopsy-slab-area">
          <div className="morgue-lamp" aria-hidden="true" />
          <div className="autopsy-slab">
            <MagnifyingSearch
              bounds={null}
              hiddenClues={hidden_clues}
              onDiscover={handleDiscover}
              imageUrl={postMortemPortrait}
              isPortrait={true}
              sheetFolded={sheetFolded}
            />
            <div className="slab-foot">
              <span className="toe-tag">{agent.full_name} · deceased</span>
            </div>
          </div>
          <p className="small muted autopsy-hint">
            {sheetFolded
              ? "Sweep the magnifier over the body — click when the lens glints."
              : "Take the gloves and fold back the sheet to examine the body."}
          </p>
        </div>

        <aside className="autopsy-report">
          <div className="clipboard-clip" aria-hidden="true" />
          <div className="coroner-sheet">
            <span className="coroner-stamp" aria-hidden="true">Preliminary</span>
            <header className="coroner-head">
              <span className="coroner-office">Office of the County Coroner</span>
              <span className="coroner-form-no">Form 12-B · External Examination</span>
            </header>
            <div className="report-field">
              <span className="report-label">Subject</span>
              {agent.full_name} · {agent.occupation}
            </div>
            <div className="report-field">
              <span className="report-label">Preliminary finding</span>
              {location.description}
            </div>
            <div className="report-field">
              <span className="report-label">External examination</span>
              <div className="exam-progress">
                <div className="exam-progress-fill" style={{ width: `${pct}%` }} />
              </div>
              <span className="small exam-count">
                {found} / {total} observations logged
              </span>
            </div>
            <div className="report-field report-evidence">
              <span className="report-label">Findings on record</span>
              {known_clues && known_clues.length > 0 ? (
                <div className="found-evidence-list">
                  {known_clues.map((c: any) => (
                    <ClueCard key={c.clue_id} clue={c} />
                  ))}
                </div>
              ) : (
                <p className="small nothing-found">
                  — no findings entered —
                </p>
              )}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
