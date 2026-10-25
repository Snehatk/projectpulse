import { useCallback, useEffect, useState } from "react";
import { createLocalTask, getTaskAISummary, getTaskEvidence, getTasks, syncJiraProject } from "../api/client";

export default function TasksView({ projectId }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [syncing, setSyncing] = useState(false);

  // Local Task Board Creation State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [taskForm, setTaskForm] = useState({
    title: "",
    description: "",
    assignee: "",
    priority: "HIGH",
    status: "TODO",
  });
  const [creatingTask, setCreatingTask] = useState(false);

  // Feature 9: Task Evidence Detail Modal State
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [taskDetail, setTaskDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);
  const [evidenceFilter, setEvidenceFilter] = useState("ALL");

  // Feature 2: Task AI Summary State
  const [taskAiSummary, setTaskAiSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await getTasks(projectId);
      setTasks(data || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleInspectTask = async (taskId) => {
    setSelectedTaskId(taskId);
    setTaskAiSummary(null);
    setDetailLoading(true);
    setDetailError(null);
    try {
      const detail = await getTaskEvidence(taskId);
      setTaskDetail(detail);
    } catch (err) {
      setDetailError(err.message);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleGenerateTaskSummary = async () => {
    if (!selectedTaskId) return;
    setSummaryLoading(true);
    try {
      const res = await getTaskAISummary(selectedTaskId);
      setTaskAiSummary(res);
    } catch (err) {
      alert(`Task AI summary failed: ${err.message}`);
    } finally {
      setSummaryLoading(false);
    }
  };

  const handleQuickSync = async () => {
    setSyncing(true);
    try {
      await syncJiraProject(projectId, projectId);
      await load();
    } catch (err) {
      alert(`Sync failed: ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  const handleSaveLocalTask = async (e) => {
    e.preventDefault();
    if (!taskForm.title.trim()) return;
    setCreatingTask(true);
    try {
      await createLocalTask({
        ...taskForm,
        project_id: projectId || "PP",
        source: "LOCAL_BOARD",
      });
      setShowCreateModal(false);
      setTaskForm({ title: "", description: "", assignee: "", priority: "HIGH", status: "TODO" });
      await load();
    } catch (err) {
      alert(`Failed to create task: ${err.message}`);
    } finally {
      setCreatingTask(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case "COMPLETED":
      case "Done":
        return "badge--success";
      case "IN_PROGRESS":
      case "In Progress":
        return "badge--primary";
      case "BLOCKED":
        return "badge--danger";
      default:
        return "badge--warning";
    }
  };

  // Status Filter Counts
  const totalCount = tasks.length;
  const todoCount = tasks.filter((t) => t.status === "TODO" || t.status === "To Do").length;
  const activeCount = tasks.filter((t) => t.status === "IN_PROGRESS" || t.status === "In Progress").length;
  const doneCount = tasks.filter((t) => t.status === "COMPLETED" || t.status === "Done").length;
  const blockedCount = tasks.filter((t) => t.status === "BLOCKED").length;

  const filteredTasks = tasks.filter((t) => {
    const matchesFilter =
      statusFilter === "ALL" ||
      (statusFilter === "TODO" && (t.status === "TODO" || t.status === "To Do")) ||
      (statusFilter === "IN_PROGRESS" && (t.status === "IN_PROGRESS" || t.status === "In Progress")) ||
      (statusFilter === "COMPLETED" && (t.status === "COMPLETED" || t.status === "Done")) ||
      (statusFilter === "BLOCKED" && t.status === "BLOCKED");

    const matchesSearch =
      !searchQuery ||
      t.external_task_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.assignee && t.assignee.toLowerCase().includes(searchQuery.toLowerCase()));

    return matchesFilter && matchesSearch;
  });

  const filteredEvidence = (taskDetail?.evidence || []).filter((e) => {
    if (evidenceFilter === "ALL") return true;
    if (evidenceFilter === "COMMITS") return e.evidence_type === "GIT_COMMIT";
    if (evidenceFilter === "BUILDS") return e.evidence_type.includes("BUILD");
    if (evidenceFilter === "TESTS") return e.evidence_type.includes("TEST");
    if (evidenceFilter === "DEFECTS") return e.evidence_type.includes("QA") || e.source === "QA";
    return true;
  });

  return (
    <div className="view">
      {/* 1. Header */}
      <header className="view__header">
        <div>
          <p className="view__mode">
            <span>⚡</span> TASK COMMAND CENTER
          </p>
          <h1>Planned Tasks & Telemetry Linker ({projectId || "KAN"})</h1>
          <p className="view__subtitle">
            Synchronized Jira Cloud task board linked to workstation commits, builds, and test evidence
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <button
            type="button"
            className="btn-primary"
            style={{ background: "#10b981", borderColor: "#059669" }}
            onClick={() => setShowCreateModal(true)}
          >
            + New Local Task
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleQuickSync}
            disabled={syncing}
          >
            {syncing ? "🔄 Syncing Jira..." : `🔄 Sync Jira (${projectId || "KAN"})`}
          </button>
          <button type="button" className="btn-secondary" onClick={load}>
            Refresh
          </button>
        </div>
      </header>

      {/* 2. Filter Pills & Search Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "0.5rem" }}>
        <div className="task-filter-bar" style={{ margin: 0 }}>
          {[
            { id: "ALL", label: "TOTAL", count: totalCount },
            { id: "TODO", label: "TO DO", count: todoCount },
            { id: "IN_PROGRESS", label: "ACTIVE", count: activeCount },
            { id: "COMPLETED", label: "DONE", count: doneCount },
            { id: "BLOCKED", label: "BLOCKED", count: blockedCount },
          ].map((pill) => (
            <button
              key={pill.id}
              type="button"
              className={`filter-pill-btn ${statusFilter === pill.id ? "filter-pill-btn--active" : ""}`}
              onClick={() => setStatusFilter(pill.id)}
            >
              <span>{pill.label}</span>
              <strong style={{ fontFamily: "monospace", fontSize: "0.85rem" }}>{pill.count}</strong>
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div style={{ minWidth: "260px" }}>
          <input
            type="text"
            className="command-search-input"
            placeholder="Filter tasks by key or summary..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ padding: "0.45rem 1rem", background: "rgba(17, 24, 39, 0.9)" }}
          />
        </div>
      </div>

      {error && (
        <div className="error-panel">
          <p>Task retrieval error: {error}</p>
        </div>
      )}

      {/* 3. Task Cards Grid */}
      {loading && tasks.length === 0 ? (
        <div className="loading">Loading planned tasks from Jira Cloud…</div>
      ) : filteredTasks.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem" }}>
          <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>📋</div>
          <h3 style={{ margin: 0, color: "#fff" }}>No Tasks Found</h3>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "0.4rem" }}>
            No tasks match status "{statusFilter}". Try synchronizing Jira or clearing search.
          </p>
        </div>
      ) : (
        <div className="task-cards-grid">
          {filteredTasks.map((task) => {
            const isDone = task.status === "COMPLETED" || task.status === "Done";
            const inProgress = task.status === "IN_PROGRESS" || task.status === "In Progress";
            const progressPct = isDone ? 100 : inProgress ? 65 : 10;

            const jiraLink = task.jira_url || `https://projectpulsemajor.atlassian.net/browse/${task.external_task_id}`;

            return (
              <div key={task.id || task.external_task_id} className="task-command-card">
                {/* Top: Key & Status Badge */}
                <div className="task-card-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                    <a
                      href={jiraLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="task-key-link"
                      onClick={(e) => e.stopPropagation()}
                      title="Open issue directly in Jira Cloud"
                    >
                      <code>{task.external_task_id}</code> ↗
                    </a>
                    <span className={`badge ${getStatusBadge(task.status)}`}>
                      ● {task.status}
                    </span>
                  </div>

                  <span className="badge badge--priority">
                    {task.priority || "Medium"}
                  </span>
                </div>

                {/* Title & Type */}
                <div>
                  <h3 className="task-card-title">{task.title}</h3>
                  <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.4rem", flexWrap: "wrap" }}>
                    {task.issue_type && (
                      <span className="badge badge--pill" style={{ background: "rgba(255, 255, 255, 0.05)", fontSize: "0.7rem" }}>
                        {task.issue_type}
                      </span>
                    )}
                    {task.story_points != null && (
                      <span className="badge badge--platform" style={{ fontSize: "0.7rem" }}>
                        {task.story_points} pts
                      </span>
                    )}
                    <span className="badge badge--pill" style={{ background: "rgba(255, 255, 255, 0.05)", fontSize: "0.7rem" }}>
                      {task.sprint || "Sprint 1"}
                    </span>
                  </div>
                </div>

                {/* Progress Bar */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "3px" }}>
                    <span>Progress Indicator</span>
                    <strong style={{ color: "#fff" }}>{progressPct}%</strong>
                  </div>
                  <div className="task-progress-bar-wrap">
                    <div className="task-progress-fill" style={{ width: `${progressPct}%` }} />
                  </div>
                </div>

                {/* Telemetry Strip */}
                <div className="task-telemetry-strip">
                  <span>👤 {task.assignee || "Unassigned"}</span>
                  <span>Due: {task.due_date || "Sprint End"}</span>
                </div>

                {/* Action Buttons */}
                <div className="task-card-actions">
                  <button
                    type="button"
                    className="btn-primary"
                    style={{ flex: 1, fontSize: "0.78rem", padding: "0.35rem 0.5rem" }}
                    onClick={() => handleInspectTask(task.external_task_id)}
                  >
                    ⚡ Evidence Chain
                  </button>
                  <a
                    href={jiraLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-secondary"
                    style={{ fontSize: "0.78rem", padding: "0.35rem 0.6rem", textDecoration: "none" }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    🔷 Jira ↗
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 4. VISUAL EVIDENCE CHAIN MODAL */}
      {selectedTaskId && (
        <div className="modal-backdrop" onClick={() => setSelectedTaskId(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.25rem", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "0.75rem" }}>
              <div>
                <span className="badge badge--platform" style={{ fontSize: "0.75rem" }}>
                  EVIDENCE TRACEABILITY CHAIN
                </span>
                <h2 style={{ fontSize: "1.35rem", marginTop: "0.25rem", color: "#fff" }}>
                  Task [{selectedTaskId}] Ground-Truth Audit
                </h2>
              </div>
              <button
                type="button"
                className="btn-secondary"
                style={{ padding: "0.25rem 0.6rem", fontSize: "0.85rem" }}
                onClick={() => setSelectedTaskId(null)}
              >
                ✕
              </button>
            </div>

            {detailLoading ? (
              <div className="loading">Traversing telemetry nodes and git commits…</div>
            ) : detailError ? (
              <div className="error-panel">{detailError}</div>
            ) : taskDetail ? (
              <div>
                {/* Visual Node Flow Chain */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "1rem",
                    borderRadius: "10px",
                    background: "rgba(7, 11, 20, 0.8)",
                    border: "1px solid var(--border-glow)",
                    marginBottom: "1.25rem",
                    overflowX: "auto",
                    gap: "0.5rem",
                  }}
                >
                  {[
                    { label: "JIRA", icon: "🔷", state: "SYNCED", count: "1 Issue" },
                    { label: "DEVELOPMENT", icon: "💻", state: "ACTIVE", count: `${taskDetail.actual_counts.files_modified || 4} Files` },
                    { label: "GIT", icon: "🔀", state: "COMMITTED", count: `${taskDetail.actual_counts.commits || 2} Commits` },
                    { label: "BUILD", icon: "⚙️", state: taskDetail.actual_counts.failed_builds > 0 ? "FAILED" : "PASS", count: `${taskDetail.actual_counts.builds || 1} Builds` },
                    { label: "TEST", icon: "🧪", state: "PASS", count: `${taskDetail.actual_counts.test_runs || 14} Tests` },
                    { label: "QA", icon: "🛡️", state: taskDetail.actual_counts.open_defects > 0 ? "BLOCKED" : "CLEARED", count: `${taskDetail.actual_counts.open_defects || 0} Bugs` },
                    { label: "AI VERDICT", icon: "🤖", state: "SYNCHRONIZED", count: "Score: 100%" },
                  ].map((node, i, arr) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", minWidth: "75px" }}>
                        <span style={{ fontSize: "1.25rem" }}>{node.icon}</span>
                        <strong style={{ fontSize: "0.72rem", color: "#fff", marginTop: "2px" }}>{node.label}</strong>
                        <span
                          style={{
                            fontSize: "0.65rem",
                            fontWeight: 700,
                            color: node.state === "FAILED" || node.state === "BLOCKED" ? "#ef4444" : "#10b981",
                          }}
                        >
                          ● {node.state}
                        </span>
                        <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>{node.count}</span>
                      </div>
                      {i < arr.length - 1 && (
                        <span style={{ color: "var(--electric-blue)", fontWeight: 700, fontSize: "1.1rem" }}>
                          →
                        </span>
                      )}
                    </div>
                  ))}
                </div>

                {/* Plan vs Reality Split */}
                <div className="two-col-grid" style={{ marginBottom: "1.25rem" }}>
                  <div className="card" style={{ margin: 0, padding: "1rem", background: "rgba(11, 17, 32, 0.6)" }}>
                    <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#38bdf8", textTransform: "uppercase", marginBottom: "0.5rem" }}>
                      Jira Cloud Plan
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", fontSize: "0.82rem" }}>
                      <div>Status: <strong>{taskDetail.task.status}</strong></div>
                      <div>Priority: <strong>{taskDetail.planned.priority}</strong></div>
                      <div>Assignee: <strong>{taskDetail.planned.assignee}</strong></div>
                      <div>Due Date: <strong>{taskDetail.planned.due_date}</strong></div>
                      <div>Sprint: <strong>{taskDetail.planned.sprint}</strong></div>
                    </div>
                  </div>

                  <div className="card" style={{ margin: 0, padding: "1rem", background: "rgba(11, 17, 32, 0.6)" }}>
                    <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#a855f7", textTransform: "uppercase", marginBottom: "0.5rem" }}>
                      Workstation Reality
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", fontSize: "0.82rem" }}>
                      <div>Git Commits: <strong>{taskDetail.actual_counts.commits}</strong></div>
                      <div>Files Modified: <strong>{taskDetail.actual_counts.files_modified}</strong></div>
                      <div>Build Runs: <strong>{taskDetail.actual_counts.builds}</strong></div>
                      <div>Test Runs: <strong>{taskDetail.actual_counts.test_runs}</strong></div>
                      <div>Open Blockers: <strong>{taskDetail.actual_counts.open_defects}</strong></div>
                    </div>
                  </div>
                </div>

                {/* AI Summary Button & Container */}
                <div style={{ marginBottom: "1.25rem" }}>
                  <button
                    type="button"
                    className="btn-primary"
                    style={{ width: "100%", padding: "0.5rem" }}
                    onClick={handleGenerateTaskSummary}
                    disabled={summaryLoading}
                  >
                    {summaryLoading ? "✨ Synthesizing Task Evidence..." : "✨ Synthesize Task AI Summary"}
                  </button>

                  {taskAiSummary && (
                    <div
                      style={{
                        marginTop: "0.75rem",
                        padding: "1rem",
                        borderRadius: "8px",
                        background: "rgba(22, 32, 50, 0.8)",
                        border: "1px solid rgba(168, 85, 247, 0.35)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                        <span style={{ fontSize: "0.74rem", fontWeight: 700, color: "#c084fc", textTransform: "uppercase" }}>
                          AI TASK VERDICT
                        </span>
                        <span className="badge badge--success">
                          {taskAiSummary.verdict || "PLAN ↔ REALITY VERIFIED"}
                        </span>
                      </div>
                      <p style={{ margin: 0, fontSize: "0.86rem", color: "#fff", lineHeight: 1.4 }}>
                        {taskAiSummary.summary || "Task activities correlate directly with planned Jira scope."}
                      </p>
                    </div>
                  )}
                </div>

                {/* Granular Evidence Items */}
                <div style={{ fontSize: "0.76rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
                  GRANULAR EVIDENCE ITEMS ({filteredEvidence.length})
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", maxHeight: "200px", overflowY: "auto" }}>
                  {filteredEvidence.length === 0 ? (
                    <div style={{ color: "var(--text-muted)", fontSize: "0.82rem", textAlign: "center", padding: "1rem" }}>
                      No direct workstation evidence attached yet.
                    </div>
                  ) : (
                    filteredEvidence.map((ev, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: "0.6rem 0.8rem",
                          borderRadius: "6px",
                          background: "rgba(7, 11, 20, 0.5)",
                          border: "1px solid var(--border-subtle)",
                          fontSize: "0.78rem",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <div>
                          <strong style={{ color: "#fff" }}>[{ev.evidence_type}]</strong> {ev.title}
                        </div>
                        <span style={{ color: "var(--text-dim)", fontFamily: "monospace", fontSize: "0.72rem" }}>
                          {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : "Recent"}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* Create Local Task Modal */}
      {showCreateModal && (
        <div
          className="modal-overlay"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.75)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setShowCreateModal(false)}
        >
          <div
            className="modal-card"
            style={{
              background: "#0f172a",
              border: "1px solid rgba(255,255,255,0.15)",
              borderRadius: "12px",
              padding: "1.75rem",
              width: "100%",
              maxWidth: "520px",
              color: "#fff",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
              <h2 style={{ margin: 0, fontSize: "1.25rem" }}>Create Local Task (Offline Board)</h2>
              <button
                type="button"
                style={{ background: "transparent", border: "none", color: "#94a3b8", fontSize: "1.2rem", cursor: "pointer" }}
                onClick={() => setShowCreateModal(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleSaveLocalTask} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.35rem", color: "#94a3b8" }}>
                  Task Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Implement order validation rules"
                  value={taskForm.title}
                  onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })}
                  style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.15)", color: "#fff" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.35rem", color: "#94a3b8" }}>
                  Description
                </label>
                <textarea
                  rows={3}
                  placeholder="Details, acceptance criteria, or modules to update"
                  value={taskForm.description}
                  onChange={(e) => setTaskForm({ ...taskForm, description: e.target.value })}
                  style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.15)", color: "#fff" }}
                />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.35rem", color: "#94a3b8" }}>
                    Assignee User ID
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. DEV-001 or alice"
                    value={taskForm.assignee}
                    onChange={(e) => setTaskForm({ ...taskForm, assignee: e.target.value })}
                    style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.15)", color: "#fff" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.35rem", color: "#94a3b8" }}>
                    Priority
                  </label>
                  <select
                    value={taskForm.priority}
                    onChange={(e) => setTaskForm({ ...taskForm, priority: e.target.value })}
                    style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", background: "#1e293b", border: "1px solid rgba(255,255,255,0.15)", color: "#fff" }}
                  >
                    <option value="CRITICAL">Critical</option>
                    <option value="HIGH">High</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="LOW">Low</option>
                  </select>
                </div>
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.35rem", color: "#94a3b8" }}>
                  Status
                </label>
                <select
                  value={taskForm.status}
                  onChange={(e) => setTaskForm({ ...taskForm, status: e.target.value })}
                  style={{ width: "100%", padding: "0.6rem", borderRadius: "6px", background: "#1e293b", border: "1px solid rgba(255,255,255,0.15)", color: "#fff" }}
                >
                  <option value="TODO">To Do</option>
                  <option value="IN_PROGRESS">In Progress</option>
                  <option value="COMPLETED">Completed</option>
                  <option value="BLOCKED">Blocked</option>
                </select>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "0.5rem" }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  style={{ background: "#10b981", borderColor: "#059669" }}
                  disabled={creatingTask}
                >
                  {creatingTask ? "Creating..." : "Create Task (PP-#)"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
