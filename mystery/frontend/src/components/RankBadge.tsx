import { useState } from "react";
import { clearHistory, getHistory, getRank } from "../progress";
import { sfx } from "../sfx";

export default function RankBadge() {
  const [open, setOpen] = useState(false);
  const [, bump] = useState(0); // re-read storage after clearing
  const history = getHistory();
  const rank = getRank(history);

  return (
    <div className="rank-badge-wrap">
      <button
        className="tool-btn rank-badge"
        onClick={() => {
          sfx.click();
          setOpen(!open);
        }}
        title="Your detective record"
      >
        🕵️ {rank.title}
        {rank.played > 0 && (
          <span className="muted small">
            {" "}
            {rank.solved}/{rank.played}
          </span>
        )}
      </button>
      {open && (
        <div className="rank-popover panel">
          <h3>
            {rank.title} · {rank.solved} solved of {rank.played} closed
          </h3>
          {history.length === 0 && (
            <p className="muted small">No cases closed yet. Rank up by naming the right killer.</p>
          )}
          {[...history].reverse().map((h) => (
            <div
              key={`${h.case_id}:${h.accusation_id}:${h.completed_at}`}
              className="rank-history-row"
            >
              <span className={`correctness-chip ${h.killer_correct ? "yes" : "no"}`}>
                {h.killer_correct ? "✓" : "✕"}
              </span>
              <span className="rank-history-title">{h.case_title}</span>
              <span className="muted small">
                accused {h.accused_name || "—"} · {h.score}/100
                {h.duration_min != null && ` · ${h.duration_min} min`}
              </span>
            </div>
          ))}
          {history.length > 0 && (
            <button
              className="reset small-button"
              onClick={() => {
                sfx.click();
                if (confirm("Clear your detective record?")) {
                  clearHistory();
                  bump((n) => n + 1);
                }
              }}
            >
              Clear record
            </button>
          )}
        </div>
      )}
    </div>
  );
}
