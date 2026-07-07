import React, { useEffect, useState } from "react";
import { api } from "../api";
import { PlaytestSummary, Config } from "../types";
import { useToast } from "../components/Toast";

export const PlaytestPanel: React.FC = () => {
  const [config, setConfig] = useState<Config | null>(null);
  const [summary, setSummary] = useState<PlaytestSummary | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const { showToast } = useToast();

  useEffect(() => {
    api.getConfig().then(setConfig).catch(console.error);
  }, []);

  const refreshSummary = () => {
    api.getPlaytestSummary().then(setSummary).catch(console.error);
  };

  useEffect(() => {
    if (config?.playtest_mode && isOpen) {
      refreshSummary();
      const interval = setInterval(refreshSummary, 5000);
      return () => clearInterval(interval);
    }
  }, [config?.playtest_mode, isOpen]);

  if (!config?.playtest_mode) return null;

  const handleDownload = async () => {
    try {
      const data = await api.getPlaytestExport();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `playtest_export_${data.case_metadata.case_id}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export failed", e);
      showToast("Failed to download export. See console.", "error");
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        bottom: "20px",
        right: "20px",
        zIndex: 9999,
        background: "rgba(30, 30, 30, 0.95)",
        border: "1px solid #444",
        borderRadius: "8px",
        color: "#eee",
        fontFamily: "monospace",
        fontSize: "12px",
        width: isOpen ? "300px" : "auto",
        boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
      }}
    >
      <div
        style={{
          padding: "8px 12px",
          borderBottom: isOpen ? "1px solid #444" : "none",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          cursor: "pointer",
          fontWeight: "bold",
          color: "#0f0",
        }}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span>🧪 Playtest Mode</span>
        <span>{isOpen ? "▼" : "▲"}</span>
      </div>

      {isOpen && summary && (
        <div style={{ padding: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
          <div><strong>Case:</strong> {summary.case_title} ({summary.case_type})</div>
          <div><strong>Mode:</strong> {summary.mode}</div>
          <div style={{ borderTop: "1px dashed #555", margin: "4px 0" }} />
          <div><strong>Total Telemetry Events:</strong> {summary.telemetry_event_count}</div>
          <div><strong>Player Actions:</strong> {summary.player_action_count}</div>
          <div style={{ borderTop: "1px dashed #555", margin: "4px 0" }} />
          <div><strong>Clues Found:</strong> {summary.discovered_clues} / {summary.visible_clues}</div>
          <div><strong>Interviews:</strong> {summary.interviews}</div>
          <div><strong>Free Text Qs:</strong> {summary.free_text_questions}</div>
          <div><strong>Challenges:</strong> {summary.challenges_executed} executed (of {summary.challenges_suggested} suggested)</div>
          <div><strong>Notes:</strong> {summary.notes_created}</div>
          <div><strong>Markers Used:</strong> {summary.markers_used}</div>
          <div style={{ borderTop: "1px dashed #555", margin: "4px 0" }} />
          <div><strong>Accused:</strong> {summary.accusation_submitted ? "Yes" : "No"}</div>
          {summary.accusation_submitted && (
            <>
              <div><strong>Score:</strong> {summary.score}</div>
              <div><strong>Rating:</strong> {summary.detective_rating}</div>
            </>
          )}

          <button
            onClick={handleDownload}
            style={{
              marginTop: "8px",
              padding: "6px",
              background: "#0f0",
              color: "#000",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
              fontWeight: "bold",
            }}
          >
            Download Export
          </button>
        </div>
      )}
    </div>
  );
};
