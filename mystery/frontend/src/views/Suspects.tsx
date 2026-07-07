import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type {
  AskResult,
  BoardSuspect,
  ChallengeResult,
  ChallengeSuggestion,
  ClaimPublic,
  CluePublic,
  InspectResult,
  QuestionType,
  SuspicionLevel,
  TranscriptMessage,
} from "../types";
import { MagnifyingSearch } from "../components/MagnifyingSearch";
import { ClueCard } from "./shared";
import Portrait, { DEFENSIVE_THRESHOLD, CRACKING_THRESHOLD } from "../components/Portrait";
import ContradictionBeat from "../components/ContradictionBeat";
import NotebookNotification from "../components/NotebookNotification";
import { audioManager } from "../audio";
import { cinematicsEnabled } from "../settings";

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

const SUSPICION_LEVELS: { value: SuspicionLevel; label: string }[] = [
  { value: "unknown", label: "Unmarked" },
  { value: "person_of_interest", label: "Person of interest" },
  { value: "suspect", label: "Suspect" },
  { value: "prime_suspect", label: "Prime suspect" },
  { value: "likely_innocent", label: "Likely innocent" },
  { value: "cleared", label: "Cleared" },
];

const SUSPICION_LABEL = Object.fromEntries(
  SUSPICION_LEVELS.map((s) => [s.value, s.label])
) as Record<SuspicionLevel, string>;

interface SuspectBoardState {
  pressure: number;
  suspicion: SuspicionLevel;
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
  const { agents } = useWorld();
  const [boardState, setBoardState] = useState<Record<string, SuspectBoardState>>({});
  const [selectedId, setSelectedId] = useState(
    (focusAgentId && agents.some((a) => a.agent_id === focusAgentId)
      ? focusAgentId
      : agents[0]?.agent_id) ?? ""
  );
  useEffect(() => {
    if (focusAgentId && agents.some((a) => a.agent_id === focusAgentId)) {
      setSelectedId(focusAgentId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusAgentId]);
  const selected = agents.find((a) => a.agent_id === selectedId);

  const onBoardState = useCallback((suspects: BoardSuspect[]) => {
    setBoardState(
      Object.fromEntries(
        suspects.map((s) => [
          s.agent.agent_id,
          { pressure: s.pressure ?? 0, suspicion: s.suspicion },
        ])
      )
    );
  }, []);

  return (
    <div className="suspects">
      <aside className="suspect-list panel">
        <p className="roster-title">Suspects</p>
        {agents.map((a) => {
          const info = boardState[a.agent_id];
          return (
            <button
              key={a.agent_id}
              className={`suspect ${selectedId === a.agent_id ? "active" : ""}`}
              onClick={() => setSelectedId(a.agent_id)}
            >
              <Portrait agent={a} pressure={info?.pressure ?? 0} />
              <span>
                <span className="suspect-name">{a.full_name}</span>
                <span className="muted small">{a.occupation}</span>
                {info && info.suspicion !== "unknown" && (
                  <span className={`list-suspicion suspicion-${info.suspicion}`}>
                    {SUSPICION_LABEL[info.suspicion]}
                  </span>
                )}
              </span>
            </button>
          );
        })}
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
          />
        )
      )}
    </div>
  );
}

function InterviewPanel({
  agentId,
  pressure,
  onBoardState,
}: {
  agentId: string;
  pressure: number;
  onBoardState: (suspects: BoardSuspect[]) => void;
}) {
  const { agents, locations, caseOverview } = useWorld();
  const agent = agents.find((a) => a.agent_id === agentId)!;
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [lastResult, setLastResult] = useState<AskResult | null>(null);
  const [clues, setClues] = useState<CluePublic[]>([]);
  const [claims, setClaims] = useState<ClaimPublic[]>([]);
  const [suspicion, setSuspicion] = useState<SuspicionLevel>("unknown");
  const [suggestions, setSuggestions] = useState<ChallengeSuggestion[]>([]);
  const [lastChallenge, setLastChallenge] = useState<ChallengeResult | null>(null);
  const [beat, setBeat] = useState<BeatData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [notebookNote, setNotebookNote] = useState<string | null>(null);

  const [timeRef, setTimeRef] = useState("07:50");
  const [clueTopic, setClueTopic] = useState("");
  const [locationTopic, setLocationTopic] = useState("");
  const [freeText, setFreeText] = useState("");
  const [fallbackMsg, setFallbackMsg] = useState<string | null>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);

  const firstName = agent.full_name.split(" ")[0];
  const victimName = caseOverview.victim.full_name.split(" ")[0];
  const isVictim = agent.is_victim;
  const placeholder = isVictim 
    ? `Examine body (e.g. search pockets, check wounds, cause of death…)`
    : `Ask ${firstName} about ${victimName}, the timeline, a place, or discovered evidence…`;

  const contradicted =
    suggestions.length > 0 ||
    claims.some((c) => c.player_known_status === "disputed");
  const state = interviewState(transcript.length, suspicion, pressure, contradicted);

  const refresh = useCallback(() => {
    api.transcript(agentId).then((t) => {
      setTranscript(t);
      setPendingQuestion(null);
    });
    api.clues().then(setClues);
    api.challengeSuggestions(agentId).then(setSuggestions);
    api.board().then((b) => {
      const me = b.suspects.find((s) => s.agent.agent_id === agentId);
      if (me) {
        setSuspicion(me.suspicion);
        setClaims(me.claims);
      }
      onBoardState(b.suspects);
    });
  }, [agentId, onBoardState]);

  useEffect(refresh, [refresh]);

  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [transcript, lastResult, lastChallenge, busy]);

  // Audio trigger: Contradiction locked
  useEffect(() => {
    if (lastChallenge && lastChallenge.outcome === "contradiction_locked") {
      audioManager.playStinger("contradiction_locked");
    }
  }, [lastChallenge]);

  // Audio trigger: Pressure thresholds
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
    setBusy(true);
    setError(null);
    setPendingQuestion(questionText ?? null);
    try {
      const result = await api.ask({
        agent_id: agentId,
        question_type: questionType,
        ...extra,
      });
      setLastResult(result);
      setLastChallenge(null);
      setFallbackMsg(null);
      refresh();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
      setPendingQuestion(null);
    } finally {
      setBusy(false);
    }
  };

  const submitFreeText = async () => {
    if (!freeText.trim()) return;
    const questionText = freeText.trim();
    setBusy(true);
    setError(null);
    setFallbackMsg(null);
    setPendingQuestion(questionText);
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
          // Best-effort lookups from already-public data; generic labels if
          // either side can't be resolved.
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
        // The challenge suggestion will appear in the UI list after refresh!
      } else if (result.fallback_message) {
        setFallbackMsg(result.fallback_message);
      }
      setFreeText("");
      refresh();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
      setPendingQuestion(null);
    } finally {
      setBusy(false);
    }
  };

  const noteFromAnswer = async () => {
    if (!lastResult) return;
    await api.createNote({
      note_type: "interview",
      title: `${agent.full_name}: ${lastResult.answer_text.slice(0, 70)}…`,
      body: `Q: ${lastResult.question_text}\nA: ${lastResult.answer_text}`,
      linked_agent_ids: [agentId],
      linked_claim_ids: lastResult.new_claims.map((c) => c.claim_id),
      pinned_to_agent_id: agentId,
    });
    setNotebookNote(
      `${agent.full_name}: ${lastResult.answer_text.slice(0, 100)}…`
    );
  };

  const runChallenge = async (s: ChallengeSuggestion) => {
    setBusy(true);
    setError(null);
    setFallbackMsg(null);
    try {
      const result = await api.challenge({
        target_agent_id: agentId,
        challenged_claim_id: s.challenged_claim_id,
        evidence_clue_ids: [s.evidence_clue_id],
        player_statement: `You claimed: "${s.claim_text}" — but ${s.evidence_title}.`,
      });
      setLastChallenge(result);
      setLastResult(null);
      // Phase D: stage the collision only for caught contradictions; with
      // cinematics off the plain result below renders immediately.
      if (beatOutcome(result.outcome) && cinematicsEnabled()) {
        setBeat({
          claimText: s.claim_text,
          evidenceText: s.evidence_title,
          outcomeText: result.response_text,
          outcomeLabel: result.outcome.replace(/_/g, " "),
        });
      }
      refresh();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
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
      <div className="interview interrogation-main">
        <div className="dossier panel">
          <div className="dossier-portrait">
            <Portrait agent={agent} pressure={pressure} size="large" />
          </div>
          <div className="dossier-body">
            <div className="dossier-title">
              <h2>{agent.full_name}</h2>
              <span className={`badge suspect-state state-${state.tone}`}>{state.label}</span>
            </div>
            <p className="muted dossier-meta">
              {agent.occupation} · {agent.age}
            </p>
            <div className="trait-chips">
              {agent.traits.map((t) => (
                <span key={t} className="trait-chip">
                  {t}
                </span>
              ))}
            </div>
            <p className="muted small dossier-routine">{agent.routine_summary}</p>
          </div>
        </div>

        <div className="transcript-card panel">
          <div className="transcript-head">
            <span className="rec-dot" aria-hidden="true" />
            <span className="transcript-title">Interview transcript</span>
            <span className="muted small transcript-count">
              {transcript.length === 0
                ? "not started"
                : `${transcript.length} exchange${transcript.length === 1 ? "" : "s"}`}
            </span>
          </div>
          <div className="transcript" ref={transcriptRef}>
            {transcript.length === 0 && !pendingQuestion && (
              <p className="muted transcript-empty">
                You haven't questioned {firstName} yet. Open with a question below — start
                with their alibi, or ask anything in your own words.
              </p>
            )}
            {transcript.map((m, i) => (
              <div
                key={i}
                className={`bubble ${m.speaker} ${
                  m.revealed_clue_ids.length > 0 ? "important" : ""
                }`}
              >
                <span className="bubble-speaker">
                  {m.speaker === "player" ? "You" : firstName}
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
              </div>
            ))}
            {pendingQuestion && (
              <div className="bubble player pending">
                <span className="bubble-speaker">You</span>
                <p>{pendingQuestion}</p>
              </div>
            )}
            {busy && (
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
                {lastChallenge.emotional_shift && (
                  <span className="muted small">
                    {" "}
                    {firstName} seems {lastChallenge.emotional_shift}.
                  </span>
                )}
                {lastChallenge.pressure_delta > 0 && (
                  <span className="muted small pressure-up"> pressure ↑</span>
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

        {error && <p className="error">{error}</p>}
        {fallbackMsg && <p className="error fallback-message">{fallbackMsg}</p>}

        {suggestions.length > 0 && (
          <div className="challenge-builder panel">
            <h3>Contradictions you can press</h3>
            <p className="muted small">
              You hold evidence that conflicts with what {firstName} has told you. Confront
              them.
            </p>
            {suggestions.map((s) => (
              <div
                key={`${s.challenged_claim_id}:${s.evidence_clue_id}`}
                className="challenge-card"
              >
                <div className="challenge-claim">
                  <span className={`badge status-${s.claim_status}`}>{s.claim_status}</span>
                  <span>“{s.claim_text}”</span>
                </div>
                <div className="challenge-evidence">
                  <span className="muted small">contradicted by</span> {s.evidence_title}
                </div>
                <button className="challenge-btn" disabled={busy} onClick={() => runChallenge(s)}>
                  Challenge
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="question-builder panel">
          <div className="question-row free-text-row">
            <input
              type="text"
              className="flex-1 free-text-input"
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
              className="primary ask-btn"
              disabled={busy || !freeText.trim()}
              title={!freeText.trim() ? "Type a question first" : undefined}
              onClick={submitFreeText}
            >
              {isVictim ? "Examine" : "Ask"}
            </button>
          </div>
          <p className="muted small input-help">
            {isVictim
              ? "Examine the body for clues or ask about the cause of death."
              : "Ask about people, places, times, motives, or evidence."}
          </p>
          
          {!isVictim && (
            <>
              <div className="question-divider">
                <span className="muted small">or use predefined topics</span>
              </div>
          <div className="question-row">
            <button
              disabled={busy}
              onClick={() =>
                ask(
                  "alibi",
                  {},
                  `Ask alibi (${caseOverview.murder_window[0]}–${caseOverview.murder_window[1]})`
                )
              }
            >
              Ask alibi ({caseOverview.murder_window[0]}–{caseOverview.murder_window[1]})
            </button>
            <button
              disabled={busy}
              onClick={() => ask("last_seen_victim", {}, `Last saw ${victimName}?`)}
            >
              Last saw {victimName}?
            </button>
            <button
              disabled={busy}
              onClick={() => ask("relationship", {}, "Relationship with victim")}
            >
              Relationship with victim
            </button>
          </div>
          <div className="question-row">
            <input
              type="time"
              value={timeRef}
              min={caseOverview.sim_start_time}
              max={caseOverview.discovery_time}
              onChange={(e) => setTimeRef(e.target.value)}
            />
            <button
              disabled={busy}
              onClick={() =>
                ask(
                  "timeline",
                  { time_reference: timeRef },
                  `What were you doing at ${timeRef}?`
                )
              }
            >
              What were you doing at {timeRef}?
            </button>
          </div>
          </>
          )}
        </div>

        {!isVictim && (
        <div className="structured-cards">
          <div className="structured-card panel">
            <h3 className="structured-title">Question about a place</h3>
            <p className="muted small">
              Ask {firstName} what they know about a location on the estate.
            </p>
            <div className="question-row">
              <select
                className="flex-1"
                value={locationTopic}
                onChange={(e) => setLocationTopic(e.target.value)}
              >
                <option value="">Pick a place…</option>
                {locations.map((l) => (
                  <option key={l.location_id} value={l.location_id}>
                    {l.name}
                  </option>
                ))}
              </select>
              <button
                disabled={busy || !locationTopic}
                title={!locationTopic ? "Pick a place first" : undefined}
                onClick={() =>
                  ask(
                    "location",
                    { topic_location_id: locationTopic },
                    `Ask about ${
                      locations.find((l) => l.location_id === locationTopic)?.name ??
                      "this place"
                    }`
                  )
                }
              >
                Ask about this place
              </button>
            </div>
            {!locationTopic && (
              <p className="muted small disabled-hint">Pick a place to enable the question.</p>
            )}
          </div>

          <div className="structured-card evidence panel">
            <h3 className="structured-title">Confront with evidence</h3>
            <p className="muted small">
              Put a discovered clue in front of {firstName} and watch their reaction.
            </p>
            <div className="question-row">
              <select
                className="flex-1"
                value={clueTopic}
                onChange={(e) => setClueTopic(e.target.value)}
              >
                <option value="">Pick discovered evidence…</option>
                {clues.map((c) => (
                  <option key={c.clue_id} value={c.clue_id}>
                    {c.title}
                  </option>
                ))}
              </select>
              <button
                className="confront-btn"
                disabled={busy || !clueTopic}
                title={
                  clues.length === 0
                    ? "No evidence discovered yet"
                    : !clueTopic
                      ? "Pick evidence first"
                      : undefined
                }
                onClick={() =>
                  ask(
                    "evidence",
                    { topic_clue_id: clueTopic },
                    `Confront with ${
                      clues.find((c) => c.clue_id === clueTopic)?.title ?? "this evidence"
                    }`
                  )
                }
              >
                Confront with evidence
              </button>
            </div>
            {clues.length === 0 ? (
              <p className="muted small disabled-hint">
                No evidence discovered yet — search Places to find some.
              </p>
            ) : (
              !clueTopic && (
                <p className="muted small disabled-hint">
                  Pick evidence to enable the confrontation.
                </p>
              )
            )}
          </div>
        </div>
        )}

        {lastResult && lastResult.revealed_clues.length > 0 && (
          <div className="revealed">
            {lastResult.revealed_clues.map((c) => (
              <ClueCard key={c.clue_id} clue={c} isNew />
            ))}
          </div>
        )}

        {lastChallenge && lastChallenge.revealed_clues.length > 0 && (
          <div className="revealed">
            {lastChallenge.revealed_clues.map((c) => (
              <ClueCard key={c.clue_id} clue={c} isNew />
            ))}
          </div>
        )}
      </div>

      <aside className="judgement-panel panel">
        <p className="judgement-title">Your judgement</p>
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
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <p className="muted small">Your judgement is private until you're ready to accuse.</p>
        <div className="judgement-state">
          <span className="muted small">Demeanour</span>
          <span className={`badge suspect-state state-${state.tone}`}>{state.label}</span>
        </div>
        <div className="pressure-block">
          <span className="muted small">Pressure</span>
          <div className="pressure-meter" title={`Pressure: ${Math.round(pressure * 100)}%`}>
            <div
              className="pressure-fill"
              style={{ width: `${Math.min(100, Math.round(pressure * 100))}%` }}
            />
          </div>
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
      audioManager.playStinger("clue_discovered");
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

  return (
    <div className="interview-panel panel autopsy-panel">
      <div className="transcript-header">
        <span className="small muted">Homicide Division · Post-Mortem Examination</span>
        <div>{agent.full_name}</div>
      </div>

      <div className="autopsy-room">
        <aside className="autopsy-tray" aria-label="Instrument tray">
          <span className="tray-label">Instruments</span>
          <button type="button" className="tray-tool active" title="Field magnifier — sweep it over the body">🔍</button>
          <button type="button" className="tray-tool" disabled title="Scalpel — coroner's use only">🔪</button>
          <button type="button" className="tray-tool" disabled title="Shears — coroner's use only">✂️</button>
          <button type="button" className="tray-tool" disabled title="Syringe — coroner's use only">💉</button>
          <button type="button" className="tray-tool" disabled title="Sample jars — coroner's use only">🧪</button>
          <span className="tray-note">Only your field magnifier is cleared for use.</span>
        </aside>

        <div className="autopsy-slab-area">
          <div className="morgue-lamp" aria-hidden="true" />
          <div className="autopsy-slab">
            <MagnifyingSearch
              bounds={null}
              hiddenClues={hidden_clues}
              onDiscover={handleDiscover}
              imageUrl={agent.portrait_art?.calm || undefined}
              spriteAsset={agent.sprite_asset || undefined}
              isPortrait={true}
            />
            <div className="slab-foot">
              <span className="toe-tag">{agent.full_name} · deceased</span>
            </div>
          </div>
          <p className="small muted autopsy-hint">
            Sweep the magnifier over the body — click when the lens glints.
          </p>
        </div>

        <aside className="autopsy-report">
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
            <span className="small muted">{found} / {total} clues found</span>
          </div>
          <div className="report-field report-evidence">
            <span className="report-label">Found evidence</span>
            {known_clues && known_clues.length > 0 ? (
              <div className="found-evidence-list">
                {known_clues.map((c: any) => (
                  <ClueCard key={c.clue_id} clue={c} />
                ))}
              </div>
            ) : (
              <p className="muted small" style={{ margin: 0 }}>Nothing found yet.</p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
