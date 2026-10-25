import { useCallback, useEffect, useState } from "react";
import { getDeveloperOverview, askDeveloperAI } from "../api/client";
import StatCard from "./StatCard";
import ActivityTimeline from "./ActivityTimeline";
import CodeStudioView from "./CodeStudioView";

export default function DeveloperView({ projectId, userId }) {
  const [activeTab, setActiveTab] = useState("overview"); // overview, ai-assistant
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // AI Developer Assistant State
  const [aiMode, setAiMode] = useState("explain_build");
  const [customPrompt, setCustomPrompt] = useState("");
  const [aiResult, setAiResult] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [copiedSnippet, setCopiedSnippet] = useState(false);

  const loadData = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const overview = await getDeveloperOverview(projectId, userId || "DEV-001");
      setData(overview);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId, userId]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Trigger AI Developer Assistant
  const handleQueryAI = async (modeToUse = aiMode, promptText = customPrompt) => {
    try {
      setAiLoading(true);
      setError(null);
      const response = await askDeveloperAI(projectId, {
        project_id: projectId,
        user_id: userId || "DEV-001",
        mode: modeToUse,
        prompt: promptText,
        context_data: { active_task: "KAN-4", branch: "feature/stripe-webhook-fix" },
      });
      setAiResult(response);
    } catch (err) {
      setError(`AI Assistant Error: ${err.message}`);
    } finally {
      setAiLoading(false);
    }
  };

  // Initial load of AI response when switching to AI tab for the first time
  useEffect(() => {
    if (activeTab === "ai-assistant" && !aiResult && !aiLoading) {
      handleQueryAI("explain_build");
    }
  }, [activeTab]);

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedSnippet(true);
    setTimeout(() => setCopiedSnippet(false), 2500);
  };

  if (!projectId) {
    return <div className="loading">Loading configuration…</div>;
  }

  if (loading && !data) {
    return <div className="loading">Loading Developer Workspace…</div>;
  }

  const agentSync = data?.agent_sync_status || {};
  const ci = data?.build_pipeline_results || {};

  return (
    <div className="view">
      <header className="view__header">
        <div>
          <p className="view__mode view__mode--developer">Developer Workstation & Telemetry Station</p>
          <h1>{data?.project_name || "DLX E-Commerce Platform"}</h1>
          <p className="view__subtitle">
            Lead Backend Engineer: <strong>{data?.developer_name || "Alex Rivera"}</strong> | Active Branch: <code>{agentSync.active_branch || "feature/stripe-webhook-fix"}</code>
          </p>
        </div>
        <div className="status-pill-row">
          <span className="status-pill status-pill--active">
            ● Agent Sync: {agentSync.status || "ONLINE"} ({agentSync.sync_latency_ms || 142}ms)
          </span>
          <button type="button" className="btn-secondary" onClick={loadData}>
            ↻ Sync Workspace
          </button>
        </div>
      </header>

      {error && (
        <div className="error-panel">
          <p>Error in Developer View:</p>
          <pre>{error}</pre>
          <button type="button" className="btn-secondary" onClick={loadData}>Retry</button>
        </div>
      )}

      {/* Subtabs Navigation */}
      <nav className="view-subtabs">
        <button
          type="button"
          className={`view-subtab-btn ${activeTab === "overview" ? "view-subtab-btn--active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          💻 Developer Overview Dashboard
        </button>
        <button
          type="button"
          className={`view-subtab-btn ${activeTab === "code-studio" ? "view-subtab-btn--active" : ""}`}
          onClick={() => setActiveTab("code-studio")}
        >
          ⚡ Live Code Studio & Change Tracker
        </button>
        <button
          type="button"
          className={`view-subtab-btn ${activeTab === "ai-assistant" ? "view-subtab-btn--active" : ""}`}
          onClick={() => setActiveTab("ai-assistant")}
        >
          🤖 AI Developer Assistant <span className="badge badge--pill badge--platform">Project Differentiator</span>
        </button>
      </nav>

      {/* TAB 1: DEVELOPER OVERVIEW DASHBOARD */}
      {activeTab === "overview" && (
        <>
          {/* Deadline & Blocked Alerts */}
          {data.deadline_and_blocked_alerts?.map((alert) => (
            <div
              key={alert.alert_id}
              className={alert.severity === "CRITICAL" ? "alert-banner-blocked" : "alert-banner-warning"}
            >
              <span style={{ fontSize: "1.4rem" }}>{alert.severity === "CRITICAL" ? "🚨" : "⏳"}</span>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ color: alert.severity === "CRITICAL" ? "#f87171" : "#fbbf24", fontSize: "0.95rem" }}>
                    {alert.title}
                  </strong>
                  <span className={`badge ${alert.severity === "CRITICAL" ? "badge--danger" : "badge--warning"}`}>
                    {alert.task_key}
                  </span>
                </div>
                <p style={{ margin: "0.3rem 0", fontSize: "0.85rem", color: "var(--text-primary)" }}>
                  {alert.message}
                </p>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.4rem" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    <strong>Action Required:</strong> {alert.action_required}
                  </span>
                  <button
                    type="button"
                    className="btn-exec btn-exec--fail"
                    onClick={() => {
                      setActiveTab("ai-assistant");
                      setAiMode("debug_steps");
                      handleQueryAI("debug_steps");
                    }}
                  >
                    Ask AI Assistant to Diagnose →
                  </button>
                </div>
              </div>
            </div>
          ))}

          {/* Build and CI Pipeline Results Banner */}
          <section className={`ci-pipeline-card ${ci.status === "UNSTABLE" ? "ci-pipeline-card--unstable" : ""}`}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span className={`badge ${ci.status === "UNSTABLE" ? "badge--danger" : "badge--success"}`}>
                    {ci.status}
                  </span>
                  <strong style={{ color: "#fff", fontSize: "1rem" }}>{ci.pipeline || "DLX Backend CI"}</strong>
                  <code style={{ color: "var(--electric-blue)", fontSize: "0.82rem" }}>{ci.build_id}</code>
                </div>
                <p style={{ margin: "0.35rem 0", fontSize: "0.84rem", color: "var(--text-secondary)" }}>
                  Commit: <code>{ci.commit}</code> | Duration: {ci.duration} | Pass Rate: {ci.pass_rate}% ({ci.passed_tests}/{ci.total_tests} passed)
                </p>
              </div>
              <button
                type="button"
                className="btn-secondary"
                style={{ fontSize: "0.78rem" }}
                onClick={() => {
                  setActiveTab("ai-assistant");
                  setAiMode("explain_build");
                  handleQueryAI("explain_build");
                }}
              >
                Explain Failure with AI 🤖
              </button>
            </div>

            {ci.status === "UNSTABLE" && (
              <div style={{ marginTop: "0.75rem", background: "rgba(0,0,0,0.4)", borderRadius: "6px", padding: "0.6rem 0.85rem", borderLeft: "3px solid #f87171" }}>
                <div style={{ color: "#f87171", fontSize: "0.84rem", fontWeight: 700 }}>
                  Failing Stage: {ci.failing_stage}
                </div>
                <div style={{ fontFamily: "monospace", fontSize: "0.8rem", color: "#fca5a5", marginTop: "0.25rem" }}>
                  {ci.failure_reason}
                </div>
              </div>
            )}
          </section>

          {/* Assigned Jira Issues Section */}
          <section className="card">
            <div className="card__header-row">
              <h2>Assigned Jira Issues & Sprints</h2>
              <span className="badge badge--pill badge--platform">{data.assigned_jira_issues?.length || 0} Issues Assigned</span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: "1rem", marginTop: "1rem" }}>
              {data.assigned_jira_issues?.map((issue) => (
                <div
                  key={issue.external_task_id}
                  className="task-command-card"
                  style={{ borderColor: issue.is_blocked ? "rgba(239, 68, 68, 0.45)" : undefined }}
                >
                  <div className="task-card-header">
                    <a
                      href={issue.jira_url}
                      target="_blank"
                      rel="noreferrer"
                      className="task-key-link"
                    >
                      {issue.external_task_id} ↗
                    </a>
                    <div style={{ display: "flex", gap: "0.35rem" }}>
                      <span className={`badge ${issue.priority === "CRITICAL" ? "badge--danger" : "badge--priority"}`}>
                        {issue.priority}
                      </span>
                      <span className={`badge ${issue.status === "BLOCKED" ? "badge--danger" : issue.status === "COMPLETED" ? "badge--success" : "badge--primary"}`}>
                        {issue.status}
                      </span>
                    </div>
                  </div>

                  <h3 className="task-card-title">{issue.title}</h3>

                  {issue.is_blocked && (
                    <div style={{ background: "rgba(239, 68, 68, 0.12)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "6px", padding: "0.5rem", fontSize: "0.78rem", color: "#fca5a5" }}>
                      <strong>Blocker Reason:</strong> {issue.blocker_reason}
                    </div>
                  )}

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "auto", paddingTop: "0.5rem", borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                    <span>Due: <strong>{issue.due_date}</strong></span>
                    <span>Sprint: {issue.sprint}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Recent Commits & Pull Requests */}
          <div className="two-col-grid">
            <section className="card">
              <h2>Recent Commits & Branch Activity</h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", marginTop: "0.85rem" }}>
                {data.recent_commits_and_prs?.map((c) => (
                  <div key={c.hash} style={{ background: "rgba(17, 24, 39, 0.6)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "0.85rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <code style={{ color: "var(--electric-blue)", fontWeight: 700 }}>{c.hash}</code>
                        <span className="badge badge--platform">{c.branch}</span>
                      </div>
                      <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                        {new Date(c.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div style={{ color: "#fff", fontSize: "0.88rem", fontWeight: 600, margin: "0.4rem 0" }}>
                      {c.message}
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                      <span>Files: {c.files_changed?.join(", ")}</span>
                      <span style={{ color: "#34d399" }}>+{c.lines_added} / -{c.lines_deleted}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="card">
              <h2>Pending Code Reviews & PR Status</h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", marginTop: "0.85rem" }}>
                {data.pending_reviews?.map((pr) => (
                  <div key={pr.pr_id} style={{ background: "rgba(17, 24, 39, 0.6)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "0.85rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <strong style={{ color: "var(--electric-blue)", fontSize: "0.95rem" }}>{pr.pr_id}: {pr.title}</strong>
                        <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
                          <code>{pr.source_branch}</code> → <code>{pr.target_branch}</code>
                        </div>
                      </div>
                      <span className="badge badge--warning">{pr.status}</span>
                    </div>
                    <div style={{ background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.25)", borderRadius: "6px", padding: "0.45rem 0.65rem", margin: "0.5rem 0", fontSize: "0.8rem", color: "#fca5a5" }}>
                      {pr.checks_summary}
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      <span>Reviewers: {pr.reviewers?.join(", ")}</span>
                      <button
                        type="button"
                        className="btn-secondary"
                        style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}
                        onClick={() => {
                          setActiveTab("ai-assistant");
                          setAiMode("summarize_pr");
                          handleQueryAI("summarize_pr");
                        }}
                      >
                        Summarize PR with AI 🤖
                      </button>
                    </div>
                  </div>
                ))}

                {/* What You Did Today Highlight */}
                <div style={{ marginTop: "1rem", paddingTop: "0.85rem", borderTop: "1px solid var(--border-subtle)" }}>
                  <h3 style={{ fontSize: "0.9rem", color: "#fff", marginBottom: "0.5rem" }}>What You Did Today</h3>
                  <ul className="highlight-list">
                    {data.what_you_did?.map((item, idx) => (
                      <li key={idx} style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </section>
          </div>

          {/* Activity Feed */}
          <section className="card">
            <h2>Recent Workspace Activity Ledger</h2>
            <ActivityTimeline events={data.recent_activity || []} emptyMessage="No recent activity logged for developer." />
          </section>
        </>
      )}

      {/* TAB 2: LIVE CODE STUDIO & CHANGE TRACKER */}
      {activeTab === "code-studio" && (
        <CodeStudioView projectId={projectId} userId={userId} />
      )}

      {/* TAB 3: AI DEVELOPER ASSISTANT (PROJECT DIFFERENTIATOR) */}
      {activeTab === "ai-assistant" && (
        <section className="ai-assistant-wrapper">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <div>
              <h2 style={{ margin: 0, color: "#fff", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span>🤖</span> AI Developer Assistant
              </h2>
              <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                Grounded in authorized project architecture, Jira issues, git history, and CI test traces.
              </p>
            </div>
            <span className="badge badge--success">● Zero Fabrication Guarantee</span>
          </div>

          {/* Safety Boundary Banner */}
          <div className="ai-safety-disclaimer">
            <span style={{ fontSize: "1.1rem" }}>🛡️</span>
            <div>
              <strong>Strict Safety Boundary:</strong> Suggestions are provided strictly as advisory explanations and drafts. The assistant will <em>never</em> silently modify, overwrite, or commit code to your repository.
            </div>
          </div>

          {/* Mode Chips Selector */}
          <div className="ai-mode-chips">
            <button
              type="button"
              className={`ai-mode-chip ${aiMode === "explain_build" ? "ai-mode-chip--active" : ""}`}
              onClick={() => {
                setAiMode("explain_build");
                handleQueryAI("explain_build");
              }}
            >
              🔍 Explain Build Failure (504 Timeout)
            </button>
            <button
              type="button"
              className={`ai-mode-chip ${aiMode === "summarize_pr" ? "ai-mode-chip--active" : ""}`}
              onClick={() => {
                setAiMode("summarize_pr");
                handleQueryAI("summarize_pr");
              }}
            >
              🔀 Summarize PR #14 & Commits
            </button>
            <button
              type="button"
              className={`ai-mode-chip ${aiMode === "explain_code" ? "ai-mode-chip--active" : ""}`}
              onClick={() => {
                setAiMode("explain_code");
                handleQueryAI("explain_code");
              }}
            >
              🏛️ Architecture & Order Modules
            </button>
            <button
              type="button"
              className={`ai-mode-chip ${aiMode === "debug_steps" ? "ai-mode-chip--active" : ""}`}
              onClick={() => {
                setAiMode("debug_steps");
                handleQueryAI("debug_steps");
              }}
            >
              🐞 Debugging Protocol & Benchmarks
            </button>
            <button
              type="button"
              className={`ai-mode-chip ${aiMode === "jira_criteria" ? "ai-mode-chip--active" : ""}`}
              onClick={() => {
                setAiMode("jira_criteria");
                handleQueryAI("jira_criteria");
              }}
            >
              📋 Jira Requirements & Criteria
            </button>
            <button
              type="button"
              className={`ai-mode-chip ${aiMode === "plan_implementation" ? "ai-mode-chip--active" : ""}`}
              onClick={() => {
                setAiMode("plan_implementation");
                handleQueryAI("plan_implementation");
              }}
            >
              📝 Implementation Plan & Scaffold
            </button>
          </div>

          {/* Custom Prompt Box */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleQueryAI("general", customPrompt);
            }}
            style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}
          >
            <input
              type="text"
              placeholder="Ask custom question (e.g. How do I tune the database connection pool?)"
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              style={{
                flex: 1,
                background: "rgba(17, 24, 39, 0.8)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "0.6rem 1rem",
                color: "#fff",
                fontSize: "0.88rem",
              }}
            />
            <button type="submit" className="btn-primary" disabled={aiLoading}>
              {aiLoading ? "Thinking..." : "Ask Assistant"}
            </button>
          </form>

          {/* AI Response Area */}
          {aiLoading && (
            <div className="loading" style={{ padding: "2rem" }}>
              Synthesizing grounded explanation from project evidence…
            </div>
          )}

          {aiResult && !aiLoading && (
            <div style={{ background: "rgba(10, 15, 29, 0.75)", border: "1px solid var(--border-subtle)", borderRadius: "10px", padding: "1.25rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "0.5rem" }}>
                <h3 style={{ margin: 0, color: "var(--electric-blue)", fontSize: "1.05rem" }}>
                  {aiResult.title}
                </h3>
                <span className="badge badge--success">Advisory Mode</span>
              </div>

              {/* Explanation Text */}
              <div style={{ color: "#e2e8f0", fontSize: "0.9rem", lineHeight: 1.6, whiteSpace: "pre-line" }}>
                {aiResult.explanation}
              </div>

              {/* Suggested Steps Checklist */}
              {aiResult.suggested_steps?.length > 0 && (
                <div style={{ marginTop: "1.25rem" }}>
                  <h4 style={{ color: "#fff", fontSize: "0.88rem", marginBottom: "0.5rem" }}>Suggested Next Steps</h4>
                  <ul className="highlight-list">
                    {aiResult.suggested_steps.map((step, idx) => (
                      <li key={idx} style={{ color: "var(--text-primary)", fontSize: "0.85rem" }}>{step}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Code Snippets Box */}
              {aiResult.code_snippets?.map((snip, idx) => (
                <div key={idx} style={{ marginTop: "1.25rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
                    <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", fontWeight: 700 }}>
                      RECOMMENDED CODE SCAFFOLD (REVIEW BEFORE APPLYING):
                    </span>
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ fontSize: "0.72rem", padding: "0.2rem 0.6rem" }}
                      onClick={() => copyToClipboard(snip)}
                    >
                      {copiedSnippet ? "✓ Copied!" : "📋 Copy Code"}
                    </button>
                  </div>
                  <pre className="code-snippet-box">{snip}</pre>
                </div>
              ))}

              {/* Verified Citations */}
              {aiResult.citations?.length > 0 && (
                <div style={{ marginTop: "1.25rem", paddingTop: "0.75rem", borderTop: "1px solid var(--border-subtle)" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 700, display: "block", marginBottom: "0.35rem" }}>
                    VERIFIED PROJECT EVIDENCE CITATIONS:
                  </span>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                    {aiResult.citations.map((cite, idx) => (
                      <span key={idx} className="badge badge--platform" style={{ fontSize: "0.74rem" }}>
                        📎 {cite}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
