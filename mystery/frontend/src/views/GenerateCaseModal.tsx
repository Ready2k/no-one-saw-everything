import { useState, useEffect } from "react";
import { api } from "../api";
import { useEscapeToClose } from "../useEscapeToClose";

interface GenerateCaseModalProps {
  onClose: () => void;
  onSuccess: (fallbackUsed: boolean) => void;
  initialRecipe?: any;
}

export default function GenerateCaseModal({ onClose, onSuccess, initialRecipe }: GenerateCaseModalProps) {
  useEscapeToClose(onClose);
  const [step, setStep] = useState<"config" | "summary">("config");
  const [numSuspects, setNumSuspects] = useState<number>(initialRecipe?.num_suspects ?? 7);
  const [numLocations, setNumLocations] = useState<number>(initialRecipe?.num_locations ?? 8);
  const [themePreset, setThemePreset] = useState<string>(initialRecipe?.theme_preset ?? "blackmail");
  const [customTheme, setCustomTheme] = useState<string>(initialRecipe?.custom_theme ?? "");
  const [tone, setTone] = useState<string>(initialRecipe?.tone ?? "standard");
  const [llmNotes, setLlmNotes] = useState<string>(initialRecipe?.llm_notes ?? "");
  const [seedStr, setSeedStr] = useState("");
  const [mode, setMode] = useState<"deterministic" | "llm_assisted">(initialRecipe?.mode ?? "deterministic");
  const [candidateCount, setCandidateCount] = useState<number>(initialRecipe?.candidate_count ?? 1);
  const [lastRecipe, setLastRecipe] = useState<any>(null);
  
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [generatedCase, setGeneratedCase] = useState<any>(null);

  // Creative options are present if custom theme, non-standard tone, or notes are filled
  const hasCreativeFields = 
    (themePreset === "custom" && customTheme.trim().length > 0) || 
    (tone !== "standard") || 
    (llmNotes.trim().length > 0);

  const showWarning = mode === "deterministic" && hasCreativeFields;

  useEffect(() => {
    if (loading && mode === "llm_assisted") {
      const messages = [
        "Generating case...",
        "Writing motive seeds...",
        "Checking alibi consistency...",
        "Pruning unnecessary timelines...",
        "Validating the mystery...",
        "Assembling the narrative..."
      ];
      let i = 0;
      setLoadingMsg(messages[0]);
      const interval = setInterval(() => {
        i = (i + 1) % messages.length;
        setLoadingMsg(messages[i]);
      }, 1500);
      return () => clearInterval(interval);
    } else if (loading) {
      setLoadingMsg("Generating deterministically...");
    } else {
      setLoadingMsg("");
    }
  }, [loading, mode]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const seed = seedStr.trim() ? parseInt(seedStr, 10) : Math.floor(Math.random() * 100000);
      const effectiveCaseType = themePreset === "custom" ? "blackmail" : themePreset;

      const payload = {
        case_type: effectiveCaseType,
        difficulty: "standard",
        seed: isNaN(seed) ? 12345 : seed,
        activate: false,
        mode,
        fallback_allowed: true,
        num_suspects: numSuspects,
        num_locations: numLocations,
        theme_preset: themePreset,
        custom_theme: themePreset === "custom" ? customTheme : undefined,
        tone: tone,
        llm_notes: llmNotes,
        candidate_count: candidateCount
      };

      const res = await api.generate(payload);

      if (!res.validation.valid) {
        setError("Generated case failed validation. Check console.");
        console.error("Validation errors:", res.validation.errors);
        return;
      }
      
      setGeneratedCase(res);
      setLastRecipe(payload);
      setStep("summary");
    } catch (err: any) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleActivate = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.activate(generatedCase.case_id);
      onSuccess(generatedCase.fallback_used);
    } catch (err: any) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (!lastRecipe) return;
    setLoading(true);
    setError(null);
    try {
      const newSeed = Math.floor(Math.random() * 100000);
      setSeedStr(newSeed.toString());
      
      const payload = {
        ...lastRecipe,
        seed: newSeed,
        activate: false
      };
      
      const res = await api.generate(payload);
      
      if (!res.validation.valid) {
        setError("Generated case failed validation. Check console.");
        console.error("Validation errors:", res.validation.errors);
        return;
      }
      
      setGeneratedCase(res);
      setLastRecipe(payload);
      setStep("summary");
    } catch (err: any) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const safeFallbackMessage = (reason: string) => {
    const safeMessages: Record<string, string> = {
      llm_not_configured: "LLM integration is not fully configured.",
      provider_timeout: "LLM provider took too long to respond.",
      provider_error: "LLM provider encountered an error.",
      repair_exhausted: "LLM struggled to create a fully fair case within limits.",
      invalid_llm_json: "LLM returned unparseable content.",
      validation_failed: "LLM proposed a case that did not meet the fairness bar.",
    };
    return safeMessages[reason] || "An unexpected LLM error occurred.";
  };

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ maxWidth: "600px", width: "90%", maxHeight: "90vh", overflowY: "auto" }}>
        {step === "config" ? (
          <>
            <h2 style={{ borderBottom: "1px solid #333", paddingBottom: "0.5rem", marginBottom: "1rem" }}>Configure New Case</h2>
            {error && <div className="error-message" style={{ padding: "0.75rem", backgroundColor: "#3a1a1a", border: "1px solid #a33", borderRadius: "4px", color: "#f88", marginBottom: "1rem" }}>{error}</div>}
            
            {showWarning && (
              <div className="warning-banner" style={{ marginBottom: "1.25rem", padding: "1rem", backgroundColor: "#3a2a1a", border: "1px solid #d91", borderRadius: "6px", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <p style={{ color: "#f8b35e", margin: 0, fontSize: "0.9rem", lineHeight: "1.4" }}>
                  <strong>Notice:</strong> Custom theme, non-standard tone, or Director's Notes require <strong>LLM-Assisted</strong> generation.
                </p>
                <button 
                  type="button" 
                  className="btn-primary" 
                  style={{ alignSelf: "flex-start", fontSize: "0.8rem", padding: "4px 10px", backgroundColor: "#c97c36", borderColor: "#c97c36" }} 
                  onClick={() => setMode("llm_assisted")}
                >
                  Switch to LLM-Assisted Mode
                </button>
              </div>
            )}

            <form onSubmit={handleGenerate} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              
              {/* Section 1: Case Shape */}
              <fieldset style={{ border: "1px solid #2a2a2a", borderRadius: "6px", padding: "1rem", backgroundColor: "#141414" }}>
                <legend style={{ padding: "0 0.5rem", fontSize: "0.9rem", fontWeight: "bold", color: "#888" }}>Case Shape</legend>
                <div style={{ display: "flex", gap: "1rem" }}>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "#ccc" }}>Living suspects</label>
                    <select value={numSuspects} onChange={(e) => setNumSuspects(parseInt(e.target.value, 10))} disabled={loading} style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", backgroundColor: "#1e1e1e", border: "1px solid #333", color: "#fff" }}>
                      <option value={3}>3 (Killer + 2 Red Herrings)</option>
                      <option value={4}>4 suspects</option>
                      <option value={5}>5 suspects</option>
                      <option value={6}>6 suspects</option>
                      <option value={7}>7 suspects (Full village)</option>
                    </select>
                  </div>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "#ccc" }}>Active locations</label>
                    <select value={numLocations} onChange={(e) => setNumLocations(parseInt(e.target.value, 10))} disabled={loading} style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", backgroundColor: "#1e1e1e", border: "1px solid #333", color: "#fff" }}>
                      <option value={3}>3 locations</option>
                      <option value={4}>4 locations</option>
                      <option value={5}>5 locations</option>
                      <option value={6}>6 locations</option>
                      <option value={7}>7 locations</option>
                      <option value={8}>8 locations (Full map)</option>
                    </select>
                  </div>
                </div>
              </fieldset>

              {/* Section 2: Case Style */}
              <fieldset style={{ border: "1px solid #2a2a2a", borderRadius: "6px", padding: "1rem", backgroundColor: "#141414" }}>
                <legend style={{ padding: "0 0.5rem", fontSize: "0.9rem", fontWeight: "bold", color: "#888" }}>Case Style</legend>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <div className="form-group">
                    <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "#ccc" }}>Theme Preset</label>
                    <select value={themePreset} onChange={(e) => setThemePreset(e.target.value)} disabled={loading} style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", backgroundColor: "#1e1e1e", border: "1px solid #333", color: "#fff" }}>
                      <option value="blackmail">Blackmail</option>
                      <option value="debt">Debt</option>
                      <option value="betrayal">Betrayal</option>
                      <option value="custom">Other / Custom Theme...</option>
                    </select>
                  </div>
                  
                  {themePreset === "custom" && (
                    <div className="form-group" style={{ animation: "fadeIn 0.3s ease" }}>
                      <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "#ccc" }}>Custom Theme / Setting</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Cyberpunk Space Station, High Fantasy Tavern"
                        value={customTheme}
                        onChange={(e) => setCustomTheme(e.target.value)}
                        disabled={loading}
                        required
                        style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", backgroundColor: "#1e1e1e", border: "1px solid #333", color: "#fff", boxSizing: "border-box" }}
                      />
                    </div>
                  )}

                  <div className="form-group">
                    <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "#ccc" }}>Tone</label>
                    <select value={tone} onChange={(e) => setTone(e.target.value)} disabled={loading} style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", backgroundColor: "#1e1e1e", border: "1px solid #333", color: "#fff" }}>
                      <option value="standard">Standard (Classic Mystery)</option>
                      <option value="family_friendly">Family Friendly (Cozy)</option>
                      <option value="dark_noir">Dark Noir (Gritty)</option>
                    </select>
                  </div>
                </div>
              </fieldset>

              {/* Section 3: Generation Engine */}
              <fieldset style={{ border: "1px solid #2a2a2a", borderRadius: "6px", padding: "1rem", backgroundColor: "#141414" }}>
                <legend style={{ padding: "0 0.5rem", fontSize: "0.9rem", fontWeight: "bold", color: "#888" }}>Generation Engine</legend>
                <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
                  <div className="form-group" style={{ flex: "1 1 150px" }}>
                    <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "#ccc" }}>Generation Mode</label>
                    <select value={mode} onChange={(e) => setMode(e.target.value as any)} disabled={loading} style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", backgroundColor: "#1e1e1e", border: "1px solid #333", color: "#fff" }}>
                      <option value="deterministic">Deterministic Template</option>
                      <option value="llm_assisted">LLM-Assisted</option>
                    </select>
                  </div>
                  <div className="form-group" style={{ flex: "1 1 150px" }}>
                    <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "#ccc" }}>Random Seed (optional)</label>
                    <input 
                      type="number" 
                      placeholder="Leave blank for random"
                      value={seedStr} 
                      onChange={(e) => setSeedStr(e.target.value)}
                      disabled={loading}
                      style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", backgroundColor: "#1e1e1e", border: "1px solid #333", color: "#fff", boxSizing: "border-box" }}
                    />
                  </div>
                  <div className="form-group" style={{ flex: "1 1 150px" }}>
                    <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "#ccc" }}>Best of N Candidates</label>
                    <select value={candidateCount} onChange={(e) => setCandidateCount(parseInt(e.target.value, 10))} disabled={loading} style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", backgroundColor: "#1e1e1e", border: "1px solid #333", color: "#fff" }}>
                      <option value="1">1 (Single Candidate)</option>
                      <option value="2">2 Candidates</option>
                      <option value="3">3 Candidates</option>
                      <option value="4">4 Candidates</option>
                      <option value="5">5 Candidates (Best Quality)</option>
                    </select>
                  </div>
                </div>
              </fieldset>

              {/* Section 4: Director's Notes */}
              <fieldset style={{ border: "1px solid #2a2a2a", borderRadius: "6px", padding: "1rem", backgroundColor: "#141414" }}>
                <legend style={{ padding: "0 0.5rem", fontSize: "0.9rem", fontWeight: "bold", color: "#888" }}>Director's Notes</legend>
                <div className="form-group">
                  <label style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.85rem", color: "#ccc" }}>LLM Notes</label>
                  <textarea 
                    placeholder="Provide specific clues, character instructions, or weapon ideas for the LLM (e.g. 'Victim found holding a pocket watch stopped at 7:15', 'Clara Wells is the killer', etc.)"
                    value={llmNotes}
                    onChange={(e) => setLlmNotes(e.target.value)}
                    disabled={loading}
                    rows={3}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", backgroundColor: "#1e1e1e", border: "1px solid #333", color: "#fff", resize: "vertical", boxSizing: "border-box" }}
                  />
                </div>
              </fieldset>

              <div className="form-actions" style={{ display: "flex", justifyContent: "flex-end", gap: "1rem", marginTop: "1rem", borderTop: "1px solid #222", paddingTop: "1rem" }}>
                <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={loading || showWarning}>
                  {loading ? "Generating..." : "Generate Case"}
                </button>
              </div>
              {loading && (
                <div className="loading-state" style={{ marginTop: "1rem", textAlign: "center", color: "#aaa" }}>
                  <p>{loadingMsg}</p>
                </div>
              )}
            </form>
          </>
        ) : (
          <>
            <h2>Case Summary</h2>
            {error && <div className="error-message">{error}</div>}
            
            <div className="summary-box" style={{ padding: "1rem", backgroundColor: "#1c1c1c", border: "1px solid #2c2c2c", borderRadius: "6px" }}>
              <p style={{ margin: "0 0 0.5rem 0" }}><strong>Title:</strong> {generatedCase.title}</p>
              <p style={{ margin: "0 0 0.5rem 0" }}><strong>Type:</strong> {generatedCase.case_type}</p>
              
              {generatedCase.fallback_used && (
                <div className="warning-box" style={{ marginTop: "1rem", padding: "1rem", backgroundColor: "#3a2a20", border: "1px solid #c97c36", borderRadius: "4px" }}>
                  <p style={{ color: "#f0b37e", margin: 0 }}>
                    <strong>Note:</strong> We fell back to a highly polished deterministic template.
                  </p>
                  <p style={{ fontSize: "0.9rem", color: "#d89668", marginTop: "0.5rem", marginBottom: 0 }}>
                    Reason: {safeFallbackMessage(generatedCase.fallback_reason)}
                  </p>
                </div>
              )}
            </div>

            {generatedCase.generation_metadata && (
              <details style={{ marginTop: "1rem", border: "1px solid #2a2a2a", borderRadius: "6px", backgroundColor: "#141414" }}>
                <summary style={{ padding: "0.75rem 1rem", cursor: "pointer", fontSize: "0.9rem", fontWeight: "bold", color: "#888", userSelect: "none" }}>
                  Generation Details (Developer-Visible)
                </summary>
                <div style={{ padding: "1rem", borderTop: "1px solid #2a2a2a", fontSize: "0.85rem", color: "#ccc" }}>
                  <div style={{ marginBottom: "1rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <p style={{ margin: 0 }}><strong>Selected Seed:</strong> {generatedCase.generation_metadata.selected_seed ?? generatedCase.generation_metadata.seed}</p>
                    <p style={{ margin: 0 }}><strong>Best-of-N Used:</strong> {generatedCase.generation_metadata.best_of_n_used ? "Yes" : "No"}</p>
                    {generatedCase.generation_metadata.candidate_scores && (
                      <div style={{ marginTop: "0.5rem" }}>
                        <strong>Candidate Scores:</strong>
                        <ul style={{ margin: "0.25rem 0 0 1.25rem", padding: 0, listStyle: "disc" }}>
                          {generatedCase.generation_metadata.candidate_scores.map((cand: any, idx: number) => {
                            const isSelected = cand.seed === (generatedCase.generation_metadata.selected_seed ?? generatedCase.generation_metadata.seed);
                            return (
                              <li key={idx} style={{ color: isSelected ? "#4fc1ff" : "#aaa", fontWeight: isSelected ? "bold" : "normal" }}>
                                Seed {cand.seed}: Score {cand.overall_score} ({cand.is_valid ? "Valid" : "Invalid"})
                                {isSelected && " [Selected]"}
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    )}
                  </div>
                  <pre style={{ margin: 0, overflowX: "auto", whiteSpace: "pre-wrap", backgroundColor: "#0d0d0d", padding: "0.75rem", borderRadius: "4px", border: "1px solid #222", color: "#9cdcfe" }}>
                    {JSON.stringify(generatedCase.generation_metadata, null, 2)}
                  </pre>
                </div>
              </details>
            )}
            
            <div className="form-actions" style={{ marginTop: "2rem", display: "flex", justifyContent: "flex-end", gap: "1rem", flexWrap: "wrap" }}>
              <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>
                Discard
              </button>
              <button type="button" className="btn-secondary" onClick={handleRegenerate} disabled={loading || !lastRecipe}>
                {loading ? "Regenerating..." : "Regenerate with same settings"}
              </button>
              <button type="button" className="btn-primary" onClick={handleActivate} disabled={loading}>
                {loading ? "Starting..." : "Start Investigation"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
