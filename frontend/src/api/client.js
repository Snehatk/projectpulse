const API_BASE = import.meta.env.VITE_API_BASE || "";

async function fetchJson(path, options = {}) {
  const token = localStorage.getItem("projectpulse_token");
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  const text = await response.text();
  let parsed = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!response.ok) {
    const detail =
      (parsed && typeof parsed === "object" ? parsed.detail : null) ||
      (typeof parsed === "string" ? parsed : null) ||
      `Request failed with status ${response.status}`;
    throw new Error(detail);
  }

  return parsed;
}

export async function getAppConfig() {
  return fetchJson("/api/config");
}

export async function getDeveloperSummary(projectId, userId) {
  const params = new URLSearchParams({ user_id: userId });
  return fetchJson(`/api/projects/${projectId}/summary?${params}`);
}

export async function getManagerDashboard(projectId) {
  const params = new URLSearchParams({ role: "PROJECT_MANAGER" });
  return fetchJson(`/api/projects/${projectId}/dashboard?${params}`);
}

export async function getAgents(projectId = "") {
  const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return fetchJson(`/api/agents${q}`);
}

export async function getTasks(projectId = "") {
  const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return fetchJson(`/api/tasks${q}`);
}

export async function createLocalTask(payload) {
  return fetchJson("/api/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getEvents(params = {}) {
  const q = new URLSearchParams(params).toString();
  return fetchJson(`/api/events${q ? `?${q}` : ""}`);
}

export async function getTestingMetrics(projectId = "") {
  return fetchJson(`/api/projects/${projectId}/testing`);
}

export async function getQAMetrics(projectId = "") {
  return fetchJson(`/api/projects/${projectId}/qa`);
}

export async function reportDefect(projectId, payload) {
  return fetchJson(`/api/projects/${projectId}/defects`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateDefectStatus(defectId, status) {
  return fetchJson(`/api/defects/${defectId}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export async function recordQAVerdict(projectId, payload) {
  return fetchJson(`/api/projects/${projectId}/qa/verdict`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getIntegrations() {
  return fetchJson("/api/integrations");
}

export async function connectIntegration(platform, payload = {}) {
  return fetchJson(`/api/integrations/${platform}/connect`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function disconnectIntegration(platform) {
  return fetchJson(`/api/integrations/${platform}/disconnect`, {
    method: "POST",
  });
}

export async function syncIntegrations(projectId = "DLX") {
  return fetchJson(`/api/integrations/sync?project_id=${encodeURIComponent(projectId)}`, {
    method: "POST",
  });
}

// AI Assistant APIs (Phases 14 & 15)
export async function getAISuggestions(projectId = "DLX") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/ai/suggestions`);
}

export async function getAIBudgetStatus() {
  return fetchJson("/api/ai/budget-status");
}

export async function chatWithAI(projectId = "DLX", query) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/ai/chat`, {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

// Task Evidence & Intelligence APIs (Features 9, 13, 20)
export async function getTaskEvidence(taskId) {
  return fetchJson(`/api/tasks/${encodeURIComponent(taskId)}/evidence`);
}

export async function getSprintAnalytics(projectId = "DLX", sprint = "Sprint 1") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/analytics?sprint=${encodeURIComponent(sprint)}`);
}

export async function getSyncHistory(projectId = "DLX") {
  return fetchJson(`/api/integrations/history?project_id=${encodeURIComponent(projectId)}`);
}

// 6 Major Extension APIs
export async function getAIRisks(projectId = "DLX") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/risks/ai`);
}

export async function getProjectAISummary(projectId = "DLX", summaryType = "project", timeframe = "24h") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/ai/summary`, {
    method: "POST",
    body: JSON.stringify({ summary_type: summaryType, timeframe }),
  });
}

export async function getTaskAISummary(taskId) {
  return fetchJson(`/api/tasks/${encodeURIComponent(taskId)}/ai/summary`, {
    method: "POST",
  });
}

export async function getUnifiedTimeline(projectId = "DLX", filter = "ALL", limit = 150) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/timeline?filter=${encodeURIComponent(filter)}&limit=${limit}`);
}

export async function getCodeExplanations(projectId = "DLX", limit = 30) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/code-explanations?limit=${limit}`);
}

export async function getJiraInfo() {
  return fetchJson("/api/integrations/jira/info");
}

export async function testJiraConnection(projectKey = null) {
  const query = projectKey ? `?project_key=${encodeURIComponent(projectKey)}` : "";
  return fetchJson(`/api/integrations/jira/test${query}`);
}

export async function connectJira(credentials) {
  return fetchJson("/api/integrations/jira/connect", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export async function getJiraProjects() {
  return fetchJson("/api/integrations/jira/projects");
}

export async function getJiraIssues(projectId = null, limit = 50, offset = 0, jql = null) {
  let url = `/api/integrations/jira/issues?limit=${limit}&offset=${offset}`;
  if (projectId) url += `&project_id=${encodeURIComponent(projectId)}`;
  if (jql) url += `&jql=${encodeURIComponent(jql)}`;
  return fetchJson(url);
}

export async function getJiraIssueDetail(issueKey) {
  return fetchJson(`/api/integrations/jira/issues/${encodeURIComponent(issueKey)}`);
}

export async function syncJiraProject(projectId = null, jiraProjectKey = null) {
  const body = {};
  if (projectId) body.project_id = projectId;
  if (jiraProjectKey) body.jira_project_key = jiraProjectKey;
  return fetchJson("/api/integrations/jira/sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// -------------------------------------------------------------
// Authentication, User Management & Device Pairing API
// -------------------------------------------------------------

export async function getAuthStatus() {
  return fetchJson("/api/auth/status");
}

export async function loginUser(email, password) {
  return fetchJson("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function setupFirstPM(payload) {
  return fetchJson("/api/auth/setup-first-pm", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getCurrentUserProfile() {
  return fetchJson("/api/auth/me");
}

export async function getTeamUsers() {
  return fetchJson("/api/auth/users");
}

export async function createTeamUser(payload) {
  return fetchJson("/api/auth/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateTeamUser(userId, payload) {
  return fetchJson(`/api/auth/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function generatePairingCode(projectId = "PP") {
  return fetchJson(`/api/auth/pair-code?project_id=${encodeURIComponent(projectId)}`, {
    method: "POST",
  });
}

export async function getPairedDevices() {
  return fetchJson("/api/auth/devices");
}

export async function revokePairedDevice(deviceId) {
  return fetchJson(`/api/auth/devices/${encodeURIComponent(deviceId)}/revoke`, {
    method: "POST",
  });
}

export async function getAuditLogs(limit = 50) {
  return fetchJson(`/api/auth/audit-logs?limit=${limit}`);
}

// -------------------------------------------------------------
// Tester Overview & Test Case Management
// -------------------------------------------------------------

export async function getTesterOverview(projectId = "KAN") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/tester-overview`);
}

export async function listTestCases(projectId = "KAN", params = {}) {
  const q = new URLSearchParams(params).toString();
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/test-cases${q ? `?${q}` : ""}`);
}

export async function createTestCase(projectId = "KAN", payload = {}) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/test-cases`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateTestCase(testCaseId, payload = {}) {
  return fetchJson(`/api/test-cases/${encodeURIComponent(testCaseId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function executeTestCase(testCaseId, verdict = "PASSED", notes = "", executedBy = "Dave Miller (QA)") {
  return fetchJson(`/api/test-cases/${encodeURIComponent(testCaseId)}/execute`, {
    method: "POST",
    body: JSON.stringify({ verdict, notes, executed_by: executedBy }),
  });
}

export async function deleteTestCase(testCaseId) {
  return fetchJson(`/api/test-cases/${encodeURIComponent(testCaseId)}`, {
    method: "DELETE",
  });
}

// -------------------------------------------------------------
// Defect Drafts & Failure Linking
// -------------------------------------------------------------

export async function listDefectDrafts(projectId = "KAN") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/defect-drafts`);
}

export async function createDefectDraft(projectId = "KAN", payload = {}) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/defect-drafts`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function confirmDefectDraft(draftId, confirmedBy = "Dave Miller (QA)") {
  const q = new URLSearchParams({ confirmed_by: confirmedBy }).toString();
  return fetchJson(`/api/defect-drafts/${encodeURIComponent(draftId)}/confirm?${q}`, {
    method: "POST",
  });
}

export async function deleteDefectDraft(draftId) {
  return fetchJson(`/api/defect-drafts/${encodeURIComponent(draftId)}`, {
    method: "DELETE",
  });
}

// -------------------------------------------------------------
// Developer Overview & AI Developer Assistant
// -------------------------------------------------------------

export async function getDeveloperOverview(projectId = "KAN", userId = "DEV-001") {
  const q = new URLSearchParams({ user_id: userId }).toString();
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/developer-overview?${q}`);
}

export async function askDeveloperAI(projectId = "KAN", payload = {}) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/developer/ai-assist`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// -------------------------------------------------------------
// Real-Time Code Tracking, Error Monitoring & Git Sync
// -------------------------------------------------------------

export async function listWorkspaceFiles(projectId = "PP") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/code/files`);
}

export async function readWorkspaceFile(projectId = "PP", path = "") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/code/file?path=${encodeURIComponent(path)}`);
}

export async function saveWorkspaceFile(projectId = "PP", payload = {}) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/code/file`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function runWorkspaceTests(projectId = "PP", changeSetId = null) {
  const q = changeSetId ? `?change_set_id=${encodeURIComponent(changeSetId)}` : "";
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/code/test-run${q}`, {
    method: "POST",
  });
}

export async function getActiveChangeSet(projectId = "PP") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/code/change-sets/active`);
}

export async function listChangeSets(projectId = "PP", limit = 15) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/code/change-sets?limit=${limit}`);
}

export async function listTrackedErrors(projectId = "PP", status = "ALL") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/code/errors?status=${encodeURIComponent(status)}`);
}

export async function getGitStatus(projectId = "PP") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/code/git-status`);
}

export async function finalizeChangeSet(projectId = "PP", changeSetId = "", payload = {}) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/code/change-sets/${encodeURIComponent(changeSetId)}/finalize`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function syncChangeSet(projectId = "PP", changeSetId = "") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/code/change-sets/${encodeURIComponent(changeSetId)}/sync`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Automated Browser Testing (Selenium + Java + TestNG)
// ---------------------------------------------------------------------------

export async function getSeleniumStatus(projectId = "PP") {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/selenium/status`);
}

export async function listSeleniumRuns(projectId = "PP", limit = 25) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/selenium/runs?limit=${limit}`);
}

export async function getSeleniumRun(runId) {
  return fetchJson(`/api/selenium/runs/${encodeURIComponent(runId)}`);
}

export async function runSeleniumSuite(projectId = "PP", payload = {}) {
  return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/selenium/run`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function linkSeleniumFailureToJira(runId, payload = {}) {
  return fetchJson(`/api/selenium/runs/${encodeURIComponent(runId)}/link-jira`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}


