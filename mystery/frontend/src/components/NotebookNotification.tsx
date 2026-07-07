import { useEffect, useRef, useState } from "react";
import { api } from "../api";

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

  // Pre-baked/dynamic notes grouped by page
  const [existingNotes, setExistingNotes] = useState<string[][]>([
    ["Check alibi — said kitchen\nbut found at stables 07:52?", "Broken glass near study — prints?"],
    ["Witness saw argument\n\"Voices raised\" — 07:40", "Marcus's safe code: 4-8-1-5?"],
    ["Clara Wells routine:\nOpens cafe at 08:00 sharp."]
  ]);

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    timers.push(setTimeout(() => setPhase("open"), 600));
    timers.push(setTimeout(() => setPhase("flip"), 2200));
    timers.push(setTimeout(() => setPhase("write"), 4800));
    timers.push(setTimeout(() => setPhase("done"), 8500));
    timers.push(setTimeout(() => setPhase("exit"), 13500));
    timers.push(setTimeout(() => onDone(), 14500));
    return () => timers.forEach(clearTimeout);
  }, [onDone]);



  // Fetch and prepare notes
  useEffect(() => {
    api.notes()
      .then((notes) => {
        // Filter out event notes, and filter out the current note we are adding
        const relevantNotes = notes.filter(n => {
          if (n.note_type === "event") return false;

          const cleanTitle = n.title.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
          const cleanCurrent = noteText.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
          
          const isCurrent = cleanCurrent.includes(cleanTitle) || cleanTitle.includes(cleanCurrent);
          return !isCurrent;
        });

        // Reverse to show the most recent notes first in the flip animation
        relevantNotes.reverse();

        // Clean up note titles
        const cleaned = relevantNotes.map(n => {
          let text = n.title;
          text = text.replace(/^([A-Za-z]+)\s+[A-Za-z]+:/, "$1:"); // E.g., "Clara Wells:" -> "Clara:"
          text = text.replace(/✨/g, "").trim();
          
          if (text.length > 50) {
            text = text.slice(0, 47) + "…";
          }
          return text;
        });

        // Group into pages of up to 2 notes
        const pages: string[][] = [];
        for (let i = 0; i < cleaned.length; i += 2) {
          pages.push(cleaned.slice(i, i + 2));
        }

        // Pre-baked notes to backfill
        const defaults = [
          ["Check alibi — said kitchen\nbut found at stables 07:52?", "Broken glass near study — prints?"],
          ["Witness saw argument\n\"Voices raised\" — 07:40", "Marcus's safe code: 4-8-1-5?"],
          ["Clara Wells routine:\nOpens cafe at 08:00 sharp."]
        ];

        // Ensure we have at least 3 pages of previous notes
        while (pages.length < 3) {
          const defPage = defaults[pages.length] || [];
          pages.push(defPage);
        }

        // Limit the active page (index 2) to at most 1 note to guarantee room for writing
        if (pages[2] && pages[2].length > 1) {
          pages[2] = [pages[2][0]!];
        }

        setExistingNotes(pages);
      })
      .catch((err) => {
        console.error("Error fetching notes for animation:", err);
      });
  }, [noteText]);

  // Animate the pencil SVG stroke during write phase
  useEffect(() => {
    if (phase === "write" && pencilPathRef.current) {
      const path = pencilPathRef.current;
      const len = path.getTotalLength();
      path.style.strokeDasharray = `${len}`;
      path.style.strokeDashoffset = `${len}`;
      // eslint-disable-next-line @typescript-eslint/no-unused-expressions
      path.getBoundingClientRect();
      path.style.transition = "stroke-dashoffset 3.2s ease-in-out";
      path.style.strokeDashoffset = "0";
    }
  }, [phase]);

  const hasExistingOnActivePage = existingNotes[2] && existingNotes[2].length > 0;

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
                  {existingNotes[0]?.map((note, idx) => (
                    <p key={idx} className="nb-scribble">{note}</p>
                  ))}
                </div>
                <div className="nb-flip nb-flip-2">
                  {existingNotes[1]?.map((note, idx) => (
                    <p key={idx} className="nb-scribble">{note}</p>
                  ))}
                </div>
              </>
            )}

            {/* Old scribble visible on the page underneath flips (Page 3) */}
            {(phase === "flip" || phase === "write" || phase === "done") && hasExistingOnActivePage && (
              <div className="nb-old-notes">
                {existingNotes[2]?.map((note, idx) => (
                  <p key={idx} className="nb-scribble">{note}</p>
                ))}
              </div>
            )}

            {/* The actual note being "written" */}
            {(phase === "write" || phase === "done") && (
              <div className={`nb-writing ${hasExistingOnActivePage ? "has-existing" : ""}`}>
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
          <div className={`nb-pencil ${hasExistingOnActivePage ? "has-existing" : ""}`}>
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
          <svg className={`nb-stroke-svg ${hasExistingOnActivePage ? "has-existing" : ""}`} viewBox="0 0 160 140" aria-hidden="true">
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
