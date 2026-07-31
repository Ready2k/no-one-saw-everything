import { useCallback, useEffect, useRef, useState } from "react";
import { api, hhmm, minutes, timeOfDayLabel } from "../api";
import { useWorld } from "../App";
import type { CluePublic, EventPublic, LocationPublic } from "../types";
import LocationTransition, {
  shouldPlayLocationTransition,
} from "../components/LocationTransition";
import RewindIntro, {
  markRewindBriefingSeen,
  rewindBriefingSeen,
} from "./RewindIntro";
import { cinematicsEnabled } from "../settings";
import { audioManager } from "../audio";
import { sfx } from "../sfx";

export default function Rewind() {
  const { caseOverview, agents, locations, locationName, agentName } = useWorld();
  const period = timeOfDayLabel(caseOverview.sim_start_time);
  const start = minutes(caseOverview.sim_start_time);
  const end = minutes(caseOverview.discovery_time);
  const windowStart = minutes(caseOverview.murder_window[0]);
  const windowEnd = minutes(caseOverview.murder_window[1]);

  // A busy village is easier to read when the first replay starts where the
  // case says the crime happened. The complete period remains one click away.
  const [from, setFrom] = useState(windowStart);
  const [to, setTo] = useState(windowEnd);
  const [locationId, setLocationId] = useState("");
  const [agentId, setAgentId] = useState("");
  const [events, setEvents] = useState<EventPublic[]>([]);
  const [toast, setToast] = useState<CluePublic[] | null>(null);
  const [transitionLoc, setTransitionLoc] = useState<LocationPublic | null>(null);
  // The cinematic briefing plays the first time this view opens per case.
  const [showBriefing, setShowBriefing] = useState(
    () => cinematicsEnabled() && !rewindBriefingSeen(caseOverview.case_id)
  );

  const toastTimer = useRef<number>(0);

  useEffect(() => {
    return () => window.clearTimeout(toastTimer.current);
  }, []);

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
    sfx.pinPush();
    try {
      const result = await api.pinEvent(eventId);
      if (result.new_clues.length) {
        audioManager.playStinger("clue_discovered");
        setToast(result.new_clues);
        window.clearTimeout(toastTimer.current);
        toastTimer.current = window.setTimeout(() => setToast(null), 6000);
      }
      refresh();
    } catch (e) {
      console.error("Failed to pin event:", e);
    }
  };

  // Position (%) of a minute value along the full rewind range.
  const pct = (v: number) => ((v - start) / Math.max(1, end - start)) * 100;

  const focusMurderWindow = () => {
    setFrom(windowStart);
    setTo(windowEnd);
  };
  const focusFullPeriod = () => {
    setFrom(start);
    setTo(end);
  };
  const windowFocused = from === windowStart && to === windowEnd;
  const fullFocused = from === start && to === end;

  if (showBriefing) {
    return (
      <RewindIntro
        onDone={() => {
          // Mark before unmounting the overlay. This makes every completion
          // route (Skip, Escape, or the final CTA) idempotent and guarantees
          // a remount remains in the active Rewind view.
          markRewindBriefingSeen(caseOverview.case_id);
          setShowBriefing(false);
        }}
      />
    );
  }

  return (
    <div className="rewind">
      {transitionLoc && (
        <LocationTransition
          location={transitionLoc}
          onDone={() => setTransitionLoc(null)}
        />
      )}
      <div className="rewind-controls panel">
        <div className="time-strip" aria-hidden>
          <div
            className="time-strip-selection"
            style={{ left: `${pct(from)}%`, width: `${pct(to) - pct(from)}%` }}
          />
          <div
            className="time-strip-window"
            style={{
              left: `${pct(windowStart)}%`,
              width: `${pct(windowEnd) - pct(windowStart)}%`,
            }}
            title={`Estimated murder window ${caseOverview.murder_window[0]} – ${caseOverview.murder_window[1]}`}
          />
          <span className="time-strip-label start">{caseOverview.sim_start_time}</span>
          <span className="time-strip-label end">{caseOverview.discovery_time}</span>
        </div>
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
          <button
            className={windowFocused ? "chip danger active" : "chip danger"}
            onClick={focusMurderWindow}
            title="Zoom the replay to the estimated murder window"
          >
            ◉ Murder window {caseOverview.murder_window[0]}–{caseOverview.murder_window[1]}
          </button>
          <button
            className={fullFocused ? "chip active" : "chip"}
            onClick={focusFullPeriod}
            title={`Replay the whole ${period}`}
          >
            Full {period}
          </button>
          <select
            value={locationId}
            onChange={(e) => {
              const id = e.target.value;
              setLocationId(id);
              const loc = locations.find((l) => l.location_id === id);
              if (loc && shouldPlayLocationTransition(id)) setTransitionLoc(loc);
            }}
          >
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
        {!windowFocused && (
          <p className="rewind-focus-hint">
            Start with the shaded murder window, then widen the replay when a lead needs context.
          </p>
        )}
      </div>

      {toast && (
        <div className="clue-toast">
          <div className="clue-toast-head">🔎 Evidence uncovered</div>
          {toast.map((c) => (
            <div key={c.clue_id}>
              <strong>{c.title}</strong>
            </div>
          ))}
        </div>
      )}

      <div className="event-feed">
        {events.length === 0 && (
          <p className="muted">Nothing visible in this window. Widen the filters.</p>
        )}
        {events.map((e, i) => {
          const inWindow = minutes(e.time) >= windowStart && minutes(e.time) <= windowEnd;
          return (
            <div
              key={e.event_id}
              className={`event event-appear ${e.visibility} ${inWindow ? "murder-window" : ""}`}
              style={{ animationDelay: `${Math.min(i, 12) * 45}ms` }}
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
