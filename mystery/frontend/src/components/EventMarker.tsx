import type { MapEvent, VisualEventType } from "../types";

const MARKER_GLYPHS: Record<VisualEventType, { glyph: string; label: string }> = {
  agent_move: { glyph: "→", label: "Movement" },
  agent_present: { glyph: "•", label: "Activity" },
  object_marker: { glyph: "◆", label: "Object" },
  sound_marker: { glyph: "♪", label: "Sound" },
  body_discovery: { glyph: "☠", label: "Body discovered" },
  unknown_figure: { glyph: "?", label: "Unknown figure" },
  hidden_activity: { glyph: "▒", label: "Something unclear" },
  conversation_marker: { glyph: "💬", label: "Conversation" },
  clue_marker: { glyph: "★", label: "Clue" },
};

export function markerMeta(type: VisualEventType) {
  return MARKER_GLYPHS[type] ?? MARKER_GLYPHS.agent_present;
}

export default function EventMarker({
  event,
  x,
  y,
  zoomCompensation = 1,
  selected,
  onClick,
}: {
  event: MapEvent;
  x: number;
  y: number;
  zoomCompensation?: number;
  selected: boolean;
  onClick: () => void;
}) {
  const meta = markerMeta(event.visual_event_type);
  return (
    <button
      className={`map-marker type-${event.visual_event_type} ${selected ? "selected" : ""}`}
      style={{ left: x, top: y, transform: `translate(-50%, -50%) scale(${zoomCompensation})` }}
      title={`${event.time} — ${meta.label}`}
      onClick={onClick}
    >
      {meta.glyph}
    </button>
  );
}
