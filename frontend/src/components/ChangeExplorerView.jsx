import { useCallback, useEffect, useState } from "react";
import { getCodeExplanations } from "../api/client";

export default function ChangeExplorerView({ projectId }) {
  const [changes, setChanges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await getCodeExplanations(projectId || "PP", 50);
      setChanges(data || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  }, [load]);

  const filteredChanges = changes.filter((c) => {
    if (filter === "LINKED" && (!c.matched_task_id || c.confidence_level === "UNLINKED")) return false;
    if (filter === "UNLINKED" && c.confidence_level !== "UNLINKED") return false;
    if (filter === "CATCHUP" && !c.evidence_signals?.some((s) => s.includes("catch-up"))) return false;

    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    const matchTask = c.matched_task_id?.toLowerCase().includes(q) || c.matched_task_title?.toLowerCase().includes(q);
    const matchFiles = c.files_changed?.some((f) => f.toLowerCase().includes(q));
    const matchMsg = c.commit_message?.toLowerCase().includes(q);
    const matchExpl = c.explanation?.toLowerCase().includes(q);
    return matchTask || matchFiles || matchMsg || matchExpl;
  });

  const getConfidenceBadge = (level) => {
    switch (level) {
      case "DIRECT":
        return { label: "DIRECT LINK", bg: "rgba(16, 185, 129, 0.15)", border: "#10b981", color: "#6ee7b7" };
      case "LIKELY":
        return { label: "LIKELY CORRELATED", bg: "rgba(56, 189, 248, 0.15)", border: "#38bdf8", color: "#7dd3fc" };
      case "PLAUSIBLE":
        return { label: "PLAUSIBLE ASSIGNEE", bg: "rgba(245, 158, 11, 0.15)", border: "#f59e0b", color: "#fcd34d" };
      default:
        return { label: "UNLINKED ACTIVITY", bg: "rgba(239, 68, 68, 0.15)", border: "#ef4444", color: "#fca5a5" };
    }
  };

  return (
    <div className="view">
      {/* 1. Header */}
      <header className="view__header">
        <div>
          <p className="view__mode" style={{ color: "#38bdf8" }}>
            <span>🔍</span> CHANGE INTELLIGENCE OBSERVATORY
          </p>
          <h1>Change Explorer ({projectId || "PP"})</h1>
          <p className="view__subtitle">
            AST symbol-level change tracking, debounced change sets, and evidence-grounded semantic explanations
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <button type="button" className="btn-secondary" onClick={load}>
            Refresh
          </button>
        </div>
      </header>

      {/* 2. Controls & Search */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          {[
            { id: "ALL", label: `ALL CHANGES (${changes.length})` },
            { id: "LINKED", label: `LINKED TO TASKS (${changes.filter((c) => c.matched_task_id && c.confidence_level !== "UNLINKED").length})` },
            { id: "UNLINKED", label: `UNLINKED (${changes.filter((c) => c.confidence_level === "UNLINKED").length})` },
            { id: "CATCHUP", label: `CATCH-UP (${changes.filter((c) => c.evidence_signals?.some((s) => s.includes("catch-up"))).length})` },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`filter-pill-btn ${filter === tab.id ? "filter-pill-btn--active" : ""}`}
              onClick={() => setFilter(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div style={{ minWidth: "260px" }}>
          <input
            type="text"
            placeholder="Search files, symbols, tasks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              padding: "0.5rem 0.85rem",
              borderRadius: "8px",
              background: "rgba(255, 255, 255, 0.05)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              color: "#fff",
              fontSize: "0.85rem",
            }}
          />
        </div>
      </div>

      {/* 3. Changes List */}
      {loading && changes.length === 0 ? (
        <div className="loading">Analyzing project AST symbols and commit ledger…</div>
      ) : error ? (
        <div className="error-panel">
          <p>Failed to load change intelligence:</p>
          <pre>{error}</pre>
          <button type="button" onClick={load}>Retry</button>
        </div>
      ) : filteredChanges.length === 0 ? (
        <div className="card" style={{ padding: "2.5rem", textAlign: "center", color: "var(--text-muted)" }}>
          <p style={{ fontSize: "1.1rem", marginBottom: "0.5rem", color: "#fff" }}>No code changes found</p>
          <p style={{ fontSize: "0.88rem" }}>
            Make edits in the monitored project folder or run <code>showcase_project/demo_actions.py</code> to generate real changes.
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {filteredChanges.map((change) => {
            const badge = getConfidenceBadge(change.confidence_level);
            const isCatchup = change.evidence_signals?.some((s) => s.includes("catch-up"));

            return (
              <div
                key={change.explanation_id || change.event_id}
                className="card"
                style={{
                  padding: "1.25rem",
                  background: "rgba(15, 23, 42, 0.65)",
                  border: isCatchup ? "1px solid rgba(245, 158, 11, 0.4)" : "1px solid rgba(255, 255, 255, 0.08)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.75rem",
                }}
              >
                {/* Header Row */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap", marginBottom: "0.3rem" }}>
                      <span
                        style={{
                          padding: "0.2rem 0.6rem",
                          borderRadius: "4px",
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          background: badge.bg,
                          border: `1px solid ${badge.border}`,
                          color: badge.color,
                        }}
                      >
                        {badge.label}
                      </span>
                      {isCatchup && (
                        <span
                          style={{
                            padding: "0.2rem 0.6rem",
                            borderRadius: "4px",
                            fontSize: "0.72rem",
                            fontWeight: 700,
                            background: "rgba(245, 158, 11, 0.15)",
                            border: "1px solid #f59e0b",
                            color: "#fcd34d",
                          }}
                        >
                          OFFLINE CATCH-UP
                        </span>
                      )}
                      <span style={{ fontSize: "0.76rem", color: "var(--text-dim)", fontFamily: "monospace" }}>
                        {change.timestamp ? new Date(change.timestamp).toLocaleString() : ""}
                      </span>
                    </div>

                    <h3 style={{ margin: 0, fontSize: "1.05rem", color: "#fff", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span>{change.commit_message || "Code Modification"}</span>
                    </h3>
                  </div>

                  {change.matched_task_id && (
                    <div style={{ textAlign: "right" }}>
                      <span
                        style={{
                          padding: "0.25rem 0.6rem",
                          borderRadius: "6px",
                          background: "rgba(56, 189, 248, 0.15)",
                          border: "1px solid rgba(56, 189, 248, 0.35)",
                          color: "#38bdf8",
                          fontFamily: "monospace",
                          fontWeight: 700,
                          fontSize: "0.85rem",
                        }}
                      >
                        [{change.matched_task_id}]
                      </span>
                      <div style={{ fontSize: "0.76rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                        {change.matched_task_title}
                      </div>
                    </div>
                  )}
                </div>

                {/* Grounded Explanation Narrative */}
                <div
                  style={{
                    padding: "0.85rem 1rem",
                    borderRadius: "8px",
                    background: "rgba(2, 6, 23, 0.6)",
                    borderLeft: "3px solid #38bdf8",
                    fontSize: "0.88rem",
                    lineHeight: 1.5,
                    color: "#e2e8f0",
                  }}
                >
                  {change.explanation}
                </div>

                {/* Evidence & AST Symbol Signals */}
                {change.evidence_signals && change.evidence_signals.length > 0 && (
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                    <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 600 }}>EVIDENCE:</span>
                    {change.evidence_signals.map((sig, i) => (
                      <span
                        key={i}
                        style={{
                          padding: "0.2rem 0.5rem",
                          borderRadius: "4px",
                          background: "rgba(255, 255, 255, 0.04)",
                          border: "1px solid rgba(255, 255, 255, 0.08)",
                          fontSize: "0.75rem",
                          color: "#94a3b8",
                        }}
                      >
                        {sig}
                      </span>
                    ))}
                  </div>
                )}

                {/* Touched Files List */}
                {change.files_changed && change.files_changed.length > 0 && (
                  <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", alignItems: "center", fontSize: "0.78rem" }}>
                    <span style={{ color: "var(--text-dim)", fontWeight: 600 }}>FILES:</span>
                    {change.files_changed.map((f, i) => (
                      <code
                        key={i}
                        style={{
                          background: "rgba(15, 23, 42, 0.8)",
                          padding: "0.15rem 0.4rem",
                          borderRadius: "4px",
                          color: "#38bdf8",
                          fontSize: "0.74rem",
                        }}
                      >
                        {f}
                      </code>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
