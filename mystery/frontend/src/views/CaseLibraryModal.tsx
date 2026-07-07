import { useState, useEffect } from "react";
import { api } from "../api";

interface CaseLibraryModalProps {
  onClose: () => void;
  activeCaseId: string;
  onDuplicate: (recipe: any) => void;
}

export default function CaseLibraryModal({ onClose, activeCaseId, onDuplicate }: CaseLibraryModalProps) {
  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter states
  const [sortBy, setSortBy] = useState<string>("created_at");
  const [toneFilter, setToneFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [bestOfNFilter, setBestOfNFilter] = useState<string>(""); // "", "true", "false"
  const [fallbackFilter, setFallbackFilter] = useState<string>(""); // "", "true", "false"

  // Expanded states for generation details
  const [expandedCases, setExpandedCases] = useState<Record<string, boolean>>({});

  const fetchCases = async () => {
    setLoading(true);
    try {
      const params: any = { sort_by: sortBy };
      if (toneFilter) params.tone = toneFilter;
      if (typeFilter) params.case_type = typeFilter;
      if (bestOfNFilter) params.best_of_n = bestOfNFilter === "true";
      if (fallbackFilter) params.fallback_used = fallbackFilter === "true";

      const res = await api.generatedCases.list(params);
      setCases(res);
    } catch (err: any) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, [sortBy, toneFilter, typeFilter, bestOfNFilter, fallbackFilter]);

  const handleActivate = async (caseId: string) => {
    if (confirm("Activate this case? Your current progress will be lost.")) {
      try {
        await api.generatedCases.activate(caseId);
        location.reload();
      } catch (err: any) {
        alert("Failed to activate case: " + err);
      }
    }
  };

  const handleRegenerate = async (caseId: string) => {
    setLoading(true);
    try {
      const res = await api.generatedCases.regenerate(caseId);
      if (res.validation && !res.validation.valid) {
        alert("Regenerated case failed validation.");
        return;
      }
      alert(`Successfully regenerated case: "${res.title}" with seed: ${res.generation_metadata.seed}`);
      fetchCases();
    } catch (err: any) {
      alert("Regeneration failed: " + err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (caseId: string) => {
    if (confirm("Are you sure you want to permanently delete this case? This cannot be undone.")) {
      try {
        await api.generatedCases.delete(caseId);
        fetchCases();
      } catch (err: any) {
        alert("Failed to delete case: " + err);
      }
    }
  };

  const toggleExpand = (caseId: string) => {
    setExpandedCases((prev) => ({ ...prev, [caseId]: !prev[caseId] }));
  };

  const formatDate = (isoString: string | undefined) => {
    if (!isoString) return "N/A";
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ maxWidth: "850px", width: "95%", maxHeight: "90vh", overflowY: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #333", paddingBottom: "0.75rem", marginBottom: "1rem" }}>
          <h2 style={{ margin: 0 }}>📚 Generated Cases Library</h2>
          <button type="button" className="btn-secondary" style={{ padding: "4px 8px", fontSize: "0.9rem" }} onClick={onClose}>Close</button>
        </div>

        {error && <div className="error-message" style={{ padding: "0.75rem", backgroundColor: "#3a1a1a", border: "1px solid #a33", borderRadius: "4px", color: "#f88", marginBottom: "1rem" }}>{error}</div>}

        {/* Filters Controls Row */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", padding: "10px", backgroundColor: "#1e1e1e", borderRadius: "6px", marginBottom: "1.25rem", fontSize: "0.85rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ color: "#aaa" }}>Sort By</label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} style={{ backgroundColor: "#2e2e2e", border: "1px solid #444", color: "#eee", padding: "4px 8px", borderRadius: "4px" }}>
              <option value="created_at">Date Created (Newest)</option>
              <option value="quality_score">Quality Score (Highest)</option>
            </select>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ color: "#aaa" }}>Tone</label>
            <select value={toneFilter} onChange={(e) => setToneFilter(e.target.value)} style={{ backgroundColor: "#2e2e2e", border: "1px solid #444", color: "#eee", padding: "4px 8px", borderRadius: "4px" }}>
              <option value="">All Tones</option>
              <option value="standard">Standard</option>
              <option value="family_friendly">Family Friendly</option>
              <option value="dark_noir">Dark Noir</option>
            </select>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ color: "#aaa" }}>Case Type</label>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ backgroundColor: "#2e2e2e", border: "1px solid #444", color: "#eee", padding: "4px 8px", borderRadius: "4px" }}>
              <option value="">All Types</option>
              <option value="blackmail">Blackmail</option>
              <option value="murder">Murder</option>
              <option value="theft">Theft</option>
            </select>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ color: "#aaa" }}>Best-of-N Used</label>
            <select value={bestOfNFilter} onChange={(e) => setBestOfNFilter(e.target.value)} style={{ backgroundColor: "#2e2e2e", border: "1px solid #444", color: "#eee", padding: "4px 8px", borderRadius: "4px" }}>
              <option value="">All</option>
              <option value="true">Best-of-N Only</option>
              <option value="false">Single Candidate Only</option>
            </select>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <label style={{ color: "#aaa" }}>Fallback Used</label>
            <select value={fallbackFilter} onChange={(e) => setFallbackFilter(e.target.value)} style={{ backgroundColor: "#2e2e2e", border: "1px solid #444", color: "#eee", padding: "4px 8px", borderRadius: "4px" }}>
              <option value="">All</option>
              <option value="true">Fallback Only</option>
              <option value="false">No Fallback</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: "2rem", color: "#888" }}>Loading cases...</div>
        ) : cases.length === 0 ? (
          <div style={{ textAlign: "center", padding: "3rem", color: "#888", backgroundColor: "#1a1a1a", borderRadius: "6px" }}>
            <p style={{ margin: "0 0 10px" }}>No generated cases found matching your filters.</p>
            <p style={{ fontSize: "0.85rem", color: "#666" }}>Generate a new case or adjust your filters to see entries.</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {cases.map((c) => {
              const isActive = c.case_id === activeCaseId;
              const isExpanded = !!expandedCases[c.case_id];
              const scoreColor = c.quality_score >= 4.0 ? "#4caf50" : c.quality_score >= 3.0 ? "#ffeb3b" : "#f44336";

              return (
                <div key={c.case_id} style={{ border: isActive ? "2px solid #5c7cfa" : "1px solid #333", backgroundColor: isActive ? "#181f38" : "#1a1a1a", borderRadius: "8px", padding: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "15px" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                        <span style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#fff" }}>{c.title}</span>
                        {isActive && <span style={{ backgroundColor: "#5c7cfa", color: "#fff", padding: "2px 6px", borderRadius: "4px", fontSize: "0.75rem", fontWeight: "bold" }}>ACTIVE</span>}
                        {c.activated_at && !isActive && <span style={{ backgroundColor: "#333", color: "#aaa", padding: "2px 6px", borderRadius: "4px", fontSize: "0.75rem" }}>Played</span>}
                      </div>

                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px", fontSize: "0.75rem" }}>
                        <span style={{ backgroundColor: "#2c2c2c", color: "#ccc", padding: "2px 6px", borderRadius: "4px" }}>Type: {c.case_type}</span>
                        <span style={{ backgroundColor: "#2c2c2c", color: "#ccc", padding: "2px 6px", borderRadius: "4px" }}>Tone: {c.tone}</span>
                        <span style={{ backgroundColor: "#2c2c2c", color: "#ccc", padding: "2px 6px", borderRadius: "4px" }}>Seed: {c.seed}</span>
                        {c.candidate_count > 1 && <span style={{ backgroundColor: "#2e3b2e", color: "#a8c0a8", padding: "2px 6px", borderRadius: "4px" }}>Best of {c.candidate_count}</span>}
                        {c.fallback_used && <span style={{ backgroundColor: "#3a2a1a", color: "#f8b35e", padding: "2px 6px", borderRadius: "4px" }}>Safe Fallback</span>}
                        <span style={{ color: "#888", display: "inline-self", marginLeft: "4px" }}>Created: {formatDate(c.created_at)}</span>
                      </div>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "4px" }}>
                      {c.quality_score !== null && (
                        <div style={{ display: "flex", alignItems: "baseline", gap: "4px" }}>
                          <span style={{ fontSize: "0.75rem", color: "#aaa" }}>Quality:</span>
                          <span style={{ fontSize: "1.15rem", fontWeight: "bold", color: scoreColor }}>{c.quality_score.toFixed(1)}</span>
                          <span style={{ fontSize: "0.75rem", color: "#888" }}>/5.0</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Collapsible Generation Details */}
                  {isExpanded && (
                    <div style={{ marginTop: "8px", padding: "10px", backgroundColor: "#111", borderRadius: "6px", fontSize: "0.8rem", border: "1px solid #222" }}>
                      <h4 style={{ margin: "0 0 6px", color: "#888" }}>Generation Receipt & Diagnostics</h4>
                      <pre style={{ margin: 0, overflowX: "auto", fontFamily: "monospace", color: "#ccc", fontSize: "0.75rem" }}>
                        {JSON.stringify({
                          mode: c.mode,
                          seed: c.seed,
                          selected_seed: c.selected_seed,
                          num_suspects: c.num_suspects,
                          num_locations: c.num_locations,
                          theme_preset: c.theme_preset,
                          custom_theme: c.custom_theme,
                          tone: c.tone,
                          fallback_used: c.fallback_used,
                          repair_attempts: c.repair_attempts,
                          compaction_applied: c.compaction_applied,
                          quality_report: c.quality_report,
                          created_at: c.created_at,
                          activated_at: c.activated_at
                        }, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Actions Row */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "4px", borderTop: "1px solid #222", paddingTop: "8px" }}>
                    <button type="button" className="btn-secondary" style={{ padding: "4px 8px", fontSize: "0.75rem" }} onClick={() => toggleExpand(c.case_id)}>
                      {isExpanded ? "Hide Details ▴" : "Show Details ▾"}
                    </button>

                    <div style={{ display: "flex", gap: "8px" }}>
                      <button type="button" className="btn-secondary" style={{ padding: "4px 8px", fontSize: "0.75rem" }} onClick={() => onDuplicate(c)}>
                        Duplicate Recipe
                      </button>
                      <button type="button" className="btn-secondary" style={{ padding: "4px 8px", fontSize: "0.75rem" }} onClick={() => handleRegenerate(c.case_id)}>
                        Regenerate
                      </button>
                      <button type="button" className="btn-secondary" style={{ padding: "4px 8px", fontSize: "0.75rem", color: "#f88" }} onClick={() => handleDelete(c.case_id)}>
                        Delete
                      </button>
                      {!isActive && (
                        <button type="button" className="btn-primary" style={{ padding: "4px 10px", fontSize: "0.75rem" }} onClick={() => handleActivate(c.case_id)}>
                          Activate & Play
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
