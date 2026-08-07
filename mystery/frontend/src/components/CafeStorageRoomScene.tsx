import { useMemo, useState, type CSSProperties, type PointerEvent } from "react";
import type { ClueHotspot } from "../types";
import { sfx } from "../sfx";

type StorageView = "wide" | "floor" | "drawer" | "stain" | "door";
type StorageTool = "raking" | "swab" | "uv";
type FloorInterpretation = "single-impact" | "multiple-impacts" | "spillage";

const VIEW_ASSETS: Record<Exclude<StorageView, "wide">, string> = {
  floor: "/art/case_001/storage_room_floor_trace_v1.avif",
  drawer: "/art/case_001/storage_room_drawer_closed_v1.avif",
  stain: "/art/case_001/storage_room_crate_stain_v1.avif",
  door: "/art/case_001/storage_room_rear_door_v1.avif",
};

const VIEW_LABELS: { id: StorageView; label: string; detail: string }[] = [
  { id: "wide", label: "Room", detail: "Establish the routes, surfaces and possible transfer points." },
  { id: "floor", label: "Floor trace", detail: "Flour disturbance between the lower shelf and kitchen threshold." },
  { id: "drawer", label: "Stock drawer", detail: "A low pull-out drawer beneath the stock table." },
  { id: "stain", label: "Crate stain", detail: "A dark red-brown mark on a produce crate." },
  { id: "door", label: "Rear door", detail: "Latch, inner threshold and the service-lane exit." },
];

const TOOL_LABELS: Record<StorageTool, string> = {
  raking: "Raking light",
  swab: "Presumptive swab",
  uv: "UV lamp",
};

export function CafeStorageRoomScene({
  imageUrl,
  hiddenClues,
  onDiscover,
}: {
  imageUrl?: string;
  hiddenClues: ClueHotspot[];
  onDiscover: (clueId: string) => void;
}) {
  const [view, setView] = useState<StorageView>("wide");
  const [tool, setTool] = useState<StorageTool>("raking");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerCleared, setDrawerCleared] = useState(false);
  const [stainCleared, setStainCleared] = useState(false);
  const [doorChecked, setDoorChecked] = useState(false);
  const [floorStage, setFloorStage] = useState(0);
  const [interpretation, setInterpretation] = useState<FloorInterpretation | null>(null);
  const [feedback, setFeedback] = useState("Choose a surface. Do not assume the most dramatic mark is the useful one.");
  const [parallax, setParallax] = useState({ x: 0, y: 0 });
  const [lightPosition, setLightPosition] = useState({ x: 50, y: 50 });
  const [swabApplying, setSwabApplying] = useState(false);

  const impactClue = hiddenClues.find((clue) =>
    clue.clue_id === "clue_storage_impact_pattern" ||
    clue.title.toLowerCase().includes("impact pattern"),
  );

  const image = view === "wide"
    ? imageUrl || "/art/case_001/storage_room_interactive_wide_v1.avif"
    : view === "drawer" && drawerOpen
      ? "/art/case_001/storage_room_drawer_open_v1.avif"
      : VIEW_ASSETS[view];

  const clearedCount = Number(drawerCleared) + Number(stainCleared) + Number(doorChecked) + Number(floorStage >= 4);
  const activeDetail = VIEW_LABELS.find((item) => item.id === view)?.detail;
  const canInterpret = view === "floor" && floorStage === 2;
  const canDocument = view === "floor" && floorStage === 3 && interpretation === "single-impact";

  const stageLabel = useMemo(() => {
    if (floorStage >= 4) return "Pattern documented";
    if (floorStage === 3) return "Interpretation formed";
    if (floorStage === 2) return "Sample reacts";
    if (floorStage === 1) return "Pattern exposed";
    return "Surface unread";
  }, [floorStage]);

  const chooseView = (next: StorageView) => {
    sfx.lensAdjust();
    setView(next);
    setFeedback(VIEW_LABELS.find((item) => item.id === next)?.detail || "");
  };

  const inspect = () => {
    sfx.lensAdjust();
    if (tool === "swab") {
      setSwabApplying(true);
      window.setTimeout(() => setSwabApplying(false), 480);
    }
    if (view === "wide") {
      setFeedback("Select a specific surface before applying the field kit.");
      return;
    }
    if (view === "drawer") {
      if (!drawerOpen) {
        setFeedback("The light catches dust along the drawer seam. Open it before judging its contents.");
      } else {
        setDrawerCleared(true);
        setFeedback("Old delivery slips, string and spare labels. Mundane stocktaking material—nothing concealed beneath it.");
      }
      return;
    }
    if (view === "stain") {
      if (tool !== "swab") {
        setFeedback(`${TOOL_LABELS[tool]} cannot distinguish appearance from composition. Take a controlled sample.`);
      } else {
        setStainCleared(true);
        setFeedback("Negative presumptive blood reaction. Sugar and fruit pigment are present: spilled preserve, not evidence of injury.");
      }
      return;
    }
    if (view === "door") {
      if (tool !== "raking") {
        setFeedback(`${TOOL_LABELS[tool]} adds nothing reliable here. Read the shallow surface relief instead.`);
      } else {
        setDoorChecked(true);
        setFeedback("Fresh wet scuffing crosses inward over older wear. The latch is intact; there is no sign the rear door was forced.");
      }
      return;
    }
    if (floorStage === 0) {
      if (tool !== "raking") {
        setFeedback(tool === "uv"
          ? "UV fluorescence catches faint biological specks in the disturbed flour, but the shallow movement still needs low-angle light before you interpret it."
          : `${TOOL_LABELS[tool]} misses the shallow break in the flour. Start with low-angle light.`);
      } else {
        setFloorStage(1);
        setFeedback("Raking light separates a smeared shoe movement from ordinary sweeping marks. Tiny dark transfers sit inside the disturbed flour.");
      }
      return;
    }
    if (floorStage === 1) {
      if (tool !== "swab") {
        setFeedback(tool === "uv"
          ? "The purple fluorescence marks likely biological transfer, but UV cannot identify the material. Take a controlled swab sample."
          : `The pattern is visible, but ${TOOL_LABELS[tool].toLowerCase()} cannot identify the transferred material.`);
      } else {
        setFloorStage(2);
        setFeedback("The controlled sample gives a presumptive blood response. Small dark transfer flecks are now marked inside the disturbed flour; interpret the direction and number of disturbances.");
      }
      return;
    }
    if (floorStage === 2) {
      setFeedback("Presumptive blood response confirmed: small dark transfer flecks are visible inside the disturbed flour. Choose the interpretation that fits the pattern geometry.");
      return;
    }
    setFeedback(floorStage >= 4 ? "The pattern is already documented." : "The pattern is ready to document.");
  };

  const chooseInterpretation = (choice: FloorInterpretation) => {
    setInterpretation(choice);
    if (choice === "single-impact") {
      setFloorStage(3);
      setFeedback("The sparse directional transfers and one interrupted movement fit a single close-range impact, followed by movement toward the kitchen.");
    } else if (choice === "multiple-impacts") {
      setFeedback("That would produce overlapping arcs and repeated transfer groups. They are absent here.");
    } else {
      setFeedback("A dropped container would radiate through the flour and pool in board seams. This pattern is directional.");
    }
  };

  const documentPattern = () => {
    if (impactClue) onDiscover(impactClue.clue_id);
    setFloorStage(4);
    setFeedback(impactClue
      ? "Scene inference recorded: one close-range blunt impact, with subsequent movement toward the kitchen."
      : "The scene inference was already recorded in this case file.");
  };

  const toggleDrawer = () => {
    sfx.lensAdjust();
    setDrawerOpen((open) => {
      const next = !open;
      setFeedback(next
        ? "The drawer slides open. Examine the contents before clearing it."
        : "The stock drawer is closed.");
      return next;
    });
  };

  const moveParallax = (event: PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const pointerX = Math.min(100, Math.max(0, ((event.clientX - rect.left) / rect.width) * 100));
    const pointerY = Math.min(100, Math.max(0, ((event.clientY - rect.top) / rect.height) * 100));
    setParallax({
      x: (pointerX / 100 - 0.5) * 2,
      y: (pointerY / 100 - 0.5) * 2,
    });
    setLightPosition({ x: pointerX, y: pointerY });
  };

  const parallaxStyle = {
    "--storage-image-x": `${parallax.x * -5}px`,
    "--storage-image-y": `${parallax.y * -3}px`,
    "--storage-near-x": `${parallax.x * 8}px`,
    "--storage-near-y": `${parallax.y * 5}px`,
    "--storage-light-x": `${lightPosition.x}%`,
    "--storage-light-y": `${lightPosition.y}%`,
  } as CSSProperties;

  return (
    <section className={`storage-scene storage-view-${view} storage-tool-${tool}`} aria-label="Cafe Storage Room investigation">
      <header className="storage-scene-head">
        <div>
          <span className="cafe-kicker">Scene examination · Cafe Storage Room</span>
          <p>{activeDetail}</p>
        </div>
        <div className="storage-progress">
          <strong>{clearedCount}/4</strong>
          <span>surfaces resolved</span>
        </div>
      </header>

      <div
        className="storage-scene-stage"
        style={parallaxStyle}
        onPointerMove={moveParallax}
        onPointerLeave={() => setParallax({ x: 0, y: 0 })}
      >
        <img className="storage-scene-image" src={image} alt="" draggable={false} />
        <div className="storage-depth storage-depth-near" aria-hidden="true" />
        <div className="storage-depth storage-depth-light" aria-hidden="true" />
        {tool !== "swab" && (
          <div className={`storage-light-reveal reveal-${tool}`} aria-hidden="true">
            <img className="storage-light-image" src={image} alt="" draggable={false} />
            <div className="storage-light-tint" />
            <span className="storage-light-reticle" />
          </div>
        )}
        {view === "floor" && tool === "uv" && (
          <div className="storage-uv-evidence" aria-label="Faint fluorescent biological specks">
            <span className="storage-uv-fleck fleck-one" />
            <span className="storage-uv-fleck fleck-two" />
            <span className="storage-uv-fleck fleck-three" />
          </div>
        )}
        {tool === "swab" && (
          <div className={`storage-swab-cursor${swabApplying ? " is-applying" : ""}`} aria-hidden="true">
            <span className="storage-swab-tip" />
            <span className="storage-swab-stick" />
          </div>
        )}
        {view === "floor" && floorStage >= 2 && (
          <div className="storage-evidence-mark" aria-label="Presumptive blood transfer flecks detected">
            <span className="storage-evidence-speck speck-one" />
            <span className="storage-evidence-speck speck-two" />
            <span className="storage-evidence-speck speck-three" />
            <span className="storage-evidence-label">dark transfer flecks</span>
          </div>
        )}

        {view === "wide" && (
          <div className="storage-hotspots">
            <button className="storage-zone storage-zone-floor" onClick={() => chooseView("floor")}><span>Read floor trace</span></button>
            <button className="storage-zone storage-zone-drawer" onClick={() => chooseView("drawer")}><span>Check stock drawer</span></button>
            <button className="storage-zone storage-zone-stain" onClick={() => chooseView("stain")}><span>Test crate stain</span></button>
            <button className="storage-zone storage-zone-door" onClick={() => chooseView("door")}><span>Inspect rear door</span></button>
          </div>
        )}

        {view !== "wide" && (
          <button className="storage-back" onClick={() => chooseView("wide")}>← Return to room</button>
        )}
        {view === "drawer" && (
          <button className="storage-open-control" onClick={toggleDrawer}>{drawerOpen ? "Close drawer" : "Open drawer"}</button>
        )}
      </div>

      <div className="storage-view-controls" aria-label="Storage room views">
        <span>Camera</span>
        {VIEW_LABELS.map((item) => (
          <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => chooseView(item.id)}>
            {item.label}
            {item.id === "floor" && floorStage >= 4 ? " ✓" : ""}
            {item.id === "drawer" && drawerCleared ? " ✓" : ""}
            {item.id === "stain" && stainCleared ? " ✓" : ""}
            {item.id === "door" && doorChecked ? " ✓" : ""}
          </button>
        ))}
      </div>

      <div className="storage-workbench">
        <div className="storage-kit" aria-label="Forensic field kit">
          <span>Forensic kit</span>
          {(Object.keys(TOOL_LABELS) as StorageTool[]).map((item) => (
            <button key={item} className={tool === item ? "active" : ""} onClick={() => {
              setTool(item);
              sfx.lensAdjust();
              setFeedback(item === "swab"
                ? "Presumptive swab ready. Position the tip over the surface, then apply a controlled sample."
                : item === "raking"
                  ? "Low-angle light follows the surface. Sweep it across shallow texture and edge detail."
                  : "UV illumination follows the surface. Sweep it for fluorescent or cleaned traces.");
            }}>
              {TOOL_LABELS[item]}
            </button>
          ))}
          <button className="storage-apply" onClick={inspect}>Apply to surface</button>
        </div>

        {canInterpret && (
          <fieldset className="storage-interpretation">
            <legend>Interpret the pattern</legend>
            <button onClick={() => chooseInterpretation("single-impact")}>Single close-range impact</button>
            <button onClick={() => chooseInterpretation("multiple-impacts")}>Several repeated impacts</button>
            <button onClick={() => chooseInterpretation("spillage")}>Dropped liquid container</button>
          </fieldset>
        )}

        <div className="storage-readout panel" aria-live="polite">
          <div>
            <span className="cafe-kicker">{view === "floor" ? stageLabel : VIEW_LABELS.find((item) => item.id === view)?.label}</span>
            <p>{feedback}</p>
          </div>
          {canDocument && <button className="cafe-collect" onClick={documentPattern}>Document scene inference</button>}
        </div>
      </div>
    </section>
  );
}
