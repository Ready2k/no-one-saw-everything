import { useState, useEffect } from "react";
import { api } from "../api";

interface GenerateCaseModalProps {
  onClose: () => void;
  onSuccess: (fallbackUsed: boolean) => void;
}

export default function GenerateCaseModal({ onClose, onSuccess }: GenerateCaseModalProps) {
  const [step, setStep] = useState<"config" | "summary">("config");
  const [caseType, setCaseType] = useState("blackmail");
  const [seedStr, setSeedStr] = useState("");
  const [mode, setMode] = useState<"deterministic" | "llm_assisted">("deterministic");
  
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [generatedCase, setGeneratedCase] = useState<any>(null);

  useEffect(() => {
    if (loading && mode === "llm_assisted") {
      const messages = [
        "Generating case...",
        "Writing motive seeds...",
        "Checking clue fairness...",
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
      const res = await api.generate({
        case_type: caseType,
        difficulty: "standard",
        seed: isNaN(seed) ? 12345 : seed,
        activate: false,
        mode,
        fallback_allowed: true,
      });

      if (!res.validation.valid) {
        setError("Generated case failed validation. Check console.");
        console.error("Validation errors:", res.validation.errors);
        return;
      }
      
      setGeneratedCase(res);
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
      <div className="modal">
        {step === "config" ? (
          <>
            <h2>Generate New Case</h2>
            {error && <div className="error-message">{error}</div>}
            <form onSubmit={handleGenerate}>
              <div className="form-group">
                <label>Case Type</label>
                <select value={caseType} onChange={(e) => setCaseType(e.target.value)} disabled={loading}>
                  <option value="blackmail">Blackmail</option>
                  <option value="debt">Debt</option>
                  <option value="betrayal">Betrayal</option>
                </select>
              </div>
              <div className="form-group">
                <label>Generation Mode</label>
                <select value={mode} onChange={(e) => setMode(e.target.value as any)} disabled={loading}>
                  <option value="deterministic">Deterministic Template</option>
                  <option value="llm_assisted">LLM-Assisted</option>
                </select>
              </div>
              <div className="form-group">
                <label>Random Seed (optional)</label>
                <input 
                  type="number" 
                  placeholder="Leave blank for random"
                  value={seedStr} 
                  onChange={(e) => setSeedStr(e.target.value)}
                  disabled={loading}
                />
              </div>
              <div className="form-actions">
                <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={loading}>
                  {loading ? "Generating..." : "Generate Case"}
                </button>
              </div>
              {loading && (
                <div className="loading-state">
                  <p>{loadingMsg}</p>
                </div>
              )}
            </form>
          </>
        ) : (
          <>
            <h2>Case Summary</h2>
            {error && <div className="error-message">{error}</div>}
            
            <div className="summary-box">
              <p><strong>Title:</strong> {generatedCase.title}</p>
              <p><strong>Type:</strong> {generatedCase.case_type}</p>
              
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
            
            <div className="form-actions" style={{ marginTop: "2rem" }}>
              <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>
                Discard
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
