import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import type {
  AskResult,
  ChallengeResult,
  ChallengeSuggestion,
  CluePublic,
  QuestionType,
  SuspicionLevel,
  TranscriptMessage,
} from "../types";
import { ClueCard } from "./shared";

const SUSPICION_LEVELS: { value: SuspicionLevel; label: string }[] = [
  { value: "unknown", label: "Unmarked" },
  { value: "person_of_interest", label: "Person of interest" },
  { value: "suspect", label: "Suspect" },
  { value: "prime_suspect", label: "Prime suspect" },
  { value: "likely_innocent", label: "Likely innocent" },
  { value: "cleared", label: "Cleared" },
];

export default function Suspects({ focusAgentId }: { focusAgentId?: string | null }) {
  const { agents } = useWorld();
  const living = agents.filter((a) => !a.is_victim);
  const [selectedId, setSelectedId] = useState(
    (focusAgentId && living.some((a) => a.agent_id === focusAgentId)
      ? focusAgentId
      : living[0]?.agent_id) ?? ""
  );
  useEffect(() => {
    if (focusAgentId && living.some((a) => a.agent_id === focusAgentId)) {
      setSelectedId(focusAgentId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusAgentId]);
  const selected = living.find((a) => a.agent_id === selectedId);

  return (
    <div className="suspects">
      <div className="suspect-list panel">
        {living.map((a) => (
          <button
            key={a.agent_id}
            className={`suspect ${selectedId === a.agent_id ? "active" : ""}`}
            onClick={() => setSelectedId(a.agent_id)}
          >
            <span className="portrait">{a.portrait}</span>
            <span>
              <span className="suspect-name">{a.full_name}</span>
              <span className="muted small">{a.occupation}</span>
            </span>
          </button>
        ))}
      </div>
      {selected && <InterviewPanel key={selected.agent_id} agentId={selected.agent_id} />}
    </div>
  );
}

function InterviewPanel({ agentId }: { agentId: string }) {
  const { agents, locations, caseOverview } = useWorld();
  const agent = agents.find((a) => a.agent_id === agentId)!;
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [lastResult, setLastResult] = useState<AskResult | null>(null);
  const [clues, setClues] = useState<CluePublic[]>([]);
  const [suspicion, setSuspicion] = useState<SuspicionLevel>("unknown");
  const [suggestions, setSuggestions] = useState<ChallengeSuggestion[]>([]);
  const [lastChallenge, setLastChallenge] = useState<ChallengeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [timeRef, setTimeRef] = useState("07:50");
  const [clueTopic, setClueTopic] = useState("");
  const [locationTopic, setLocationTopic] = useState("");
  const [freeText, setFreeText] = useState("");
  const [fallbackMsg, setFallbackMsg] = useState<string | null>(null);

  const victimName = caseOverview.victim.full_name.split(" ")[0];
  const placeholders = [
    `Ask a question or accuse them of a contradiction...`,
    `"Where were you between ${caseOverview.murder_window[0]} and ${caseOverview.murder_window[1]}?"`,
    `"How did you know ${victimName}?"`,
    `"What were you doing at ${caseOverview.discovery_time}?"`,
    clues.length > 0 ? `"Can you explain this ${clues[0].title.toLowerCase()}?"` : `"Why should I believe you?"`,
  ];
  const [placeholderIdx, setPlaceholderIdx] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setPlaceholderIdx((i) => (i + 1) % placeholders.length);
    }, 4000);
    return () => clearInterval(timer);
  }, [placeholders.length]);

  const refresh = useCallback(() => {
    api.transcript(agentId).then(setTranscript);
    api.clues().then(setClues);
    api.challengeSuggestions(agentId).then(setSuggestions);
    api.board().then((b) => {
      const me = b.suspects.find((s) => s.agent.agent_id === agentId);
      if (me) setSuspicion(me.suspicion);
    });
  }, [agentId]);

  useEffect(refresh, [refresh]);

  const ask = async (
    questionType: QuestionType,
    extra: Record<string, string> = {}
  ) => {
    setBusy(true);
    setError(null);
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
    } finally {
      setBusy(false);
    }
  };

  const submitFreeText = async () => {
    if (!freeText.trim()) return;
    setBusy(true);
    setError(null);
    setFallbackMsg(null);
    try {
      const result = await api.freeTextAsk({
        agent_id: agentId,
        question: freeText.trim(),
      });
      if (result.answer) {
        setLastResult(result.answer);
        setLastChallenge(null);
      } else if (result.challenge_result) {
        setLastChallenge(result.challenge_result as ChallengeResult);
        setLastResult(null);
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
    alert("Noted.");
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
      refresh();
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="interview">
      <div className="interview-head">
        <div>
          <h2>
            {agent.portrait} {agent.full_name}
          </h2>
          <p className="muted">
            {agent.occupation}, {agent.age} · {agent.traits.join(", ")}
          </p>
          <p className="muted small">{agent.routine_summary}</p>
        </div>
        <label className="suspicion-select">
          Your judgement
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
      </div>

      <div className="transcript">
        {transcript.length === 0 && (
          <p className="muted">You haven't questioned {agent.full_name.split(" ")[0]} yet.</p>
        )}
        {transcript.map((m, i) => (
          <div key={i} className={`bubble ${m.speaker}`}>
            <p>
              {m.text}
              {m.deterministic_text && m.deterministic_text !== m.text && (
                <span className="muted small" title={m.deterministic_text} style={{ cursor: "help", marginLeft: "8px" }}>
                  ✨
                </span>
              )}
            </p>
            {m.revealed_clue_ids.length > 0 && (
              <p className="small badge new">revealed: {m.revealed_clue_ids.join(", ")}</p>
            )}
          </div>
        ))}
        {lastResult?.emotional_shift && (
          <p className="muted small emotional">
            {agent.full_name.split(" ")[0]} seems {lastResult.emotional_shift}.
          </p>
        )}
        {lastResult && lastResult.suggested_followups.length > 0 && (
          <div className="followups">
            {lastResult.suggested_followups.map((f, i) => (
              <span key={i} className="followup-chip">
                {f}
              </span>
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
            <span className="badge outcome">{lastChallenge.outcome.replace(/_/g, " ")}</span>
            {lastChallenge.emotional_shift && (
              <span className="muted small">
                {" "}
                {agent.full_name.split(" ")[0]} seems {lastChallenge.emotional_shift}.
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

      {error && <p className="error">{error}</p>}
      {fallbackMsg && <p className="error fallback-message">{fallbackMsg}</p>}

      {suggestions.length > 0 && (
        <div className="challenge-builder panel">
          <h3>Contradictions you can press</h3>
          <p className="muted small">
            You hold evidence that conflicts with what {agent.full_name.split(" ")[0]} has told
            you. Confront them.
          </p>
          {suggestions.map((s) => (
            <div key={`${s.challenged_claim_id}:${s.evidence_clue_id}`} className="challenge-card">
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
            className="flex-1"
            placeholder={placeholders[placeholderIdx]}
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
          <button disabled={busy || !freeText.trim()} onClick={submitFreeText}>
            Ask
          </button>
        </div>
        <div className="question-divider">
          <span className="muted small">or use predefined topics</span>
        </div>
        <div className="question-row">
          <button disabled={busy} onClick={() => ask("alibi")}>
            Ask alibi ({caseOverview.murder_window[0]}–{caseOverview.murder_window[1]})
          </button>
          <button disabled={busy} onClick={() => ask("last_seen_victim")}>
            Last saw {caseOverview.victim.full_name.split(" ")[0]}?
          </button>
          <button disabled={busy} onClick={() => ask("relationship")}>
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
          <button disabled={busy} onClick={() => ask("timeline", { time_reference: timeRef })}>
            What were you doing at {timeRef}?
          </button>
        </div>
        <div className="question-row">
          <select value={locationTopic} onChange={(e) => setLocationTopic(e.target.value)}>
            <option value="">Pick a place…</option>
            {locations.map((l) => (
              <option key={l.location_id} value={l.location_id}>
                {l.name}
              </option>
            ))}
          </select>
          <button
            disabled={busy || !locationTopic}
            onClick={() => ask("location", { topic_location_id: locationTopic })}
          >
            Ask about this place
          </button>
        </div>
        <div className="question-row">
          <select value={clueTopic} onChange={(e) => setClueTopic(e.target.value)}>
            <option value="">Pick discovered evidence…</option>
            {clues.map((c) => (
              <option key={c.clue_id} value={c.clue_id}>
                {c.title}
              </option>
            ))}
          </select>
          <button
            disabled={busy || !clueTopic}
            onClick={() => ask("evidence", { topic_clue_id: clueTopic })}
          >
            Confront with evidence
          </button>
        </div>
      </div>

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
  );
}
