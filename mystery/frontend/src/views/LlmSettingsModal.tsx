import { useEffect, useState } from "react";
import { api } from "../api";
import type { LlmSettingsResponse, LlmProbeResult } from "../types";

interface LlmSettingsModalProps {
  onClose: () => void;
}

type Provider = "fake" | "auto" | "openai_compatible";

export default function LlmSettingsModal({ onClose }: LlmSettingsModalProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<LlmSettingsResponse | null>(null);

  const [provider, setProvider] = useState<Provider>("fake");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [dialogueEnabled, setDialogueEnabled] = useState(false);

  const [probing, setProbing] = useState(false);
  const [probeResult, setProbeResult] = useState<LlmProbeResult | null>(null);

  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getLlmSettings()
      .then((res) => {
        setData(res);
        const saved = res.saved;
        setProvider((saved?.provider as Provider) ?? "fake");
        setBaseUrl(saved?.base_url ?? "");
        setApiKey(saved?.api_key ?? "");
        setModel(saved?.model ?? "");
        setDialogueEnabled(saved?.dialogue_enabled ?? false);
        if (saved?.provider === "openai_compatible" && saved.base_url) {
          fetchModels(saved.base_url, saved.api_key ?? "");
        }
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchModels = async (urlOverride?: string, keyOverride?: string) => {
    const url = (urlOverride ?? baseUrl).trim();
    if (!url) return;
    setModelsLoading(true);
    setModelsError(null);
    try {
      const res = await api.discoverLlmModels({
        base_url: url,
        api_key: (keyOverride ?? apiKey).trim() || undefined,
      });
      setModelOptions(res.models);
      if (res.models.length === 0) {
        setModelsError("No models found at this endpoint.");
      } else {
        setModel((current) => (current && res.models.includes(current) ? current : res.models[0]));
      }
    } catch (err: any) {
      setModelOptions([]);
      setModelsError(String(err));
    } finally {
      setModelsLoading(false);
    }
  };

  const handleProbe = async () => {
    setProbing(true);
    setProbeResult(null);
    try {
      const res = await api.probeLlm();
      setProbeResult(res);
    } catch (err: any) {
      setError(String(err));
    } finally {
      setProbing(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await api.updateLlmSettings({
        provider,
        base_url: baseUrl.trim() || undefined,
        api_key: apiKey.trim() || undefined,
        model: model.trim() || undefined,
        dialogue_enabled: dialogueEnabled,
      });
      setData(res);
    } catch (err: any) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2>LLM Settings</h2>
        {error && <div className="error-message">{error}</div>}

        {loading ? (
          <p>Loading...</p>
        ) : (
          <>
            <p style={{ fontSize: "0.9rem", color: "var(--text-dim, #999)" }}>
              Controls the LLM used by "Generate New Case" (LLM-Assisted mode) and
              in-game dialogue rewriting. Without a configured LLM, generation
              falls back to the built-in deterministic templates.
            </p>

            <div className="form-group">
              <label>Provider</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value as Provider)}
                disabled={saving}
              >
                <option value="fake">Off (deterministic templates only)</option>
                <option value="auto">Auto-detect local LLM (Ollama / vmlx)</option>
                <option value="openai_compatible">Custom (OpenAI-compatible endpoint)</option>
              </select>
            </div>

            {provider === "auto" && (
              <div className="form-group">
                <button type="button" className="btn-secondary" onClick={handleProbe} disabled={probing}>
                  {probing ? "Probing..." : "Test detection now"}
                </button>
                {probeResult && (
                  <p style={{ fontSize: "0.9rem", marginTop: "0.5rem" }}>
                    {probeResult.found
                      ? `Found: ${probeResult.model} at ${probeResult.endpoint} (${probeResult.source})`
                      : "No reachable local LLM host found (checked known Ollama/vmlx hosts)."}
                  </p>
                )}
              </div>
            )}

            {provider === "openai_compatible" && (
              <>
                <div className="form-group">
                  <label>Base URL</label>
                  <input
                    type="text"
                    placeholder="http://localhost:11434/v1"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    onBlur={() => fetchModels()}
                    disabled={saving}
                  />
                </div>
                <div className="form-group">
                  <label>API Key (optional)</label>
                  <input
                    type="password"
                    placeholder="leave blank if not required"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    onBlur={() => fetchModels()}
                    disabled={saving}
                  />
                </div>
                <div className="form-group">
                  <label>Model</label>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      disabled={saving || modelsLoading || modelOptions.length === 0}
                      style={{ flex: 1 }}
                    >
                      {modelOptions.length === 0 && <option value="">No models discovered yet</option>}
                      {modelOptions.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => fetchModels()}
                      disabled={saving || modelsLoading || !baseUrl.trim()}
                    >
                      {modelsLoading ? "Loading..." : "Refresh"}
                    </button>
                  </div>
                  {modelsError && (
                    <p style={{ fontSize: "0.85rem", color: "#e08a8a", marginTop: "0.25rem" }}>{modelsError}</p>
                  )}
                </div>
              </>
            )}

            {provider !== "fake" && (
              <div className="form-group">
                <label>
                  <input
                    type="checkbox"
                    checked={dialogueEnabled}
                    onChange={(e) => setDialogueEnabled(e.target.checked)}
                    disabled={saving}
                    style={{ marginRight: "0.5rem" }}
                  />
                  Use this LLM to rewrite suspect dialogue during interviews
                </label>
              </div>
            )}

            {data?.effective && (
              <div
                className="warning-box"
                style={{
                  marginTop: "1rem",
                  padding: "0.75rem",
                  backgroundColor: data.effective.configured ? "#1f3a24" : "#3a2a20",
                  border: `1px solid ${data.effective.configured ? "#4caf6f" : "#c97c36"}`,
                  borderRadius: "4px",
                  fontSize: "0.85rem",
                }}
              >
                {data.effective.configured
                  ? `Active: ${data.effective.provider} — ${data.effective.model ?? "no model reported"}`
                  : `Not active${data.effective.fallback_reason ? `: ${data.effective.fallback_reason}` : ""}`}
              </div>
            )}

            <div className="form-actions">
              <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>
                Close
              </button>
              <button type="button" className="btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
