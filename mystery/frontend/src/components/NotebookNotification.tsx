import { useEffect, useRef, useState } from "react";

interface NotebookNotificationProps {
  /** The note text that was just saved */
  noteText: string;
  /** Called when the animation finishes */
  onDone: () => void;
}

/**
 * A pocket-sized detective notebook animation.
 *
 * Sequence:
 *   1. Small notebook flips open (top-bound, cover lifts up)
 *   2. Pages flip past showing old scribbled notes
 *   3. A pencil enters and "writes" the new note
 *   4. "Noted." stamp appears, page turns, notebook closes
 */
export default function NotebookNotification({
  noteText,
  onDone,
}: NotebookNotificationProps) {
  const [phase, setPhase] = useState<
    "enter" | "open" | "flip" | "write" | "done" | "exit"
  >("enter");
  const pencilPathRef = useRef<SVGPathElement | null>(null);

  // Pre-baked "old notes" that flicker past during the flip phase
  const oldNotes = [
    "Check alibi — said kitchen\nbut found at stables 07:52?",
    "Witness saw argument\n\"Voices raised\" — 07:40",
  ];

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    timers.push(setTimeout(() => setPhase("open"), 400));
    timers.push(setTimeout(() => setPhase("flip"), 1400));
    timers.push(setTimeout(() => setPhase("write"), 3200));
    timers.push(setTimeout(() => setPhase("done"), 5800));
    timers.push(setTimeout(() => setPhase("exit"), 7200));
    timers.push(setTimeout(() => onDone(), 8000));
    return () => timers.forEach(clearTimeout);
  }, [onDone]);

  // Animate the pencil SVG stroke during write phase
  useEffect(() => {
    if (phase === "write" && pencilPathRef.current) {
      const path = pencilPathRef.current;
      const len = path.getTotalLength();
      path.style.strokeDasharray = `${len}`;
      path.style.strokeDashoffset = `${len}`;
      // eslint-disable-next-line @typescript-eslint/no-unused-expressions
      path.getBoundingClientRect();
      path.style.transition = "stroke-dashoffset 2.2s ease-in-out";
      path.style.strokeDashoffset = "0";
    }
  }, [phase]);

  return (
    <div
      className={`nb-overlay phase-${phase}`}
      onClick={() => {
        setPhase("exit");
        setTimeout(onDone, 500);
      }}
    >
      <div className="nb-container">
        {/* The pocket notebook */}
        <div className="nb-book">
          {/* Spiral binding dots along the top */}
          <div className="nb-spirals" aria-hidden="true">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="nb-spiral-ring" />
            ))}
          </div>

          {/* The page — only one visible at a time */}
          <div className="nb-page">
            <div className="nb-page-lines" />

            {/* Flip pages that animate across */}
            {phase === "flip" && (
              <>
                <div className="nb-flip nb-flip-1">
                  <p className="nb-scribble">{oldNotes[0]}</p>
                </div>
                <div className="nb-flip nb-flip-2">
                  <p className="nb-scribble">{oldNotes[1]}</p>
                </div>
              </>
            )}

            {/* Old scribble visible on the page underneath flips */}
            {(phase === "flip") && (
              <div className="nb-old-notes">
                <p className="nb-scribble">Broken glass near study — prints?</p>
              </div>
            )}

            {/* The actual note being "written" */}
            {(phase === "write" || phase === "done") && (
              <div className="nb-writing">
                <p className="nb-written">{noteText.slice(0, 100)}{noteText.length > 100 ? "…" : ""}</p>
              </div>
            )}

            {/* "Noted." stamp */}
            {phase === "done" && (
              <div className="nb-stamp">Noted.</div>
            )}

            {/* Final page turn */}
            {phase === "done" && <div className="nb-final-flip" />}
          </div>

          {/* Cover — flips up from the top */}
          <div className="nb-cover">
            <div className="nb-cover-front">
              <div className="nb-cover-badge">🔍</div>
              <div className="nb-cover-title">Detective's<br/>Notebook</div>
            </div>
          </div>
        </div>

        {/* Pencil */}
        {(phase === "write" || phase === "done") && (
          <div className="nb-pencil">
            <svg viewBox="0 0 20 100" className="nb-pencil-svg" aria-hidden="true">
              <rect x="5" y="0" width="10" height="78" rx="1.5" fill="#d4a843" />
              <rect x="5" y="0" width="10" height="10" rx="1.5" fill="#c0392b" />
              <rect x="5" y="10" width="10" height="3" fill="#999" />
              <polygon points="5,78 15,78 10,100" fill="#f5deb3" />
              <polygon points="8,92 12,92 10,100" fill="#333" />
            </svg>
          </div>
        )}

        {/* Writing stroke path */}
        {phase === "write" && (
          <svg className="nb-stroke-svg" viewBox="0 0 160 140" aria-hidden="true">
            <path
              ref={pencilPathRef}
              d="M10,20 C35,17 55,23 85,20 S120,17 150,21 M10,42 C40,39 70,45 100,42 S130,39 150,43 M10,64 C30,61 60,67 90,64 S120,61 150,65 M10,86 C40,83 75,89 110,86 S140,83 150,87"
              fill="none"
              stroke="rgba(216, 162, 74, 0.25)"
              strokeWidth="1.2"
              strokeLinecap="round"
            />
          </svg>
        )}
      </div>
    </div>
  );
}
