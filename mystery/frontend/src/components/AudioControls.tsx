import { useEffect, useState } from "react";
import { audioManager, AudioState } from "../audio";

export default function AudioControls() {
  const [state, setState] = useState<AudioState>(audioManager.getAudioState());

  useEffect(() => {
    return audioManager.subscribe(setState);
  }, []);

  return (
    <div className="audio-controls">
      <button
        className={state.muted ? "tool-btn icon-only tool-off" : "tool-btn icon-only"}
        onClick={() => audioManager.toggleMute()}
        title={state.muted ? "Unmute" : "Mute"}
        aria-label={state.muted ? "Unmute" : "Mute"}
      >
        {state.muted ? "🔇" : "🔊"}
      </button>
      <input
        className="volume-slider"
        type="range"
        min="0"
        max="1"
        step="0.01"
        value={state.volume}
        onChange={(e) => audioManager.setVolume(parseFloat(e.target.value))}
        disabled={state.muted}
        title="Volume"
      />
    </div>
  );
}
