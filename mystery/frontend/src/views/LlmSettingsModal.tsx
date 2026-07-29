import { useEffect, useState } from "react";
import { api } from "../api";
import type { LlmSettingsResponse, LlmProbeResult, LlmTestResult } from "../types";
import { useEscapeToClose } from "../useEscapeToClose";

interface LlmSettingsModalProps {
  onClose: () => void;
}

type Provider = "fake" | "auto" | "openai_compatible";

export default function LlmSettingsModal({ onClose }: LlmSettingsModalProps) {
  useEscapeToClose(onClose);
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

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<LlmTestResult | null>(null);

  useEffect(() => {
    api
      .getLlmSettings()
      .then((res) => {
        setData(res);
        const saved = res.saved;
        setProvider((saved?.provider as Provider) ?? "fake");
        setBaseUrl(saved?.base_url ?? "");
        // The server never sends the real key back (see LlmSettingsSaved) —
        // leave the field blank; the placeholder shows a saved key exists.
        setApiKey("");
        setModel(saved?.model ?? "");
        setDialogueEnabled(saved?.dialogue_enabled ?? false);
        if (saved?.provider === "openai_compatible" && saved.base_url) {
          // Refresh the model list against the saved connection server-side,
          // without ever handling its key in the browser.
          fetchModels({ useSaved: true });
        }
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchModels = async (opts?: { useSaved?: boolean }) => {
    setModelsLoading(true);
    setModelsError(null);
    try {
      const res = opts?.useSaved
        ? await api.discoverSavedLlmModels()
        : await (async () => {
            const url = baseUrl.trim();
            if (!url) return { models: [], error: null };
            return api.discoverLlmModels({ base_url: url, api_key: apiKey.trim() || undefined });
          })();
      setModelOptions(res.models);
      if (res.models.length === 0) {
        setModelsError(res.error ?? "No models found at this endpoint.");
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

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // Blank key + fields unchanged from the saved connection: test the
      // saved config server-side rather than sending an empty key, which
      // would test as "no auth" even though a real key is stored.
      const usingSavedKey =
        !apiKey.trim() &&
        data?.saved?.api_key_set &&
        baseUrl.trim() === (data.saved.base_url ?? "") &&
        model.trim() === (data.saved.model ?? "");
      const res = usingSavedKey
        ? await api.testSavedLlm()
        : await api.testLlm({
            base_url: baseUrl.trim(),
            api_key: apiKey.trim() || undefined,
            model: model.trim(),
          });
      setTestResult(res);
    } catch (err: any) {
      setTestResult({ ok: false, error: String(err) });
    } finally {
      setTesting(false);
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
                    placeholder={
                      data?.saved?.api_key_set
                        ? `Saved (••••${data.saved.api_key_last4 ?? "????"}) — leave blank to keep`
                        : "leave blank if not required"
                    }
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    onBlur={() => apiKey.trim() && fetchModels()}
                    disabled={saving}
                    autoComplete="off"
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

                <div className="form-group">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={handleTest}
                    disabled={testing || !baseUrl.trim() || !model.trim()}
                  >
                    {testing ? "Testing..." : "Test"}
                  </button>
                  {testResult && (
                    <p
                      style={{
                        fontSize: "0.85rem",
                        marginTop: "0.5rem",
                        color: testResult.ok ? "#7fc98f" : "#e08a8a",
                      }}
                    >
                      {testResult.ok
                        ? `LLM responded in ${testResult.elapsed_ms}ms: "${testResult.reply}"`
                        : `Test failed: ${testResult.error}`}
                    </p>
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

            {data?.effective && (() => {
              // "Configured" only ever meant "the fields are filled in", but this
              // badge treated it as "working" and went green for a host that does
              // not resolve — while every line in the game silently fell back to
              // deterministic text. Health is now three states, not two.
              const e = data.effective;
              const healthy = e.configured && e.reachable !== false && !e.session_degraded;
              const unknown = e.configured && e.reachable === null && !e.session_degraded;
              const palette = healthy
                ? { bg: "#1f3a24", border: "#4caf6f" }
                : unknown
                  ? { bg: "#2c2f38", border: "#7b8394" }
                  : { bg: "#3a2a20", border: "#c97c36" };

              let message: string;
              if (!e.configured) {
                message = `Not active${e.fallback_reason ? `: ${e.fallback_reason}` : ""}`;
              } else if (e.reachable === false) {
                // The detail comes from discovery._describe_error and is not
                // punctuated, so terminate it before the next sentence.
                const detail = e.health_detail ?? "The host did not respond";
                const reason = /[.!?…]$/.test(detail) ? detail : `${detail}.`;
                message = `Unreachable: ${e.provider} — ${
                  e.base_url ?? "no endpoint"
                }. ${reason} Dialogue will fall back to the written script.`;
              } else if (e.session_degraded) {
                message =
                  "This session hit an LLM error and has dropped to the written script for the rest of it. Reset the session to try the model again.";
              } else if (e.reachable === null) {
                message = `Checking ${e.base_url ?? "endpoint"}… (reopen to see the result)`;
              } else {
                message = `Active: ${e.provider} — ${e.model ?? "no model reported"}`;
              }

              return (
                <div
                  className="warning-box"
                  style={{
                    marginTop: "1rem",
                    padding: "0.75rem",
                    backgroundColor: palette.bg,
                    border: `1px solid ${palette.border}`,
                    borderRadius: "4px",
                    fontSize: "0.85rem",
                  }}
                >
                  {message}
                </div>
              );
            })()}

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
