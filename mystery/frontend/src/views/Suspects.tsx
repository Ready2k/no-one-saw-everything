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
  expressionForPressure,
} from "../components/Portrait";
import ContradictionBeat from "../components/ContradictionBeat";
import ComposureMeter from "../components/ComposureMeter";
import NotebookNotification from "../components/NotebookNotification";
import { audioManager } from "../audio";
import { cinematicsEnabled } from "../settings";
import { sfx } from "../sfx";

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
        {agents.filter((a) => !a.is_background).map((a) => {
          const info = boardState[a.agent_id];
          return (
            <button
              key={a.agent_id}
              className={`suspect ${selectedId === a.agent_id ? "active" : ""} ${
                a.is_victim ? "victim" : ""
              }`}
              onClick={() => {
                if (a.agent_id !== selectedId) sfx.paperSlide();
                setSelectedId(a.agent_id);
              }}
            >
              <Portrait agent={a} pressure={info?.pressure ?? 0} />
              <span>
                <span className="suspect-name">{a.full_name}</span>
                <span className="muted small">{a.occupation}</span>
                {a.is_victim ? (
                  <span className="list-victim">✝ Victim · deceased</span>
                ) : (
                  info &&
                  info.suspicion !== "unknown" && (
                    <span className={`list-suspicion suspicion-${info.suspicion}`}>
                      {SUSPICION_LABEL[info.suspicion]}
                    </span>
                  )
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
  // The game tells you HOW MANY of this suspect's statements you can disprove — never which.
  // Working that out is the game. `suggestions` stays empty unless the player asks for a hint.
  const [contradictionCount, setContradictionCount] = useState(0);
  const [hintsTaken, setHintsTaken] = useState(0);
  const [suggestions, setSuggestions] = useState<ChallengeSuggestion[]>([]);
  // The confrontation the player is building: one claim, and the evidence they think disproves
  // it — physical clues, other people's testimony, or both.
  const [confrontClaim, setConfrontClaim] = useState("");
  const [confrontEvidence, setConfrontEvidence] = useState<string[]>([]);
  const [confrontTestimony, setConfrontTestimony] = useState<string[]>([]);
  // Everything anyone has told the player. What OTHERS said is usable against this suspect.
  const [allClaims, setAllClaims] = useState<ClaimPublic[]>([]);
  const [lastChallenge, setLastChallenge] = useState<ChallengeResult | null>(null);
  // The Observe action: a deliberate study of the suspect, spent one per fresh exchange.
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

  // Testimony usable AGAINST this suspect: everything the player has heard from anyone else.
  // Their own statements are already listed as the thing being challenged.
  const otherTestimony = allClaims.filter((c) => c.speaker_agent_id !== agentId);

  // "Contradicted" is a fact about HER — a claim of hers that a challenge has actually disputed —
  // not about what the player is holding. Merely holding an unused contradiction
  // (contradictionCount > 0) is a prompt to act, surfaced in the "Put it to …" panel below; it
  // must not brand a 100%-composed, un-challenged suspect as already caught.
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

  const refresh = useCallback(() => {
    api.transcript(agentId).then((t) => {
      setTranscript(t);
      setPendingQuestion(null);
    });
    api.clues().then(setClues);
    api.claims().then(setAllClaims);
    api.challengeSuggestions(agentId).then((r) => {
      setContradictionCount(r.contradiction_count);
      setHintsTaken(r.hints_taken);
      setSuggestions([]); // a fresh look never re-reveals a hint the player already spent
    });
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

  useEffect(() => {
    const nextClass = tellClass(latestTell);
    setActiveTellClass(nextClass);
    if (!nextClass) return;
    const t = setTimeout(() => setActiveTellClass(""), 1150);
    return () => clearTimeout(t);
  }, [latestTell?.tell_id]);

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
    sfx.questionSend();
    setBusy(true);
    setError(null);
    setPendingQuestion(questionText ?? null);
    setObserveMsg(null);
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
    sfx.questionSend();
    setBusy(true);
    setError(null);
    setFallbackMsg(null);
    setPendingQuestion(questionText);
    setObserveMsg(null);
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

  /** Spend an action watching them. The backend 409s until there is a fresh
   *  exchange to watch — that refusal is shown to the player as-is. */
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

  /** Pin a strong behavioural read where it becomes evidence-adjacent: on the
   *  suspect's page of the notebook, with the moment it was seen. */
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
    sfx.pencilScratch();
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

  /** The player has assembled a confrontation themselves: a statement they heard, and what they
   *  think disproves it — a clue, someone else's word, or both. They may well be wrong; the
   *  engine answers either way. */
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
    try {
      const result = await api.challenge({
        target_agent_id: agentId,
        challenged_claim_id: s.challenged_claim_id,
        evidence_clue_ids: evidenceIds ?? (s.evidence_clue_id ? [s.evidence_clue_id] : []),
        evidence_claim_ids: testimonyIds ?? [],
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
        <div className="active-case-strip" title="Active case loaded by the investigation server">
          <span>Active file</span>
          <strong>{caseLabel(caseOverview.case_id)}</strong>
          <span>{caseOverview.title}</span>
        </div>
        <div className="dossier panel">
          {/* Police line-up mugshot: height-chart wall, placard, and a
              backdrop that heats up as interrogation pressure rises. */}
          <div className={`dossier-portrait mugshot mugshot-${expressionForPressure(pressure)} ${activeTellClass}`}>
            <div className="mugshot-wall" aria-hidden="true" />
            <Portrait agent={agent} pressure={pressure} size="large" />
            <span className="mugshot-placard">
              {agent.full_name}
            </span>
          </div>
          <div className="dossier-body">
            <div className="dossier-title">
              <h2>{agent.full_name}</h2>
              <span className={`badge suspect-state state-${state.tone}`}>{state.label}</span>
            </div>
            <p className="muted dossier-meta">
              {agent.occupation} · {agent.age}
            </p>
            {/* Composure made visible: the meter drains as the interrogation bites, so the
                player can read how close a suspect is to breaking. */}
            <ComposureMeter
              name={firstName}
              pressure={pressure}
              lastShift={lastChallenge?.emotional_shift ?? lastResult?.emotional_shift}
            />
            {/* Observe: spend an action for a considered read of how they're holding
                up. One per fresh exchange — the refusal message is part of the game. */}
            <div className="observe-row">
              <button
                type="button"
                className="small-button observe-button"
                onClick={observeThem}
                disabled={busy}
                title={`Study ${firstName}'s manner in this exchange`}
              >
                Observe manner
              </button>
              {showObserveNudge && (
                <span className="observe-nudge">
                  Calm reads set a baseline.
                </span>
              )}
              {observeMsg && <span className="muted small observe-msg">{observeMsg}</span>}
            </div>
            {observation && (
              <div className={`observe-read observe-${observation.intensity}`}>
                <div className="observe-read-head">
                  <span className="behavioural-title">Considered read</span>
                  <span className={`tell-tags observe-tags`}>
                    <span>{observation.category}</span>
                    <span>{observation.intensity}</span>
                  </span>
                  {observation.baseline_state && (
                    <span className={`observe-baseline observe-baseline-${observation.baseline_state}`}>
                      {BASELINE_LABEL[observation.baseline_state]}
                    </span>
                  )}
                </div>
                <p>{observation.text}</p>
                <p className="muted small observe-footnote">
                  A change in manner is a clue to interpret, not proof.
                </p>
                <button type="button" className="small-button" onClick={pinObservation}>
                  Pin behaviour note
                </button>
              </div>
            )}
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
            <BehaviouralRead
              tells={lastResult?.observable_tells}
              onPin={(tell) =>
                pinTell(
                  tell,
                  lastResult ? `after being asked: “${lastResult.question_text}”` : undefined
                )
              }
            />
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
                {/* The player caught two statements that cannot both be true. Show them the
                    collision — the deduction is theirs and they should see it land. */}
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
                  <span className="muted small pressure-up"> — their composure slips</span>
                )}
                <BehaviouralRead
                  tells={lastChallenge.observable_tells}
                  onPin={(tell) => pinTell(tell, "when confronted with the evidence")}
                />
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

        {!isVictim && claims.length > 0 && (
          <div className="challenge-builder panel">
            <h3>Put it to {firstName}</h3>
            <p className="muted small">
              Pick something {firstName} has told you, and the evidence you think disproves it.
              {contradictionCount > 0 ? (
                <>
                  {" "}
                  <strong className="contradiction-nudge">
                    You are holding evidence that contradicts{" "}
                    {contradictionCount === 1
                      ? "one thing"
                      : `${contradictionCount} things`}{" "}
                    {firstName} has said.
                  </strong>{" "}
                  Which?
                </>
              ) : (
                <> Nothing you hold disproves {firstName} yet — but you can still try.</>
              )}
            </p>

            <div className="confront-columns">
              <div className="confront-col">
                <h4 className="confront-heading">What {firstName} has told you</h4>
                {claims.map((c) => (
                  <label key={c.claim_id} className="confront-option">
                    <input
                      type="radio"
                      name="confront-claim"
                      value={c.claim_id}
                      checked={confrontClaim === c.claim_id}
                      onChange={() => setConfrontClaim(c.claim_id)}
                    />
                    <span className={`badge status-${c.player_known_status}`}>
                      {c.player_known_status}
                    </span>{" "}
                    <span>“{c.claim_text}”</span>
                  </label>
                ))}
              </div>

              <div className="confront-col">
                <h4 className="confront-heading">Evidence in your notebook</h4>
                {clues.length === 0 ? (
                  <p className="muted small disabled-hint">
                    Nothing yet — search Places to find some.
                  </p>
                ) : (
                  clues.map((c) => (
                    <label key={c.clue_id} className="confront-option">
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
                  ))
                )}
              </div>

              {/* No one saw everything. What another villager told you is evidence too — and it
                  is often the only thing that can break an alibi. */}
              <div className="confront-col">
                <h4 className="confront-heading">What others have told you</h4>
                {otherTestimony.length === 0 ? (
                  <p className="muted small disabled-hint">
                    Nobody else has told you anything yet. Go and talk to them.
                  </p>
                ) : (
                  otherTestimony.map((t) => {
                    const who =
                      agents.find((a) => a.agent_id === t.speaker_agent_id)?.full_name.split(" ")[0] ??
                      "Someone";
                    return (
                      <label key={t.claim_id} className="confront-option">
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
                          <strong className="testimony-speaker">{who}:</strong> “{t.claim_text}”
                        </span>
                      </label>
                    );
                  })
                )}
              </div>
            </div>

            <div className="confront-actions">
              <button
                className="challenge-btn"
                disabled={
                  busy ||
                  !confrontClaim ||
                  (confrontEvidence.length === 0 && confrontTestimony.length === 0)
                }
                title={
                  !confrontClaim
                    ? "Pick a statement first"
                    : confrontEvidence.length === 0 && confrontTestimony.length === 0
                      ? "Pick the evidence — or the testimony — you think disproves it"
                      : undefined
                }
                onClick={putItToThem}
              >
                Put it to {firstName}
              </button>

              {contradictionCount > 0 && suggestions.length === 0 && (
                <button className="small-button hint-button" disabled={busy} onClick={revealHint}>
                  Stuck? Show me what contradicts what
                  {hintsTaken > 0 && (
                    <span className="muted small"> ({hintsTaken} hints taken)</span>
                  )}
                </button>
              )}
            </div>

            {suggestions.length > 0 && (
              <div className="hint-revealed">
                <p className="muted small">
                  Hint ({hintsTaken} taken this case) — the contradictions you are holding:
                </p>
                {suggestions.map((s) => (
                  <div
                    key={`${s.challenged_claim_id}:${s.evidence_clue_id}`}
                    className="challenge-card"
                  >
                    <div className="challenge-claim">
                      <span>“{s.claim_text}”</span>
                    </div>
                    <div className="challenge-evidence">
                      <span className="muted small">contradicted by</span> {s.evidence_title}
                    </div>
                    <button
                      className="challenge-btn"
                      disabled={busy}
                      onClick={() => runChallenge(s)}
                    >
                      Put it to {firstName}
                    </button>
                  </div>
                ))}
              </div>
            )}
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
        {/* Demeanour and pressure used to be shown here too, but the composure meter on the
            dossier is now the single, richer read of how a suspect is holding up — two copies
            only invited them to disagree on screen. */}
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
    agent.portrait_art?.deceased || agent.portrait_art?.calm || undefined;

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
              spriteAsset={postMortemPortrait ? undefined : agent.sprite_asset || undefined}
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
