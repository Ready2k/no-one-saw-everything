import { hhmm, minutes } from "../api";
import { sfx } from "../sfx";

export default function MapTimeline({
  startMin,
  endMin,
  current,
  playing,
  speed,
  murderWindow,
  onScrub,
  onTogglePlay,
  onSpeed,
}: {
  startMin: number;
  endMin: number;
  current: number;
  playing: boolean;
  speed: number;
  murderWindow: [string, string];
  onScrub: (t: number) => void;
  onTogglePlay: () => void;
  onSpeed: (s: number) => void;
}) {
  const span = endMin - startMin;
  // Playback advances in fractional minutes so figures can cross the map
  // smoothly. The controls remain minute-precise for clear detective notes.
  const displayedMinute = Math.floor(current);
  const winFrom = ((minutes(murderWindow[0]) - startMin) / span) * 100;
  const winTo = ((minutes(murderWindow[1]) - startMin) / span) * 100;

  return (
    <div className="map-timeline">
      <button
        className="map-play"
        onClick={() => {
          sfx.click();
          onTogglePlay();
        }}
      >
        {playing ? "⏸ Pause" : "▶ Play"}
      </button>
      <span className="map-clock">{hhmm(displayedMinute)}</span>
      <div className="map-scrub-wrap">
        <div
          className="map-window-band"
          style={{ left: `${winFrom}%`, width: `${winTo - winFrom}%` }}
          title={`Murder window ${murderWindow[0]}–${murderWindow[1]}`}
        />
        <input
          type="range"
          className="map-scrub"
          min={startMin}
          max={endMin}
          value={displayedMinute}
          onChange={(e) => onScrub(Number(e.target.value))}
        />
      </div>
      <select
        className="map-speed"
        value={speed}
        onChange={(e) => {
          sfx.click();
          onSpeed(Number(e.target.value));
        }}
        title="Replay speed"
      >
        <option value={0.5}>0.5×</option>
        <option value={1}>1×</option>
        <option value={2}>2×</option>
        <option value={4}>4×</option>
      </select>
    </div>
  );
}
