import { useState } from "react";
import { cinematicsPref, setCinematicsPref } from "../settings";
import { sfx } from "../sfx";

export default function CinematicsToggle() {
  const [on, setOn] = useState(cinematicsPref());
  return (
    <button
      className={on ? "tool-btn icon-only" : "tool-btn icon-only tool-off"}
      title={
        on
          ? "Cinematic transitions on — click to disable (reduced motion)"
          : "Cinematic transitions off — click to enable"
      }
      aria-label={on ? "Disable cinematic transitions" : "Enable cinematic transitions"}
      onClick={() => {
        sfx.click();
        setCinematicsPref(!on);
        setOn(!on);
      }}
    >
      🎬
    </button>
  );
}
