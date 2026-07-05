import { useState, useEffect } from "react";
import { api } from "../api";
import { useWorld } from "../App";
import { shareText } from "../progress";
import type { AccusationResult, Feedback, Config } from "../types";

export default function AccusationBreakdown({
  result,
  onPlayAgain,
}: {
  result: AccusationResult;
  onPlayAgain: () => void;
}) {
  const { caseOverview } = useWorld();
  const [config, setConfig] = useState<Config | null>(null);
  const [feedback, setFeedback] = useState<Partial<Feedback>>({});
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [feedbackSaving, setFeedbackSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [shareFallback, setShareFallback] = useState<string | null>(null);

  const copyShareCard = async () => {
    const text = shareText(result, caseOverview.title);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Clipboard unavailable (permissions/insecure context): show the text
      // so the player can copy it manually.
      setShareFallback(text);
    }
  };

  useEffect(() => {
    api.getConfig().then(setConfig).catch(console.error);
  }, []);

  const submitFeedbackForm = async () => {
    setFeedbackSaving(true);
    try {
      await api.submitFeedback(feedback as Feedback);
      setFeedbackSubmitted(true);
    } catch (e) {
      console.error(e);
      alert("Failed to submit feedback");
    } finally {
      setFeedbackSaving(false);
    }
  };

  const band =
    result.score >= 90
      ? "clean"
      : result.score >= 70
      ? "good"
      : result.score >= 50
      ? "partial"
      : result.score >= 20
      ? "weak"
      : "poor";

  const correctness: [string, boolean][] = [
    ["Killer", result.killer_correct],
    ["Motive", result.motive_correct],
    ["Method", result.method_correct],
    ["Opportunity", result.opportunity_correct],
  ];

  return (
    <div className="reveal">
      <div className={`verdict-card band-${band}`}>
        <div className="score">
          {result.score} <span className="detective-rating">({result.detective_rating} Rating)</span>
        </div>
        <h1>{result.verdict}</h1>
        <div className="correctness">
          {correctness.map(([label, ok]) => (
            <span key={label} className={`correctness-chip ${ok ? "yes" : "no"}`}>
              {ok ? "✓" : "✕"} {label}
            </span>
          ))}
        </div>
        <p className="explanation">{result.explanation}</p>
      </div>

      <div className="reveal-grid" style={!result.killer_correct ? { gridTemplateColumns: "1fr" } : undefined}>
        <div className="reveal-col panel">
          {result.killer_correct && (
            <>
              <h3>The truth</h3>
              <p>
                <strong>Killer:</strong> {result.true_killer_name}
              </p>
              <p>
                <strong>Motive:</strong> {result.true_motive}
              </p>
              <p>
                <strong>Method:</strong> {result.true_method}
              </p>
            </>
          )}

          <h3>Evidence</h3>
          <p className="muted small">
            Evidence strength {Math.round(result.evidence_score * 100)}%
          </p>
          {result.player_evidence_used.length > 0 && (
            <>
              <p className="small found-label">Evidence you cited</p>
              {result.player_evidence_used.map((c) => (
                <p key={c} className="small clue-found">
                  • {c}
                </p>
              ))}
            </>
          )}
          {result.key_clues_found.length > 0 && (
            <>
              <p className="small found-label">Key clues you found</p>
              {result.key_clues_found.map((c) => (
                <p key={c} className="small clue-found">
                  ✓ {c}
                </p>
              ))}
            </>
          )}
          {result.key_clues_missed.length > 0 && (
            <>
              <p className="small missed-label">Key clues you never found</p>
              {result.key_clues_missed.map((c) => (
                <p key={c} className="small clue-missed">
                  ✕ {c}
                </p>
              ))}
            </>
          )}
          {result.false_assumptions.length > 0 && (
            <>
              <p className="small missed-label">False assumptions</p>
              {result.false_assumptions.map((f, i) => (
                <p key={i} className="small clue-missed">
                  • {f}
                </p>
              ))}
            </>
          )}
        </div>

        {result.killer_correct && (
          <div className="reveal-col panel">
            <h3>What really happened</h3>
            <div className="truth-timeline">
              {result.true_timeline.map((e, i) => (
                <div key={i} className="truth-event">
                  <span className="event-time">{e.time}</span>
                  <span>
                    {e.description}
                    <span className="muted small"> · {e.location_name}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {result.killer_correct && (
          <div className="reveal-col panel">
            <h3>Why the others were innocent</h3>
            {result.red_herring_explanations.map((h) => (
              <div key={h.agent_id} className="herring-card">
                <strong>{h.agent_name}</strong>
                <p className="small">
                  <em>Looked guilty:</em> {h.looked_suspicious_because}
                </p>
                <p className="small">
                  <em>But:</em> {h.actually_innocent_because}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {config?.playtest_mode && !feedbackSubmitted && (
        <div className="panel" style={{ marginTop: "1rem", border: "1px solid #0f0" }}>
          <h3 style={{ color: "#0f0" }}>🧪 Playtest Feedback</h3>
          <p className="small muted">
            Please fill this out before closing the game!
          </p>
          <div style={{ display: "grid", gap: "1rem", marginTop: "1rem" }}>
            <label className="field">
              <span>Did you understand the goal of the game?</span>
              <select onChange={(e) => setFeedback({ ...feedback, understood_goal: e.target.value as any })}>
                <option value="">Choose...</option>
                <option value="yes">Yes</option>
                <option value="mostly">Mostly</option>
                <option value="no">No</option>
              </select>
            </label>
            <label className="field">
              <span>Did rewinding time make sense?</span>
              <select onChange={(e) => setFeedback({ ...feedback, rewind_made_sense: e.target.value as any })}>
                <option value="">Choose...</option>
                <option value="yes">Yes</option>
                <option value="mostly">Mostly</option>
                <option value="no">No</option>
              </select>
            </label>
            <label className="field">
              <span>How helpful were the hints?</span>
              <select onChange={(e) => setFeedback({ ...feedback, hints_helpfulness: e.target.value as any })}>
                <option value="">Choose...</option>
                <option value="too_little">Not enough</option>
                <option value="about_right">About right</option>
                <option value="too_much">Too much</option>
                <option value="spoiled">Spoiled the answer</option>
              </select>
            </label>
            <label className="field">
              <span>Difficulty?</span>
              <select onChange={(e) => setFeedback({ ...feedback, difficulty: e.target.value as any })}>
                <option value="">Choose...</option>
                <option value="too_easy">Too easy</option>
                <option value="about_right">About right</option>
                <option value="too_hard">Too hard</option>
                <option value="confusing">Confusing</option>
              </select>
            </label>
            <label className="field">
              <span>Was the final reveal fair?</span>
              <select onChange={(e) => setFeedback({ ...feedback, final_reveal_fair: e.target.value as any })}>
                <option value="">Choose...</option>
                <option value="yes">Yes</option>
                <option value="mostly">Mostly</option>
                <option value="no">No</option>
              </select>
            </label>
            <label className="field">
              <span>Enjoyment Score (1-5)</span>
              <input type="number" min="1" max="5" onChange={(e) => setFeedback({ ...feedback, enjoyment_score: parseInt(e.target.value) })} />
            </label>
            <label className="field">
              <span>Confidence Score in your accusation (1-5)</span>
              <input type="number" min="1" max="5" onChange={(e) => setFeedback({ ...feedback, confidence_score: parseInt(e.target.value) })} />
            </label>
            <label className="field">
              <span>Did you suspect the killer before the reveal?</span>
              <input type="text" onChange={(e) => setFeedback({ ...feedback, suspected_before_reveal: e.target.value })} />
            </label>
            <label className="field">
              <span>Most confusing part?</span>
              <textarea onChange={(e) => setFeedback({ ...feedback, most_confusing_part: e.target.value })} />
            </label>
            <label className="field">
              <span>Best part?</span>
              <textarea onChange={(e) => setFeedback({ ...feedback, best_part: e.target.value })} />
            </label>
            <label className="field">
              <span>Worst part?</span>
              <textarea onChange={(e) => setFeedback({ ...feedback, worst_part: e.target.value })} />
            </label>
            <label className="field">
              <span>Any clues that felt unfair?</span>
              <textarea onChange={(e) => setFeedback({ ...feedback, clues_that_felt_unfair: e.target.value })} />
            </label>
            <label className="field">
              <span>Any other feedback?</span>
              <textarea onChange={(e) => setFeedback({ ...feedback, free_text: e.target.value })} />
            </label>
            <button
              className="primary"
              onClick={submitFeedbackForm}
              disabled={feedbackSaving}
            >
              Submit Feedback
            </button>
          </div>
        </div>
      )}

      {feedbackSubmitted && (
        <div className="panel" style={{ marginTop: "1rem", border: "1px solid #0f0", color: "#0f0" }}>
          Thank you for your feedback! It has been saved.
        </div>
      )}

      <div className="reveal-actions">
        <button className="primary" onClick={onPlayAgain}>
          Play again
        </button>
        <button onClick={copyShareCard}>
          {copied ? "Copied ✓" : "Copy case-closed card"}
        </button>
      </div>
      {shareFallback && (
        <pre className="share-card panel" onClick={() => setShareFallback(null)}>
          {shareFallback}
        </pre>
      )}
    </div>
  );
}
