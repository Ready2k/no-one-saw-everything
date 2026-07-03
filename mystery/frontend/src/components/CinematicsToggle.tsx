import { useState } from "react";
import { cinematicsPref, setCinematicsPref } from "../settings";

export default function CinematicsToggle() {
  const [on, setOn] = useState(cinematicsPref());
  return (
    <button
      className="reset"
      title={
        on
          ? "Cinematic transitions on — click to disable (reduced motion)"
          : "Cinematic transitions off — click to enable"
      }
      onClick={() => {
        setCinematicsPref(!on);
        setOn(!on);
      }}
    >
      {on ? "🎬 FX on" : "🎬 FX off"}
    </button>
  );
}
