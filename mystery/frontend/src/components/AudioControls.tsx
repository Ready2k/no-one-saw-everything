import { useEffect, useState } from "react";
import { audioManager, AudioState } from "../audio";

export default function AudioControls() {
  const [state, setState] = useState<AudioState>(audioManager.getAudioState());

  useEffect(() => {
    return audioManager.subscribe(setState);
  }, []);

  const handleUnlock = () => {
    audioManager.unlock();
    audioManager.playAmbient("investigation"); // Default ambient start
  };

  return (
    <div className="audio-controls" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
      {!state.unlocked ? (
        <button className="primary small" onClick={handleUnlock}>
          Enable Sound
        </button>
      ) : (
        <>
          <button 
            className="icon-button" 
            onClick={() => audioManager.toggleMute()}
            title={state.muted ? "Unmute" : "Mute"}
          >
            {state.muted ? "🔇" : "🔊"}
          </button>
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={state.volume}
            onChange={(e) => audioManager.setVolume(parseFloat(e.target.value))}
            disabled={state.muted}
            title="Volume"
            style={{ width: "80px" }}
          />
        </>
      )}
    </div>
  );
}
