import { useMemo, useState } from "react";
import type { ClueHotspot } from "../types";
import { sfx } from "../sfx";

type Camera = "wide" | "counter" | "service";
type Tool = "torch" | "lens" | "uv";

const CAMERAS: { id: Camera; label: string; detail: string }[] = [
  { id: "wide", label: "Front room", detail: "Establish the room and routes through it." },
  { id: "counter", label: "Counter", detail: "Till, cups, receipts and the worn counter edge." },
  { id: "service", label: "Service door", detail: "Kitchen threshold and the back-of-house route." },
];

const TOOLS: { id: Tool; label: string; detail: string }[] = [
  { id: "torch", label: "Torch", detail: "Raking light catches surface disturbance." },
  { id: "lens", label: "Hand lens", detail: "Close optical inspection." },
  { id: "uv", label: "UV lamp", detail: "Look for what ordinary light misses." },
];

export function HobbsCafeScene({
  imageUrl,
  hiddenClues,
  onDiscover,
}: {
  imageUrl?: string;
  hiddenClues: ClueHotspot[];
  onDiscover: (clueId: string) => void;
}) {
  const [camera, setCamera] = useState<Camera>("wide");
  const [tool, setTool] = useState<Tool>("torch");
  const [examining, setExamining] = useState<string | null>(null);
  const clueForZone = (zone: string | null) => hiddenClues.find((clue) => {
    const title = clue.title.toLowerCase();
    if (zone === "Counter & till") return title.includes("till") || title.includes("receipt") || title.includes("ledger");
    if (zone === "Floorboards") return title.includes("foot") || title.includes("mud") || title.includes("trace");
    return title.includes("door") || title.includes("coat");
  });
  const nextClue = clueForZone(examining);
  // The API assigns one forensic method per clue.  The Café calls raking
  // light a torch, but it is the same examination method.
  const requiredTool: Tool | null = nextClue
    ? (nextClue.search_tool === "raking" ? "torch" : nextClue.search_tool || "lens")
    : null;
  const toolDetail = TOOLS.find((item) => item.id === tool)?.detail;
  const cameraDetail = CAMERAS.find((item) => item.id === camera)?.detail;
  const cluePrompt = useMemo(() => {
    if (!nextClue) return "Scene cleared — catalogue the evidence already collected.";
    if (tool !== requiredTool) return `Nothing conclusive with the ${TOOLS.find((item) => item.id === tool)?.label.toLowerCase()}. Try the ${TOOLS.find((item) => item.id === requiredTool)?.label.toLowerCase()}.`;
    if (tool === "uv") return "A faint irregularity responds at the edge of the light.";
    if (tool === "lens") return "A detail warrants a closer look.";
    return "Low-angle light makes a small disturbance stand out.";
  }, [nextClue, tool]);

  const examine = (zone: string) => {
    sfx.lensAdjust();
    setExamining(zone);
  };

  return (
    <section className={`cafe-scene tool-${tool} camera-${camera}`} aria-label="Hobbs Cafe forensic scene">
      <div className="cafe-scene-head">
        <div>
          <span className="cafe-kicker">Scene examination · Hobbs Cafe</span>
          <p>{cameraDetail}</p>
        </div>
        <span className="cafe-scene-status">{hiddenClues.length} lead{hiddenClues.length === 1 ? "" : "s"} unresolved</span>
      </div>

      <div className="cafe-scene-stage">
        <div className="cafe-scene-art" style={imageUrl ? { backgroundImage: `url(${imageUrl})` } : undefined} aria-hidden="true" />
        <div className="cafe-depth cafe-depth-foreground" aria-hidden="true" />
        <div className="cafe-depth cafe-depth-light" aria-hidden="true" />
        <div className="cafe-reticle" aria-hidden="true" />
        <div className={`cafe-tool-in-hand cafe-tool-${tool}`} aria-hidden="true">
          <span className="cafe-tool-beam" />
          <span className="cafe-tool-body" />
        </div>
        <div className="cafe-hotspots">
          <button className="cafe-zone zone-counter" onClick={() => examine("Counter & till")}>
            <span className="cafe-zone-label">Inspect counter</span>
          </button>
          <button className="cafe-zone zone-floor" onClick={() => examine("Floorboards")}>
            <span className="cafe-zone-label">Examine floor</span>
          </button>
          <button className="cafe-zone zone-service" onClick={() => examine("Service doorway")}>
            <span className="cafe-zone-label">Check service route</span>
          </button>
        </div>
        {tool === "uv" && <div className="uv-wash" aria-hidden="true" />}
      </div>

      <div className="cafe-scene-controls">
        <div className="cafe-control-group">
          <span>Camera</span>
          {CAMERAS.map((item) => <button key={item.id} className={camera === item.id ? "active" : ""} onClick={() => { setCamera(item.id); sfx.lensAdjust(); }}>{item.label}</button>)}
        </div>
        <div className="cafe-control-group">
          <span>Forensic kit</span>
          {TOOLS.map((item) => <button key={item.id} className={tool === item.id ? "active" : ""} onClick={() => { setTool(item.id); sfx.lensAdjust(); }}>{item.label}</button>)}
        </div>
      </div>

      <div className="cafe-examination panel">
        <div>
          <span className="cafe-kicker">{examining ? examining : "Select a surface"}</span>
          <p>{examining ? cluePrompt : toolDetail}</p>
        </div>
        {examining && nextClue && tool === requiredTool && (
          <button className="cafe-collect" onClick={() => { onDiscover(nextClue.clue_id); setExamining(null); }}>
            Document & collect
          </button>
        )}
      </div>
    </section>
  );
}
