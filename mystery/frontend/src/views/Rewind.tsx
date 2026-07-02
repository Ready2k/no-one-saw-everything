import { useCallback, useEffect, useState } from "react";
import { api, hhmm, minutes } from "../api";
import { useWorld } from "../App";
import type { CluePublic, EventPublic } from "../types";

export default function Rewind() {
  const { caseOverview, agents, locations, locationName, agentName } = useWorld();
  const start = minutes(caseOverview.sim_start_time);
  const end = minutes(caseOverview.discovery_time);

  const [from, setFrom] = useState(start);
  const [to, setTo] = useState(end);
  const [locationId, setLocationId] = useState("");
  const [agentId, setAgentId] = useState("");
  const [events, setEvents] = useState<EventPublic[]>([]);
  const [toast, setToast] = useState<CluePublic[] | null>(null);

  const refresh = useCallback(() => {
    api
      .events({
        time_from: hhmm(from),
        time_to: hhmm(to),
        location_id: locationId || undefined,
        agent_id: agentId || undefined,
      })
      .then(setEvents)
      .catch(console.error);
  }, [from, to, locationId, agentId]);

  useEffect(refresh, [refresh]);

  const pin = async (eventId: string) => {
    const result = await api.pinEvent(eventId);
    if (result.new_clues.length) {
      setToast(result.new_clues);
      setTimeout(() => setToast(null), 6000);
    }
    refresh();
  };

  const windowStart = minutes(caseOverview.murder_window[0]);
  const windowEnd = minutes(caseOverview.murder_window[1]);

  return (
    <div className="rewind">
      <div className="rewind-controls panel">
        <div className="range-row">
          <label>
            From <strong>{hhmm(from)}</strong>
            <input
              type="range"
              min={start}
              max={end}
              value={from}
              onChange={(e) => {
                const v = Number(e.target.value);
                setFrom(v);
                if (v > to) setTo(v);
              }}
            />
          </label>
          <label>
            To <strong>{hhmm(to)}</strong>
            <input
              type="range"
              min={start}
              max={end}
              value={to}
              onChange={(e) => {
                const v = Number(e.target.value);
                setTo(v);
                if (v < from) setFrom(v);
              }}
            />
          </label>
        </div>
        <div className="filter-row">
          <select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
            <option value="">All locations</option>
            {locations.map((l) => (
              <option key={l.location_id} value={l.location_id}>
                {l.name}
              </option>
            ))}
          </select>
          <select value={agentId} onChange={(e) => setAgentId(e.target.value)}>
            <option value="">Everyone</option>
            {agents.map((a) => (
              <option key={a.agent_id} value={a.agent_id}>
                {a.full_name}
                {a.is_victim ? " (victim)" : ""}
              </option>
            ))}
          </select>
          {agentId && (
            <span className="muted small">
              Following only shows moments where they were publicly identifiable.
            </span>
          )}
        </div>
      </div>

      {toast && (
        <div className="clue-toast">
          {toast.map((c) => (
            <div key={c.clue_id}>
              <strong>New clue:</strong> {c.title}
            </div>
          ))}
        </div>
      )}

      <div className="event-feed">
        {events.length === 0 && (
          <p className="muted">Nothing visible in this window. Widen the filters.</p>
        )}
        {events.map((e) => {
          const inWindow = minutes(e.time) >= windowStart && minutes(e.time) <= windowEnd;
          return (
            <div
              key={e.event_id}
              className={`event ${e.visibility} ${inWindow ? "murder-window" : ""}`}
            >
              <div className="event-time">{e.time}</div>
              <div className="event-body">
                <div className="event-desc">{e.description}</div>
                <div className="event-meta">
                  <span>{locationName(e.location_id)}</span>
                  {e.agent_ids.length > 0 && (
                    <span>{e.agent_ids.map(agentName).join(", ")}</span>
                  )}
                  {e.visibility !== "public" && (
                    <span className="badge ambiguous">
                      {e.visibility === "public_partial" ? "unclear" : "obscured"}
                    </span>
                  )}
                  {inWindow && <span className="badge window">murder window</span>}
                </div>
              </div>
              <button
                className={e.pinned ? "pin pinned" : "pin"}
                onClick={() => pin(e.event_id)}
                disabled={e.pinned}
                title="Pin to case board"
              >
                {e.pinned ? "Pinned" : "Pin"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
