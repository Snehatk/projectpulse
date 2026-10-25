import { useCallback, useEffect, useState } from "react";
import {
  getTesterOverview,
  listTestCases,
  createTestCase,
  updateTestCase,
  executeTestCase,
  deleteTestCase,
  listDefectDrafts,
  createDefectDraft,
  confirmDefectDraft,
  deleteDefectDraft,
  getSeleniumStatus,
  listSeleniumRuns,
  runSeleniumSuite,
  linkSeleniumFailureToJira,
} from "../api/client";
import StatCard from "./StatCard";
import ActivityTimeline from "./ActivityTimeline";

export default function TesterView({ projectId }) {
  const [activeTab, setActiveTab] = useState("overview"); // overview, test-cases, defect-linking, selenium
  const [data, setData] = useState(null);
  const [testCases, setTestCases] = useState([]);
  const [defectDrafts, setDefectDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState("");

  // Automated Browser Testing (Selenium + TestNG) State
  const [seleniumData, setSeleniumData] = useState({ environment: null, runs: [], total_runs: 0 });
  const [seleniumRunning, setSeleniumRunning] = useState(false);
  const [seleniumOptions, setSeleniumOptions] = useState({
    headless: true,
    browser: "chrome",
    test_url: "",
    suite_file: "testng.xml",
  });
  const [selectedRun, setSelectedRun] = useState(null);
  const [jiraLinkModal, setJiraLinkModal] = useState({
    show: false,
    runId: "",
    testName: "",
    failureMsg: "",
    jiraKey: "PP-3",
  });

  // Filters for test cases
  const [suiteFilter, setSuiteFilter] = useState("ALL");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  // Create Test Case Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newCase, setNewCase] = useState({
    title: "",
    suite_id: "SUITE-ORDER-PRICING",
    suite_name: "Order Calculation & Pricing Engine",
    description: "",
    test_type: "AUTOMATED",
    priority: "HIGH",
    status: "READY",
    preconditions: "",
    steps: "",
    expected_result: "",
    linked_jira_key: "KAN-2",
    assigned_to: "Dave Miller",
  });

  // Create Defect Draft Modal
  const [showDraftModal, setShowDraftModal] = useState(false);
  const [newDraft, setNewDraft] = useState({
    title: "",
    description: "",
    test_name: "test_stripe_webhook_timeout_under_concurrency",
    stack_trace: "AssertionError: Expected HTTP 200 within 500ms, got 504 Gateway Timeout during webhook concurrent stress test.",
    severity: "CRITICAL",
    priority: "HIGH",
    linked_jira_issue: "KAN-4",
    created_by: "Dave Miller (QA)",
  });

  const loadData = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const overview = await getTesterOverview(projectId);
      setData(overview);
      setTestCases(overview.test_cases || []);
      setDefectDrafts(overview.defect_drafts || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const loadSeleniumData = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await listSeleniumRuns(projectId);
      setSeleniumData(res);
      if (res.runs && res.runs.length > 0) {
        setSelectedRun((prev) => prev || res.runs[0]);
      }
    } catch (err) {
      console.warn("Failed loading Selenium runs:", err);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
    loadSeleniumData();
    const interval = setInterval(() => {
      loadData();
      loadSeleniumData();
    }, 10000);
    return () => clearInterval(interval);
  }, [loadData, loadSeleniumData]);

  // Handle running automated Selenium suite
  const handleRunSeleniumSuite = async () => {
    try {
      setSeleniumRunning(true);
      setError(null);
      setActionSuccess("");
      const result = await runSeleniumSuite(projectId, seleniumOptions);
      setSelectedRun(result);
      await loadSeleniumData();
      await loadData();
      setActionSuccess(`Selenium suite completed with status: ${result.status} (${result.passed_tests}/${result.total_tests} passed in ${result.duration_seconds}s)`);
      setTimeout(() => setActionSuccess(""), 5000);
    } catch (err) {
      setError(`Failed executing Selenium suite: ${err.message}`);
    } finally {
      setSeleniumRunning(false);
    }
  };

  // Handle linking Selenium failure to Jira
  const handleLinkJiraSubmit = async (e) => {
    e.preventDefault();
    try {
      await linkSeleniumFailureToJira(jiraLinkModal.runId, {
        jira_issue_key: jiraLinkModal.jiraKey,
        test_name: jiraLinkModal.testName,
        failure_message: jiraLinkModal.failureMsg,
      });
      setJiraLinkModal({ ...jiraLinkModal, show: false });
      setActionSuccess(`Linked test '${jiraLinkModal.testName}' to Jira ticket ${jiraLinkModal.jiraKey}`);
      setTimeout(() => setActionSuccess(""), 5000);
      loadData();
    } catch (err) {
      setError(`Failed linking to Jira: ${err.message}`);
    }
  };

  // Handle inline test case execution
  const handleExecuteCase = async (testCaseId, verdict) => {
    try {
      setActionSuccess("");
      const updated = await executeTestCase(testCaseId, verdict, `Executed manually by QA Dave Miller`, "Dave Miller (QA)");
      setTestCases((prev) => prev.map((tc) => (tc.test_case_id === testCaseId ? updated : tc)));
      setActionSuccess(`Test Case ${testCaseId} marked as ${verdict}`);
      setTimeout(() => setActionSuccess(""), 4000);
    } catch (err) {
      setError(`Failed to execute test case: ${err.message}`);
    }
  };

  // Handle test case creation
  const handleCreateCaseSubmit = async (e) => {
    e.preventDefault();
    try {
      const created = await createTestCase(projectId, newCase);
      setTestCases((prev) => [...prev, created]);
      setShowCreateModal(false);
      setActionSuccess(`Created Test Case ${created.test_case_id}: "${created.title}"`);
      setTimeout(() => setActionSuccess(""), 4000);
    } catch (err) {
      setError(`Failed to create test case: ${err.message}`);
    }
  };

  // Handle draft confirmation to Jira
  const handleConfirmDraft = async (draftId) => {
    try {
      setActionSuccess("");
      const res = await confirmDefectDraft(draftId, "Dave Miller (QA)");
      setDefectDrafts((prev) => prev.filter((d) => d.draft_id !== draftId));
      setActionSuccess(`Draft ${draftId} confirmed! Official Defect ${res.defect_id} linked to Jira.`);
      setTimeout(() => setActionSuccess(""), 5000);
      loadData();
    } catch (err) {
      setError(`Failed to confirm draft: ${err.message}`);
    }
  };

  // Handle draft creation
  const handleCreateDraftSubmit = async (e) => {
    e.preventDefault();
    try {
      const created = await createDefectDraft(projectId, newDraft);
      setDefectDrafts((prev) => [created, ...prev]);
      setShowDraftModal(false);
      setActionSuccess(`Defect Draft ${created.draft_id} created for review.`);
      setTimeout(() => setActionSuccess(""), 4000);
    } catch (err) {
      setError(`Failed to create defect draft: ${err.message}`);
    }
  };

  // Handle draft delete
  const handleDeleteDraft = async (draftId) => {
    try {
      await deleteDefectDraft(draftId);
      setDefectDrafts((prev) => prev.filter((d) => d.draft_id !== draftId));
      setActionSuccess(`Defect Draft ${draftId} rejected and removed.`);
      setTimeout(() => setActionSuccess(""), 4000);
    } catch (err) {
      setError(`Failed to delete draft: ${err.message}`);
    }
  };

  if (!projectId) {
    return <div className="loading">Loading configuration…</div>;
  }

  if (loading && !data) {
    return <div className="loading">Loading Tester Workspace…</div>;
  }

  // Filter test cases
  const filteredCases = testCases.filter((tc) => {
    if (suiteFilter !== "ALL" && tc.suite_id !== suiteFilter) return false;
    if (typeFilter !== "ALL" && tc.test_type !== typeFilter) return false;
    if (statusFilter !== "ALL" && tc.status !== statusFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const match =
        tc.test_case_id.toLowerCase().includes(q) ||
        tc.title.toLowerCase().includes(q) ||
        tc.linked_jira_key.toLowerCase().includes(q) ||
        tc.suite_name.toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  // Group cases by suite
  const suiteGroups = {};
  filteredCases.forEach((tc) => {
    if (!suiteGroups[tc.suite_name]) {
      suiteGroups[tc.suite_name] = [];
    }
    suiteGroups[tc.suite_name].push(tc);
  });

  const agentSync = data?.agent_sync_status || {};

  return (
    <div className="view">
      <header className="view__header">
        <div>
          <p className="view__mode view__mode--tester">QA Automation & Verification Station</p>
          <h1>{data?.project_name || "DLX E-Commerce Platform"}</h1>
          <p className="view__subtitle">
            Lead Tester: <strong>Dave Miller</strong> | Connected Agent: <code>{agentSync.machine_name || "TEST-RUNNER-DAVE"}</code>
          </p>
        </div>
        <div className="status-pill-row">
          <span className="status-pill status-pill--active">
            ● Watcher Active ({agentSync.reports_detected ? "Reports Synced" : "Awaiting Run"})
          </span>
          <button type="button" className="btn-secondary" onClick={loadData}>
            ↻ Sync Workspace
          </button>
        </div>
      </header>

      {actionSuccess && (
        <div className="alert-banner-blocked" style={{ borderColor: "#10b981", background: "rgba(16, 185, 129, 0.12)" }}>
          <span style={{ fontSize: "1.2rem" }}>✓</span>
          <div style={{ color: "#34d399", fontWeight: 600 }}>{actionSuccess}</div>
        </div>
      )}

      {error && (
        <div className="error-panel">
          <p>Error in Tester View:</p>
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
          📊 Tester Overview Dashboard
        </button>
        <button
          type="button"
          className={`view-subtab-btn ${activeTab === "test-cases" ? "view-subtab-btn--active" : ""}`}
          onClick={() => setActiveTab("test-cases")}
        >
          📋 Test Case Management ({testCases.length})
        </button>
        <button
          type="button"
          className={`view-subtab-btn ${activeTab === "defect-linking" ? "view-subtab-btn--active" : ""}`}
          onClick={() => setActiveTab("defect-linking")}
        >
          🔗 Failure-to-Jira Defect Linking {defectDrafts.length > 0 && <span className="badge badge--danger">{defectDrafts.length} Drafts</span>}
        </button>
        <button
          type="button"
          className={`view-subtab-btn ${activeTab === "selenium" ? "view-subtab-btn--active" : ""}`}
          onClick={() => { setActiveTab("selenium"); loadSeleniumData(); }}
        >
          🌐 Automated Browser Tests (Selenium & TestNG) {seleniumData?.runs?.length > 0 && <span className="badge badge--pill">{seleniumData.runs.length} Runs</span>}
        </button>
      </nav>

      {/* TAB 1: TESTER OVERVIEW DASHBOARD */}
      {activeTab === "overview" && (
        <>
          {/* Quick Selenium Automation Status Card */}
          <section className="card" style={{ borderLeft: "4px solid #38bdf8", marginBottom: "1rem" }}>
            <div className="card__header-row" style={{ flexWrap: "wrap", gap: "0.75rem" }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.05rem", color: "#f8fafc", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  🌐 Automated Browser Tests (Selenium + Java + TestNG)
                </h3>
                <p style={{ margin: "0.25rem 0 0", fontSize: "0.82rem", color: "var(--text-muted)" }}>
                  Suite in <code>showcase_project/selenium-tests</code>. XML reports automatically synced by Desktop Agent into telemetry.
                </p>
              </div>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                {seleniumData?.runs?.length > 0 && (
                  <span className={`badge ${seleniumData.runs[0].status === "SUCCESS" ? "badge--success" : "badge--danger"}`}>
                    Latest: {seleniumData.runs[0].passed_tests}/{seleniumData.runs[0].total_tests} Passed ({seleniumData.runs[0].duration_seconds}s)
                  </span>
                )}
                <button
                  type="button"
                  className="btn-primary"
                  style={{ fontSize: "0.82rem", padding: "0.35rem 0.8rem" }}
                  disabled={seleniumRunning}
                  onClick={handleRunSeleniumSuite}
                >
                  {seleniumRunning ? "⏳ Running..." : "▶ Run Selenium Suite"}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  style={{ fontSize: "0.82rem", padding: "0.35rem 0.8rem" }}
                  onClick={() => { setActiveTab("selenium"); loadSeleniumData(); }}
                >
                  View Details ➔
                </button>
              </div>
            </div>
          </section>

          {/* Key Metrics Grid */}
          <section className="card">
            <div className="card__header-row">
              <h2>Execution Health & Quality Gate Metrics</h2>
              <span className="badge badge--pill badge--platform">Today: {data.test_runs_today || 2} Suite Runs</span>
            </div>
            <div className="stat-grid">
              <StatCard label="Total Tests Executed" value={data.total_tests} />
              <StatCard label="Passed Tests" value={data.passed} accent="success" />
              <StatCard label="Failed Tests" value={data.failed} accent={data.failed > 0 ? "danger" : undefined} />
              <StatCard label="Skipped / Blocked" value={data.skipped} />
              <StatCard
                label="Quality Gate Pass Rate"
                value={`${data.pass_rate}%`}
                accent={data.pass_rate >= 90 ? "success" : data.pass_rate >= 75 ? "warning" : "danger"}
              />
              <StatCard label="Open QA Defects" value={data.open_defects?.length || 0} accent={data.open_defects?.length > 0 ? "danger" : "success"} />
            </div>
          </section>

          {/* Repeated Failures Detection Alert */}
          {data.repeated_failures && data.repeated_failures.length > 0 && (
            <div className="alert-banner-blocked">
              <span style={{ fontSize: "1.4rem" }}>⚠️</span>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ color: "#f87171", fontSize: "0.95rem" }}>
                    Repeated Test Failure Detected: {data.repeated_failures[0].test_name} ({data.repeated_failures[0].failure_count} times)
                  </strong>
                  <span className="badge badge--danger">Linked to {data.repeated_failures[0].linked_jira_key}</span>
                </div>
                <p style={{ margin: "0.35rem 0", fontSize: "0.86rem", color: "#fca5a5" }}>
                  {data.repeated_failures[0].sample_error}
                </p>
                <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
                  <button
                    type="button"
                    className="btn-exec btn-exec--fail"
                    onClick={() => {
                      setActiveTab("defect-linking");
                      setShowDraftModal(true);
                    }}
                  >
                    + Create Defect Draft for Jira
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{ fontSize: "0.76rem", padding: "0.25rem 0.6rem" }}
                    onClick={() => setActiveTab("test-cases")}
                  >
                    View in Test Cases
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Pending Regression Tests & Agent Connection Status */}
          <div className="two-col-grid">
            <section className="card">
              <div className="card__header-row">
                <h2>Pending Regression Tests ({data.pending_regression_tests?.length || 0})</h2>
                <button type="button" className="btn-secondary" style={{ fontSize: "0.78rem" }} onClick={() => setActiveTab("test-cases")}>
                  Manage All
                </button>
              </div>
              {data.pending_regression_tests?.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {data.pending_regression_tests.map((tc) => (
                    <div key={tc.test_case_id} className="test-case-item">
                      <div className="test-case-topline">
                        <div>
                          <span className="badge badge--priority" style={{ marginRight: "0.5rem" }}>{tc.priority}</span>
                          <strong style={{ color: "#fff", fontSize: "0.9rem" }}>{tc.title}</strong>
                        </div>
                        <span className={`badge ${tc.status === "PASSED" ? "badge--success" : tc.status === "FAILED" ? "badge--danger" : "badge--warning"}`}>
                          {tc.status}
                        </span>
                      </div>
                      <p style={{ margin: "0.3rem 0", fontSize: "0.82rem", color: "var(--text-secondary)" }}>{tc.description}</p>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.5rem" }}>
                        <span style={{ fontSize: "0.78rem", color: "var(--electric-blue)", fontFamily: "monospace" }}>
                          Jira: {tc.linked_jira_key}
                        </span>
                        <div className="exec-btn-group">
                          <button type="button" className="btn-exec btn-exec--pass" onClick={() => handleExecuteCase(tc.test_case_id, "PASSED")}>✓ Pass</button>
                          <button type="button" className="btn-exec btn-exec--fail" onClick={() => handleExecuteCase(tc.test_case_id, "FAILED")}>✕ Fail</button>
                          <button type="button" className="btn-exec btn-exec--block" onClick={() => handleExecuteCase(tc.test_case_id, "BLOCKED")}>⊘ Block</button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="empty-state">All regression test cases have passed!</p>
              )}
            </section>

            <section className="card">
              <h2>Agent & Report Synchronization Status</h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", marginTop: "0.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "0.6rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                  <span style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>Agent Role & Node</span>
                  <strong style={{ color: "#fff", fontSize: "0.85rem" }}>{agentSync.machine_name || "TEST-RUNNER-DAVE"}</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "0.6rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                  <span style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>Agent Connection Status</span>
                  <span className="badge badge--success">● {agentSync.status || "ONLINE"}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "0.6rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                  <span style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>JUnit Report Watcher</span>
                  <span style={{ color: "#38bdf8", fontFamily: "monospace", fontSize: "0.8rem" }}>
                    {agentSync.junit_file || "reports/junit.xml"} (ACTIVE)
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "0.6rem 0", borderBottom: "1px solid var(--border-subtle)" }}>
                  <span style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>Coverage XML Watcher</span>
                  <span style={{ color: "#38bdf8", fontFamily: "monospace", fontSize: "0.8rem" }}>
                    {agentSync.coverage_file || "reports/coverage.xml"} (ACTIVE)
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "0.6rem 0" }}>
                  <span style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>Last Verified Sync</span>
                  <span style={{ color: "var(--text-primary)", fontSize: "0.82rem" }}>
                    {agentSync.last_report_synced ? new Date(agentSync.last_report_synced).toLocaleTimeString() : "Just now"}
                  </span>
                </div>
              </div>

              <div style={{ marginTop: "1rem", paddingTop: "0.85rem", borderTop: "1px solid var(--border-subtle)" }}>
                <h3 style={{ fontSize: "0.88rem", color: "#fff", marginBottom: "0.5rem" }}>Upcoming Testing Tasks</h3>
                {data.upcoming_tasks?.map((t) => (
                  <div key={t.external_task_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.4rem 0" }}>
                    <span style={{ fontSize: "0.82rem", color: "var(--text-primary)" }}>
                      <code style={{ color: "var(--electric-blue)", marginRight: "0.4rem" }}>{t.external_task_id}</code>
                      {t.title}
                    </span>
                    <span className="badge badge--priority">{t.priority}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>

          {/* Recent Executions & Activity Feed */}
          <section className="card">
            <h2>Recent Test Executions History</h2>
            <div className="table-responsive">
              <table className="agents-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Suite / Title</th>
                    <th>Verdict</th>
                    <th>Duration</th>
                    <th>Error Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_executions?.map((ex, idx) => (
                    <tr key={idx}>
                      <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                        {new Date(ex.timestamp).toLocaleTimeString()}
                      </td>
                      <td>
                        <strong style={{ color: "#fff", fontSize: "0.85rem" }}>{ex.title}</strong>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>{ex.suite}</div>
                      </td>
                      <td>
                        <span className={`badge ${ex.failed > 0 ? "badge--danger" : "badge--success"}`}>
                          {ex.failed > 0 ? "FAILED" : "PASSED"}
                        </span>
                      </td>
                      <td style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{ex.duration}s</td>
                      <td style={{ fontSize: "0.78rem", color: ex.errors?.length ? "#f87171" : "var(--text-muted)" }}>
                        {ex.errors?.length ? ex.errors[0] : "All assertions passed"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {/* TAB 2: TEST CASE MANAGEMENT */}
      {activeTab === "test-cases" && (
        <section className="card">
          <div className="card__header-row">
            <div>
              <h2>Test Case Management</h2>
              <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                Organize, author, and execute manual and automated test suites linked to Jira stories.
              </p>
            </div>
            <button
              type="button"
              className="btn-primary"
              onClick={() => setShowCreateModal(true)}
            >
              + Create Test Case
            </button>
          </div>

          {/* Filter Bar */}
          <div className="task-filter-bar" style={{ marginTop: "1rem" }}>
            <input
              type="text"
              placeholder="Search test cases by ID, title, Jira key..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                background: "rgba(17, 24, 39, 0.8)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "0.45rem 0.85rem",
                color: "#fff",
                fontSize: "0.85rem",
                width: "280px",
              }}
            />
            <select
              value={suiteFilter}
              onChange={(e) => setSuiteFilter(e.target.value)}
              style={{
                background: "rgba(17, 24, 39, 0.8)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "0.45rem 0.85rem",
                color: "#fff",
                fontSize: "0.85rem",
              }}
            >
              <option value="ALL">All Test Suites</option>
              <option value="SUITE-ORDER-PRICING">Order Calculation & Pricing</option>
              <option value="SUITE-PAYMENT-GATEWAY">Payment Gateway Integration</option>
              <option value="SUITE-LOYALTY-ENGINE">Customer Loyalty Engine</option>
            </select>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              style={{
                background: "rgba(17, 24, 39, 0.8)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "0.45rem 0.85rem",
                color: "#fff",
                fontSize: "0.85rem",
              }}
            >
              <option value="ALL">All Types</option>
              <option value="AUTOMATED">Automated</option>
              <option value="MANUAL">Manual</option>
              <option value="REGRESSION">Regression</option>
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                background: "rgba(17, 24, 39, 0.8)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "0.45rem 0.85rem",
                color: "#fff",
                fontSize: "0.85rem",
              }}
            >
              <option value="ALL">All Statuses</option>
              <option value="PASSED">Passed</option>
              <option value="FAILED">Failed</option>
              <option value="BLOCKED">Blocked</option>
              <option value="READY">Ready</option>
            </select>
          </div>

          {/* Grouped Test Cases Accordion / List */}
          <div style={{ marginTop: "1rem" }}>
            {Object.keys(suiteGroups).length === 0 ? (
              <p className="empty-state">No test cases match the active filters.</p>
            ) : (
              Object.entries(suiteGroups).map(([suiteName, cases]) => (
                <div key={suiteName} style={{ marginBottom: "1.5rem" }}>
                  <div className="test-suite-header">
                    <div>
                      <strong style={{ color: "#fff", fontSize: "0.95rem" }}>{suiteName}</strong>
                      <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginLeft: "0.75rem" }}>
                        ({cases.length} test cases)
                      </span>
                    </div>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
                    {cases.map((tc) => (
                      <div key={tc.test_case_id} className="test-case-item">
                        <div className="test-case-topline">
                          <div>
                            <code style={{ color: "var(--electric-blue)", fontWeight: 700, marginRight: "0.6rem" }}>
                              {tc.test_case_id}
                            </code>
                            <span className="badge badge--platform" style={{ marginRight: "0.4rem" }}>{tc.test_type}</span>
                            <span className="badge badge--priority" style={{ marginRight: "0.4rem" }}>{tc.priority}</span>
                            <strong style={{ color: "#fff", fontSize: "0.95rem" }}>{tc.title}</strong>
                          </div>
                          <span
                            className={`badge ${
                              tc.status === "PASSED"
                                ? "badge--success"
                                : tc.status === "FAILED"
                                ? "badge--danger"
                                : tc.status === "BLOCKED"
                                ? "badge--warning"
                                : "badge--platform"
                            }`}
                          >
                            {tc.status}
                          </span>
                        </div>

                        <p style={{ margin: "0.4rem 0", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                          {tc.description}
                        </p>

                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", background: "rgba(0,0,0,0.25)", padding: "0.6rem 0.75rem", borderRadius: "6px", margin: "0.5rem 0", fontSize: "0.8rem" }}>
                          <div>
                            <span style={{ color: "var(--text-muted)", display: "block" }}>Preconditions:</span>
                            <span style={{ color: "var(--text-secondary)" }}>{tc.preconditions || "None specified"}</span>
                          </div>
                          <div>
                            <span style={{ color: "var(--text-muted)", display: "block" }}>Expected Result:</span>
                            <span style={{ color: "#34d399" }}>{tc.expected_result || "Standard HTTP 200 / PASS"}</span>
                          </div>
                        </div>

                        {tc.steps && (
                          <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: "0.4rem 0", whiteSpace: "pre-line" }}>
                            <strong style={{ color: "var(--text-muted)" }}>Steps:</strong> {tc.steps}
                          </div>
                        )}

                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.6rem", paddingTop: "0.5rem", borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.8rem" }}>
                            <span style={{ color: "var(--electric-blue)", fontFamily: "monospace" }}>
                              🔗 Jira: <a href={`https://projectpulse.atlassian.net/browse/${tc.linked_jira_key}`} target="_blank" rel="noreferrer" style={{ color: "var(--electric-blue)" }}>{tc.linked_jira_key}</a>
                            </span>
                            <span style={{ color: "var(--text-muted)" }}>Assigned: {tc.assigned_to}</span>
                            {tc.last_verdict && (
                              <span style={{ color: tc.last_verdict === "PASSED" ? "#34d399" : "#f87171" }}>
                                Last Run: {tc.last_verdict} ({tc.last_executed_at ? new Date(tc.last_executed_at).toLocaleTimeString() : ""})
                              </span>
                            )}
                          </div>

                          <div className="exec-btn-group">
                            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginRight: "0.25rem" }}>Inline Run:</span>
                            <button type="button" className="btn-exec btn-exec--pass" onClick={() => handleExecuteCase(tc.test_case_id, "PASSED")}>✓ Pass</button>
                            <button type="button" className="btn-exec btn-exec--fail" onClick={() => handleExecuteCase(tc.test_case_id, "FAILED")}>✕ Fail</button>
                            <button type="button" className="btn-exec btn-exec--block" onClick={() => handleExecuteCase(tc.test_case_id, "BLOCKED")}>⊘ Block</button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      )}

      {/* TAB 3: TEST FAILURE-TO-JIRA DEFECT LINKING & DRAFTS */}
      {activeTab === "defect-linking" && (
        <section className="card">
          <div className="card__header-row">
            <div>
              <h2>Test Failure-to-Jira Defect Linking</h2>
              <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                Connect test failures to verified Jira issues. Defect drafts allow testers to review failure evidence before syncing, avoiding duplicate tickets.
              </p>
            </div>
            <button
              type="button"
              className="btn-primary"
              onClick={() => setShowDraftModal(true)}
            >
              + Author Defect Draft
            </button>
          </div>

          {/* Active Defect Drafts for Review */}
          <div style={{ marginTop: "1.25rem" }}>
            <h3 style={{ fontSize: "0.95rem", color: "#fff", marginBottom: "0.75rem" }}>
              Pending Defect Drafts for Tester Review ({defectDrafts.length})
            </h3>

            {defectDrafts.length === 0 ? (
              <p className="empty-state">No pending defect drafts. All failures are resolved or linked.</p>
            ) : (
              defectDrafts.map((draft) => (
                <div key={draft.draft_id} className="defect-draft-card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <code style={{ color: "#f87171", fontWeight: 700, marginRight: "0.5rem" }}>{draft.draft_id}</code>
                      <span className="badge badge--danger" style={{ marginRight: "0.5rem" }}>{draft.severity}</span>
                      <span className="badge badge--priority" style={{ marginRight: "0.5rem" }}>{draft.priority}</span>
                      <strong style={{ color: "#fff", fontSize: "1rem" }}>{draft.title}</strong>
                    </div>
                    <span className="badge badge--warning">STATUS: {draft.status}</span>
                  </div>

                  <p style={{ margin: "0.5rem 0", fontSize: "0.88rem", color: "var(--text-secondary)" }}>
                    {draft.description}
                  </p>

                  {draft.stack_trace && (
                    <div>
                      <span style={{ fontSize: "0.76rem", color: "var(--text-muted)", fontWeight: 700 }}>
                        STACK TRACE & FAILURE LOGS:
                      </span>
                      <pre className="stack-trace-box">{draft.stack_trace}</pre>
                    </div>
                  )}

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.75rem" }}>
                    <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                      <span>Linked Jira Ticket: </span>
                      <code style={{ color: "var(--electric-blue)", fontWeight: 700 }}>{draft.linked_jira_issue || "KAN-4"}</code>
                      <span style={{ marginLeft: "1rem", color: "var(--text-muted)" }}>Author: {draft.created_by}</span>
                    </div>

                    <div style={{ display: "flex", gap: "0.6rem" }}>
                      <button
                        type="button"
                        className="btn-exec btn-exec--fail"
                        onClick={() => handleDeleteDraft(draft.draft_id)}
                      >
                        Dismiss / Reject Draft
                      </button>
                      <button
                        type="button"
                        className="btn-exec btn-exec--pass"
                        onClick={() => handleConfirmDraft(draft.draft_id)}
                      >
                        ✓ Confirm & Promote to Jira Ticket
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Open Defects currently in system */}
          <div style={{ marginTop: "2rem" }}>
            <h3 style={{ fontSize: "0.95rem", color: "#fff", marginBottom: "0.75rem" }}>
              Active Verified Defects in Jira ({data.open_defects?.length || 0})
            </h3>
            <div className="table-responsive">
              <table className="agents-table">
                <thead>
                  <tr>
                    <th>Defect ID</th>
                    <th>Title</th>
                    <th>Severity</th>
                    <th>Linked Jira Key</th>
                    <th>Status</th>
                    <th>Reported By</th>
                  </tr>
                </thead>
                <tbody>
                  {data.open_defects?.map((d) => (
                    <tr key={d.defect_id}>
                      <td><code style={{ color: "#f87171" }}>{d.defect_id}</code></td>
                      <td><strong style={{ color: "#fff" }}>{d.title}</strong></td>
                      <td><span className={`badge ${d.severity === "CRITICAL" ? "badge--danger" : "badge--warning"}`}>{d.severity}</span></td>
                      <td><code style={{ color: "var(--electric-blue)" }}>{d.related_task_id || "KAN-4"}</code></td>
                      <td><span className="badge badge--success">{d.status}</span></td>
                      <td style={{ color: "var(--text-secondary)" }}>{d.reported_by}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* TAB 4: AUTOMATED BROWSER TESTS (SELENIUM & TESTNG) */}
      {activeTab === "selenium" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {/* Environment Status & Configuration Bar */}
          <section className="card" style={{ borderLeft: "4px solid #38bdf8" }}>
            <div className="card__header-row" style={{ flexWrap: "wrap", gap: "1rem" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: "1.2rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  🌐 Selenium WebDriver & TestNG Automation Environment
                </h2>
                <p style={{ margin: "0.35rem 0 0", fontSize: "0.84rem", color: "var(--text-secondary)" }}>
                  Target Project: <code>{seleniumData?.environment?.test_project_path || "showcase_project/selenium-tests"}</code>
                </p>
              </div>
              <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", alignItems: "center" }}>
                <span className={`status-pill ${seleniumData?.environment?.java_installed ? "status-pill--active" : "status-pill--warning"}`}>
                  ☕ Java: {seleniumData?.environment?.java_installed ? "Java 17 OpenJDK (LTS)" : "Java Missing"}
                </span>
                <span className={`status-pill ${seleniumData?.environment?.maven_installed ? "status-pill--active" : "status-pill--warning"}`}>
                  📦 Maven: {seleniumData?.environment?.maven_installed ? "Apache Maven 3.9" : "Maven Missing"}
                </span>
                <span className={`status-pill ${seleniumData?.environment?.chrome_installed ? "status-pill--active" : "status-pill--warning"}`}>
                  🌐 Chrome: {seleniumData?.environment?.chrome_installed ? "Google Chrome" : "Chrome Missing"}
                </span>
                <button type="button" className="btn-secondary" onClick={loadSeleniumData} style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}>
                  ↻ Refresh Runs
                </button>
              </div>
            </div>

            {seleniumData?.environment?.missing_prerequisites?.length > 0 && (
              <div style={{ marginTop: "1rem", padding: "0.85rem", background: "rgba(239, 68, 68, 0.12)", border: "1px solid #ef4444", borderRadius: "8px" }}>
                <strong style={{ color: "#f87171" }}>Prerequisites Required:</strong>
                <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.2rem", color: "#fca5a5", fontSize: "0.85rem" }}>
                  {seleniumData.environment.missing_prerequisites.map((p, idx) => (
                    <li key={idx}>{p}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          {/* Test Execution Control Station */}
          <section className="card">
            <div className="card__header-row">
              <div>
                <h3 style={{ margin: 0, fontSize: "1.05rem", color: "#f8fafc" }}>Execute Browser Automation Suite</h3>
                <p style={{ margin: "0.2rem 0 0", fontSize: "0.82rem", color: "var(--text-muted)" }}>
                  Spawns a sandboxed subprocess executing <code>mvn clean test</code> with real Chrome WebDriver.
                </p>
              </div>
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", alignItems: "center", marginTop: "1rem", padding: "1rem", background: "#090d16", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", color: "#e2e8f0", fontSize: "0.9rem" }}>
                <input
                  type="checkbox"
                  checked={seleniumOptions.headless}
                  onChange={(e) => setSeleniumOptions({ ...seleniumOptions, headless: e.target.checked })}
                />
                <strong>Headless Mode</strong> (Fast execution without desktop window)
              </label>

              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Browser:</span>
                <select
                  value={seleniumOptions.browser}
                  onChange={(e) => setSeleniumOptions({ ...seleniumOptions, browser: e.target.value })}
                  style={{ padding: "0.35rem 0.65rem", background: "#1e293b", color: "#fff", border: "1px solid var(--border-subtle)", borderRadius: "6px" }}
                >
                  <option value="chrome">Google Chrome (Default)</option>
                </select>
              </div>

              <div style={{ flex: "1 1 250px", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Test URL:</span>
                <input
                  type="text"
                  placeholder="Defaults to demo_page.html"
                  value={seleniumOptions.test_url}
                  onChange={(e) => setSeleniumOptions({ ...seleniumOptions, test_url: e.target.value })}
                  style={{ flex: 1, padding: "0.35rem 0.65rem", background: "#1e293b", color: "#fff", border: "1px solid var(--border-subtle)", borderRadius: "6px" }}
                />
              </div>

              <button
                type="button"
                className="btn-primary"
                disabled={seleniumRunning || !seleniumData?.environment?.is_ready}
                onClick={handleRunSeleniumSuite}
                style={{ padding: "0.55rem 1.25rem", fontWeight: 700, fontSize: "0.92rem" }}
              >
                {seleniumRunning ? "⏳ Executing Browser Tests..." : "▶ Run Selenium Suite"}
              </button>
            </div>
          </section>

          {/* Latest Execution Summary or Empty State */}
          {selectedRun ? (
            <>
              <section className="card">
                <div className="card__header-row">
                  <div>
                    <span className="badge badge--pill badge--platform" style={{ marginBottom: "0.4rem", display: "inline-block" }}>
                      Run ID: <code>{selectedRun.run_id}</code>
                    </span>
                    <h3 style={{ margin: 0, fontSize: "1.15rem", color: "#fff" }}>{selectedRun.suite_name}</h3>
                    <p style={{ margin: "0.25rem 0 0", fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      Executed: <strong>{new Date(selectedRun.created_at).toLocaleString()}</strong> by <strong>{selectedRun.executed_by}</strong> | Browser: <strong>{selectedRun.browser}</strong> ({selectedRun.headless ? "Headless" : "Visible"}) | Duration: <strong>{selectedRun.duration_seconds}s</strong>
                    </p>
                  </div>
                  <div>
                    <span className={`badge ${selectedRun.status === "SUCCESS" ? "badge--success" : selectedRun.status === "FAILED" ? "badge--danger" : "badge--warning"}`} style={{ fontSize: "0.95rem", padding: "0.4rem 0.85rem" }}>
                      {selectedRun.status === "SUCCESS" ? "✓ ALL TESTS PASSED" : selectedRun.status === "FAILED" ? "✗ TEST FAILURES DETECTED" : "⚠ " + selectedRun.status}
                    </span>
                  </div>
                </div>

                {/* Stat Grid */}
                <div className="stat-grid" style={{ marginTop: "1rem" }}>
                  <StatCard label="Total Executed" value={selectedRun.total_tests} tone="neutral" />
                  <StatCard label="Passed" value={selectedRun.passed_tests} tone="good" />
                  <StatCard label="Failed" value={selectedRun.failed_tests} tone={selectedRun.failed_tests > 0 ? "bad" : "neutral"} />
                  <StatCard label="Skipped" value={selectedRun.skipped_tests} tone="neutral" />
                  <StatCard label="Pass Rate" value={`${selectedRun.pass_rate}%`} tone={selectedRun.pass_rate >= 80 ? "good" : "bad"} />
                  <StatCard label="Exit Code" value={selectedRun.exit_code} tone={selectedRun.exit_code === 0 ? "good" : "bad"} />
                </div>
              </section>

              {/* Individual Test-Method Results */}
              <section className="card">
                <div className="card__header-row">
                  <h2>Individual Test Method Outcomes (TestNG)</h2>
                  <span className="badge badge--pill">{selectedRun.test_methods?.length || 0} Test Methods</span>
                </div>
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Status</th>
                        <th>Test Method</th>
                        <th>Class</th>
                        <th>Duration</th>
                        <th>Details / Error Trace</th>
                        <th>Jira Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedRun.test_methods?.map((m, idx) => (
                        <tr key={idx}>
                          <td>
                            <span className={`badge ${m.status === "PASS" ? "badge--success" : m.status === "FAIL" ? "badge--danger" : "badge--warning"}`}>
                              {m.status}
                            </span>
                          </td>
                          <td>
                            <strong style={{ color: "#fff" }}>{m.name}</strong>
                            {m.description && <p style={{ margin: "0.15rem 0 0", fontSize: "0.78rem", color: "var(--text-muted)" }}>{m.description}</p>}
                          </td>
                          <td>
                            <code style={{ fontSize: "0.8rem", color: "var(--electric-blue)" }}>{m.class_name.split(".").pop()}</code>
                          </td>
                          <td style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                            {m.duration_seconds}s
                          </td>
                          <td>
                            {m.error_message ? (
                              <div style={{ maxWidth: "420px" }}>
                                <p style={{ margin: 0, color: "#f87171", fontSize: "0.82rem", fontWeight: 600 }}>{m.error_message}</p>
                                {m.stack_trace && (
                                  <details style={{ marginTop: "0.3rem" }}>
                                    <summary style={{ fontSize: "0.75rem", color: "var(--text-muted)", cursor: "pointer" }}>View Stack Trace</summary>
                                    <pre style={{ margin: "0.3rem 0 0", padding: "0.5rem", background: "#090d16", color: "#fca5a5", fontSize: "0.72rem", overflowX: "auto", maxHeight: "150px" }}>
                                      {m.stack_trace}
                                    </pre>
                                  </details>
                                )}
                              </div>
                            ) : (
                              <span style={{ color: "var(--text-dim)", fontSize: "0.82rem" }}>✓ Assertion Passed Cleanly</span>
                            )}
                          </td>
                          <td>
                            {m.status === "FAIL" ? (
                              <button
                                type="button"
                                className="btn-secondary"
                                style={{ fontSize: "0.78rem", padding: "0.25rem 0.6rem", borderColor: "#f87171", color: "#fca5a5" }}
                                onClick={() => setJiraLinkModal({
                                  show: true,
                                  runId: selectedRun.run_id,
                                  testName: `${m.class_name}::${m.name}`,
                                  failureMsg: m.error_message || "Assertion failed during browser test",
                                  jiraKey: "PP-3",
                                })}
                              >
                                🔗 Link to Jira Defect
                              </button>
                            ) : (
                              <span style={{ color: "var(--text-dim)", fontSize: "0.78rem" }}>—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          ) : (
            <div className="card" style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
              <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>🌐</div>
              <h3 style={{ margin: 0, color: "#fff" }}>No Selenium Test Runs Recorded Yet</h3>
              <p style={{ maxWidth: "540px", margin: "0.5rem auto 1.5rem", color: "var(--text-secondary)", fontSize: "0.88rem" }}>
                Execute the automated suite above to launch Chrome WebDriver against <code>showcase_project/selenium-tests</code>, or run <code>mvn test</code> in your terminal. All TestNG XML reports are automatically ingested by the Desktop Agent.
              </p>
              <button
                type="button"
                className="btn-primary"
                disabled={seleniumRunning || !seleniumData?.environment?.is_ready}
                onClick={handleRunSeleniumSuite}
              >
                {seleniumRunning ? "⏳ Executing Suite..." : "▶ Run First Selenium Test Suite"}
              </button>
            </div>
          )}

          {/* Historical Test Runs List */}
          {seleniumData?.runs?.length > 1 && (
            <section className="card">
              <div className="card__header-row">
                <h2>Historical Browser Test Executions</h2>
                <span className="badge badge--pill">{seleniumData.runs.length} Saved Executions</span>
              </div>
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Run ID</th>
                      <th>Executed At</th>
                      <th>Status</th>
                      <th>Results (Pass/Fail)</th>
                      <th>Duration</th>
                      <th>Command</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {seleniumData.runs.map((r) => (
                      <tr key={r.run_id} style={{ background: selectedRun?.run_id === r.run_id ? "rgba(56, 189, 248, 0.08)" : "transparent" }}>
                        <td><code style={{ color: "var(--electric-blue)" }}>{r.run_id}</code></td>
                        <td>{new Date(r.created_at).toLocaleString()}</td>
                        <td>
                          <span className={`badge ${r.status === "SUCCESS" ? "badge--success" : r.status === "FAILED" ? "badge--danger" : "badge--warning"}`}>
                            {r.status}
                          </span>
                        </td>
                        <td>
                          <strong style={{ color: r.failed_tests > 0 ? "#f87171" : "#34d399" }}>
                            {r.passed_tests}/{r.total_tests} passed
                          </strong>
                          {r.failed_tests > 0 && <span style={{ color: "#f87171", marginLeft: "0.4rem" }}>({r.failed_tests} failed)</span>}
                        </td>
                        <td>{r.duration_seconds}s</td>
                        <td><code style={{ fontSize: "0.75rem" }}>{r.command}</code></td>
                        <td>
                          <button
                            type="button"
                            className="btn-secondary"
                            style={{ fontSize: "0.78rem", padding: "0.2rem 0.55rem" }}
                            onClick={() => setSelectedRun(r)}
                          >
                            Inspect ➔
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>
      )}

      {/* CREATE TEST CASE MODAL */}
      {showCreateModal && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: "680px" }}>
            <div className="modal__header">
              <h2>Author New Test Case</h2>
              <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateCaseSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Verify Stripe Checkout Session Webhook Idempotency"
                  value={newCase.title}
                  onChange={(e) => setNewCase({ ...newCase, title: e.target.value })}
                  style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Suite Name</label>
                  <select
                    value={newCase.suite_name}
                    onChange={(e) => {
                      const name = e.target.value;
                      const id = name.includes("Payment") ? "SUITE-PAYMENT-GATEWAY" : name.includes("Loyalty") ? "SUITE-LOYALTY-ENGINE" : "SUITE-ORDER-PRICING";
                      setNewCase({ ...newCase, suite_name: name, suite_id: id });
                    }}
                    style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                  >
                    <option value="Order Calculation & Pricing Engine">Order Calculation & Pricing Engine</option>
                    <option value="Payment Gateway Integration">Payment Gateway Integration</option>
                    <option value="Customer Loyalty Engine">Customer Loyalty Engine</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Test Type</label>
                  <select
                    value={newCase.test_type}
                    onChange={(e) => setNewCase({ ...newCase, test_type: e.target.value })}
                    style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                  >
                    <option value="AUTOMATED">Automated</option>
                    <option value="MANUAL">Manual</option>
                    <option value="REGRESSION">Regression</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Priority</label>
                  <select
                    value={newCase.priority}
                    onChange={(e) => setNewCase({ ...newCase, priority: e.target.value })}
                    style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                  >
                    <option value="CRITICAL">Critical</option>
                    <option value="HIGH">High</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="LOW">Low</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Linked Jira Key</label>
                  <input
                    type="text"
                    value={newCase.linked_jira_key}
                    placeholder="e.g. KAN-1 or KAN-4"
                    onChange={(e) => setNewCase({ ...newCase, linked_jira_key: e.target.value })}
                    style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Preconditions</label>
                <input
                  type="text"
                  placeholder="e.g. Stripe mock server running; customer order created"
                  value={newCase.preconditions}
                  onChange={(e) => setNewCase({ ...newCase, preconditions: e.target.value })}
                  style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Steps to Execute</label>
                <textarea
                  rows="3"
                  placeholder="1. Send checkout session webhook with ID evt_123&#10;2. Resend identical webhook within 50ms&#10;3. Verify HTTP 200 idempotent response"
                  value={newCase.steps}
                  onChange={(e) => setNewCase({ ...newCase, steps: e.target.value })}
                  style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Expected Result</label>
                <input
                  type="text"
                  placeholder="e.g. Second webhook returns 200 with idempotent response; no double charge"
                  value={newCase.expected_result}
                  onChange={(e) => setNewCase({ ...newCase, expected_result: e.target.value })}
                  style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "0.75rem" }}>
                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary">Save Test Case</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE DEFECT DRAFT MODAL */}
      {showDraftModal && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: "680px" }}>
            <div className="modal__header">
              <h2>Draft Defect for Jira Review</h2>
              <button type="button" className="btn-secondary" onClick={() => setShowDraftModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateDraftSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Defect Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Payment webhook drops confirmations under concurrency > 10 req/sec"
                  value={newDraft.title}
                  onChange={(e) => setNewDraft({ ...newDraft, title: e.target.value })}
                  style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Severity</label>
                  <select
                    value={newDraft.severity}
                    onChange={(e) => setNewDraft({ ...newDraft, severity: e.target.value })}
                    style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                  >
                    <option value="CRITICAL">Critical</option>
                    <option value="HIGH">High</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="LOW">Low</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Link to Jira Issue</label>
                  <input
                    type="text"
                    value={newDraft.linked_jira_issue}
                    placeholder="e.g. KAN-4"
                    onChange={(e) => setNewDraft({ ...newDraft, linked_jira_issue: e.target.value })}
                    style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Description</label>
                <textarea
                  rows="3"
                  placeholder="Describe failure conditions, observed behavior, and impact..."
                  value={newDraft.description}
                  onChange={(e) => setNewDraft({ ...newDraft, description: e.target.value })}
                  style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Stack Trace / Error Output</label>
                <textarea
                  rows="4"
                  placeholder="Paste stack trace or pytest failure assertions..."
                  value={newDraft.stack_trace}
                  onChange={(e) => setNewDraft({ ...newDraft, stack_trace: e.target.value })}
                  style={{ width: "100%", padding: "0.55rem", background: "#090d16", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#f87171", fontFamily: "monospace", fontSize: "0.8rem" }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "0.75rem" }}>
                <button type="button" className="btn-secondary" onClick={() => setShowDraftModal(false)}>Cancel</button>
                <button type="submit" className="btn-primary">Save Defect Draft</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* JIRA LINKING MODAL FOR SELENIUM FAILURES */}
      {jiraLinkModal.show && (
        <div className="modal-backdrop">
          <div className="modal" style={{ maxWidth: "560px" }}>
            <div className="modal__header">
              <h2>Link Browser Test Failure to Jira Defect</h2>
              <button type="button" className="btn-secondary" onClick={() => setJiraLinkModal({ ...jiraLinkModal, show: false })}>✕</button>
            </div>
            <form onSubmit={handleLinkJiraSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Test Name</label>
                <input
                  type="text"
                  readOnly
                  value={jiraLinkModal.testName}
                  style={{ width: "100%", padding: "0.55rem", background: "#090d16", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "var(--electric-blue)", fontFamily: "monospace" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Failure Message</label>
                <textarea
                  rows="3"
                  readOnly
                  value={jiraLinkModal.failureMsg}
                  style={{ width: "100%", padding: "0.55rem", background: "#090d16", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#f87171", fontFamily: "monospace", fontSize: "0.8rem" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Real Jira Issue Key (e.g. PP-3, PP-1)</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. PP-3"
                  value={jiraLinkModal.jiraKey}
                  onChange={(e) => setJiraLinkModal({ ...jiraLinkModal, jiraKey: e.target.value.toUpperCase() })}
                  style={{ width: "100%", padding: "0.55rem", background: "#0f172a", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "#fff", fontWeight: 700 }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "0.75rem" }}>
                <button type="button" className="btn-secondary" onClick={() => setJiraLinkModal({ ...jiraLinkModal, show: false })}>Cancel</button>
                <button type="submit" className="btn-primary">Confirm & Link to Jira</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

