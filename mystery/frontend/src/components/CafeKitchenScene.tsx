import { useState } from "react";
import type { ClueHotspot } from "../types";
import { sfx } from "../sfx";

type Tool = "raking" | "swab" | "uv";
const TOOLS: { id: Tool; label: string; readout: string }[] = [
  { id: "raking", label: "Raking light", readout: "Skimming light across tile and steel." },
  { id: "swab", label: "Trace swab", readout: "Collect a controlled surface sample." },
  { id: "uv", label: "UV lamp", readout: "Search for cleaned or transferred residue." },
];

export function CafeKitchenScene({ imageUrl, hiddenClues, onDiscover }: { imageUrl?: string; hiddenClues: ClueHotspot[]; onDiscover: (clueId: string) => void }) {
  const [tool, setTool] = useState<Tool>("raking");
  const [area, setArea] = useState<string | null>(null);
  const requiredTool = (clue: ClueHotspot): Tool => {
    const title = clue.title.toLowerCase();
    if (title.includes("weight") || title.includes("damp") || title.includes("smudge") || title.includes("blood")) return "swab";
    return "uv";
  };
  const clueForArea = (selected: string | null) => hiddenClues.find((clue) => {
    const title = clue.title.toLowerCase();
    if (selected === "Mop bucket") return title.includes("bucket") || title.includes("weight");
    if (selected === "Sink & draining board") return title.includes("coat") || title.includes("damp") || title.includes("smudge");
    if (selected === "Tile floor") return title.includes("foot") || title.includes("mud") || title.includes("trace");
    return false;
  });
  const nextClue = clueForArea(area);
  const needsTool = nextClue ? requiredTool(nextClue) : null;
  const selectArea = (name: string) => { setArea(name); sfx.lensAdjust(); };
  const readout = !area
    ? TOOLS.find((item) => item.id === tool)?.readout
    : nextClue && tool !== needsTool ? `No recoverable lead with ${TOOLS.find((item) => item.id === tool)?.label.toLowerCase()}. Try ${TOOLS.find((item) => item.id === needsTool)?.label.toLowerCase()}.`
    : tool === "uv" ? "A weak response catches at the edge of the illuminated surface."
    : tool === "swab" ? "The surface can be documented before a sample is taken."
    : "The changed angle reveals a break in the ordinary pattern of wear.";

  return <section className={`kitchen-scene tool-${tool} ${area === "Sink & draining board" ? "view-sink" : area === "Mop bucket" ? "view-mop" : area === "Storage threshold" ? "view-threshold" : "view-wide"}`} aria-label="Cafe kitchen forensic scene">
    <div className="kitchen-scene-head">
      <div><span className="cafe-kicker">Scene examination · Cafe Kitchen</span><p>Follow the cleanup route before entering the storage room.</p></div>
      <span className="cafe-scene-status">{hiddenClues.length} lead{hiddenClues.length === 1 ? "" : "s"} unresolved</span>
    </div>
    <div className="kitchen-scene-stage">
      <div className="kitchen-scene-art" style={imageUrl ? { backgroundImage: `url(${imageUrl})` } : undefined} aria-hidden="true" />
      <div className="kitchen-light-cone" aria-hidden="true" />
      <div className={`scene-tool-in-hand scene-tool-${tool}`} aria-hidden="true"><span className="scene-tool-beam" /><span className="scene-tool-body" /></div>
      <div className="kitchen-hotspots">
        <button className="kitchen-zone zone-sink" onClick={() => selectArea("Sink & draining board")}><span>Inspect sink</span></button>
        <button className="kitchen-zone zone-mop" onClick={() => selectArea("Mop bucket")}><span>Examine bucket</span></button>
        <button className="kitchen-zone zone-doorway" onClick={() => selectArea("Storage threshold")}><span>Check threshold</span></button>
        <button className="kitchen-zone zone-floor-kitchen" onClick={() => selectArea("Tile floor")}><span>Read floor trace</span></button>
      </div>
      {tool === "uv" && <div className="kitchen-uv" aria-hidden="true" />}
    </div>
    <div className="kitchen-toolbar"><span>Camera</span><button className={!area ? "active" : ""} onClick={() => setArea(null)}>Wide scene</button><button onClick={() => selectArea("Sink & draining board")}>Sink</button><button onClick={() => selectArea("Mop bucket")}>Bucket</button><button onClick={() => selectArea("Storage threshold")}>Threshold</button><span className="kitchen-tool-label">Forensic kit</span>{TOOLS.map((item) => <button key={item.id} className={tool === item.id ? "active" : ""} onClick={() => { setTool(item.id); sfx.lensAdjust(); }}>{item.label}</button>)}</div>
    <div className="kitchen-readout panel"><div><span className="cafe-kicker">{area || "Select a surface"}</span><p>{readout}</p></div>{area && nextClue && tool === needsTool && <button className="cafe-collect" onClick={() => { onDiscover(nextClue.clue_id); setArea(null); }}>Document & collect</button>}</div>
  </section>;
}
