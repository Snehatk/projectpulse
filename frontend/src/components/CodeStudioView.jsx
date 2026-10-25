import { useCallback, useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  listWorkspaceFiles,
  readWorkspaceFile,
  saveWorkspaceFile,
  runWorkspaceTests,
  getActiveChangeSet,
  listTrackedErrors,
  getGitStatus,
  finalizeChangeSet,
  syncChangeSet,
} from "../api/client";

export default function CodeStudioView({ projectId = "PP", userId = "DEV-001" }) {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState("src/app.py");
  const [fileContent, setFileContent] = useState("");
  const [initialContent, setInitialContent] = useState("");
  const [fileLanguage, setFileLanguage] = useState("python");
  const [loadingFile, setLoadingFile] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");

  // Change Set & Git State
  const [activeChangeSet, setActiveChangeSet] = useState(null);
  const [errors, setErrors] = useState([]);
  const [gitStatus, setGitStatus] = useState(null);
  const [testResult, setTestResult] = useState(null);

  // Review & Finalize Modal
  const [showFinalizeModal, setShowFinalizeModal] = useState(false);
  const [commitMessage, setCommitMessage] = useState("");
  const [finalizing, setFinalizing] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState(null);

  // Load File Tree
  const loadFiles = useCallback(async () => {
    try {
      const tree = await listWorkspaceFiles(projectId);
      setFiles(tree || []);
    } catch (err) {
      console.error("Error loading workspace files:", err);
    }
  }, [projectId]);

  // Load Active File Content
  const loadFileContent = useCallback(async (filePath) => {
    if (!filePath) return;
    try {
      setLoadingFile(true);
      const res = await readWorkspaceFile(projectId, filePath);
      setFileContent(res.content || "");
      setInitialContent(res.content || "");
      setFileLanguage(res.language || "plaintext");
      setSelectedFile(filePath);
      setSaveMessage("");
    } catch (err) {
      console.error("Error reading file:", err);
      setSaveMessage(`Failed to read file: ${err.message}`);
    } finally {
      setLoadingFile(false);
    }
  }, [projectId]);

  // Refresh Intelligence: Change Set, Errors, Git Status
  const refreshIntelligence = useCallback(async () => {
    try {
      const [cs, errList, git] = await Promise.all([
        getActiveChangeSet(projectId).catch(() => null),
        listTrackedErrors(projectId, "ALL").catch(() => []),
        getGitStatus(projectId).catch(() => null),
      ]);
      setActiveChangeSet(cs);
      setErrors(errList || []);
      setGitStatus(git);
    } catch (err) {
      console.error("Error refreshing intelligence:", err);
    }
  }, [projectId]);

  useEffect(() => {
    loadFiles();
    loadFileContent("src/app.py");
    refreshIntelligence();
    const interval = setInterval(refreshIntelligence, 8000);
    return () => clearInterval(interval);
  }, [loadFiles, loadFileContent, refreshIntelligence]);

  const hasUnsavedChanges = fileContent !== initialContent;

  // Handle Save & AST Analysis
  const handleSave = async () => {
    if (!selectedFile) return;
    setSaving(true);
    setSaveMessage("Saving and analyzing AST changes...");
    try {
      const res = await saveWorkspaceFile(projectId, {
        path: selectedFile,
        content: fileContent,
        user_id: userId,
      });
      setInitialContent(fileContent);
      setSaveMessage(res.errors_detected?.length > 0 ? "Saved! Syntax error detected." : "Saved! AST change set updated.");
      await refreshIntelligence();
    } catch (err) {
      setSaveMessage(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  // Keyboard shortcut Ctrl+S / Cmd+S
  const handleEditorKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      e.preventDefault();
      handleSave();
    }
  };

  // Handle Run Tests
  const handleRunTests = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await runWorkspaceTests(projectId, activeChangeSet?.change_set_id);
      setTestResult(res);
      await refreshIntelligence();
    } catch (err) {
      setTestResult({ success: false, output: err.message, total: 0, passed: 0, failed: 1 });
    } finally {
      setTesting(false);
    }
  };

  // Finalize & Commit Locally
  const handleFinalizeCommit = async () => {
    if (!activeChangeSet?.change_set_id) return;
    setFinalizing(true);
    setSyncFeedback(null);
    try {
      const msg = commitMessage || `Refactor: Updated ${activeChangeSet.files_modified?.join(", ")}`;
      const res = await finalizeChangeSet(projectId, activeChangeSet.change_set_id, {
        commit_message: msg,
        author_name: "Alex Rivera <alex@projectpulse.local>",
      });
      setActiveChangeSet(res);
      setSyncFeedback({ type: "success", text: `Committed successfully! Commit hash: ${res.commit_hash}` });
      await refreshIntelligence();
    } catch (err) {
      setSyncFeedback({ type: "error", text: err.message });
    } finally {
      setFinalizing(false);
    }
  };

  // Push to Remote GitHub
  const handlePushToRemote = async () => {
    if (!activeChangeSet?.change_set_id) return;
    setPushing(true);
    setSyncFeedback(null);
    try {
      const res = await syncChangeSet(projectId, activeChangeSet.change_set_id);
      if (res.success) {
        setSyncFeedback({ type: "success", text: `Pushed to GitHub! Commit: ${res.commit_hash}` });
      } else {
        setSyncFeedback({ type: "warning", text: res.message });
      }
      await refreshIntelligence();
    } catch (err) {
      setSyncFeedback({ type: "error", text: err.message });
    } finally {
      setPushing(false);
    }
  };

  // Helper for status badge
  const getStatusBadgeClass = (status) => {
    switch (status) {
      case "SYNCED":
        return "badge--synced";
      case "FINALIZED":
        return "badge--finalized";
      case "READY_FOR_REVIEW":
        return "badge--ready";
      case "NEEDS_ATTENTION":
        return "badge--attention";
      case "SYNC_FAILED":
        return "badge--sync-failed";
      default:
        return "badge--in-progress";
    }
  };

  // Flat file list rendering
  const flattenFiles = (nodes, prefix = "") => {
    let list = [];
    for (const n of nodes) {
      if (n.is_dir && n.children) {
        list = list.concat(flattenFiles(n.children, `${prefix}${n.name}/`));
      } else {
        list.push(n);
      }
    }
    return list;
  };
  const flatFileList = flattenFiles(files);

  const openErrors = errors.filter((e) => e.status === "OPEN");
  const resolvedErrors = errors.filter((e) => e.status === "RESOLVED");

  return (
    <div className="code-studio" onKeyDown={handleEditorKeyDown}>
      {/* Top Studio Control Bar */}
      <div className="code-studio__toolbar">
        <div className="code-studio__toolbar-left">
          <span className="code-studio__tag">⚡ LIVE CODE STUDIO</span>
          <span className="code-studio__filename">
            {selectedFile} {hasUnsavedChanges && <span className="unsaved-indicator" title="Unsaved changes">● Unsaved</span>}
          </span>
          <span className="code-studio__lang">{fileLanguage}</span>
        </div>
        <div className="code-studio__toolbar-actions">
          {saveMessage && <span className="code-studio__save-msg">{saveMessage}</span>}
          <button
            type="button"
            className="btn-secondary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "Saving..." : "💾 Save & Analyze (Ctrl+S)"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleRunTests}
            disabled={testing}
          >
            {testing ? "Running Tests..." : "🧪 Run Verification Tests"}
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => {
              setCommitMessage(`Refactor(${selectedFile.split("/").pop()}): ${activeChangeSet?.title || "Code updates"}`);
              setShowFinalizeModal(true);
            }}
          >
            🚀 Review & Finalize Git Changes
          </button>
        </div>
      </div>

      {/* Main 3-Column Studio Grid */}
      <div className="code-studio__grid">
        {/* Left Column: Workspace File Explorer */}
        <aside className="code-studio__files-panel">
          <div className="panel-title">
            <span>📁 Project Files</span>
            <button type="button" className="icon-btn" onClick={loadFiles} title="Refresh File Tree">↻</button>
          </div>
          <div className="files-list">
            {flatFileList.map((f) => (
              <button
                key={f.path}
                type="button"
                className={`file-item ${selectedFile === f.path ? "file-item--active" : ""}`}
                onClick={() => loadFileContent(f.path)}
              >
                <span className="file-icon">{f.path.endsWith(".py") ? "🐍" : f.path.endsWith(".json") ? "📋" : "📄"}</span>
                <span className="file-name">{f.path}</span>
                {f.size > 0 && <span className="file-size">{(f.size / 1024).toFixed(1)}k</span>}
              </button>
            ))}
          </div>
        </aside>

        {/* Center Column: Monaco Code Editor */}
        <section className="code-studio__editor-panel">
          {loadingFile ? (
            <div className="editor-loading">Loading file content...</div>
          ) : (
            <Editor
              height="100%"
              language={fileLanguage}
              theme="vs-dark"
              value={fileContent}
              onChange={(val) => setFileContent(val || "")}
              options={{
                fontSize: 14,
                fontFamily: "'Fira Code', 'JetBrains Mono', Consolas, monospace",
                minimap: { enabled: true },
                automaticLayout: true,
                tabSize: 4,
                scrollBeyondLastLine: false,
                lineNumbers: "on",
                renderLineHighlight: "all",
              }}
            />
          )}
        </section>

        {/* Right Column: Change Intelligence & Git Status */}
        <aside className="code-studio__intel-panel">
          {/* Active Change Set Card */}
          <div className="intel-card">
            <div className="intel-card__header">
              <span className="intel-card__title">📦 Active Change Set</span>
              <span className={`status-badge ${getStatusBadgeClass(activeChangeSet?.status)}`}>
                {activeChangeSet?.status || "IN_PROGRESS"}
              </span>
            </div>
            <div className="intel-card__body">
              <div className="info-row">
                <span className="info-label">ID:</span>
                <span className="info-value font-mono">{activeChangeSet?.change_set_id || "None"}</span>
              </div>
              <div className="info-row">
                <span className="info-label">Title:</span>
                <span className="info-value">{activeChangeSet?.title || "Working session"}</span>
              </div>
              <div className="info-row">
                <span className="info-label">Modified:</span>
                <span className="info-value">{activeChangeSet?.files_modified?.length || 0} files</span>
              </div>
              {activeChangeSet?.symbols_impacted && activeChangeSet.symbols_impacted.length > 0 && (
                <div className="symbols-impacted">
                  <span className="info-label">Impacted Symbols:</span>
                  <div className="symbol-tags">
                    {activeChangeSet.symbols_impacted.map((sym, i) => (
                      <span key={i} className="symbol-tag">
                        {sym.name} <small>({sym.type})</small>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Centralized Error and Test Monitoring */}
          <div className="intel-card">
            <div className="intel-card__header">
              <span className="intel-card__title">
                🚨 Error & Test Monitor ({openErrors.length} Open)
              </span>
              {openErrors.length === 0 && <span className="badge--passed">● All Clear</span>}
            </div>
            <div className="intel-card__body error-monitor-body">
              {openErrors.length === 0 && resolvedErrors.length === 0 && (
                <div className="empty-notice">No detected syntax errors or test exceptions.</div>
              )}

              {/* Open Errors */}
              {openErrors.map((err) => (
                <div key={err.error_id} className={`error-item error-item--${err.severity?.toLowerCase()}`}>
                  <div className="error-item__head">
                    <span className="error-item__type">[{err.error_type}]</span>
                    <span className="error-item__severity">{err.severity}</span>
                  </div>
                  <div className="error-item__msg">{err.message}</div>
                  {err.file_path && (
                    <div className="error-item__loc">
                      {err.file_path} {err.line_number ? `: Line ${err.line_number}` : ""}
                    </div>
                  )}
                  {err.details && <pre className="error-item__details">{err.details}</pre>}
                </div>
              ))}

              {/* Recently Verified / Resolved */}
              {resolvedErrors.slice(0, 2).map((err) => (
                <div key={err.error_id} className="error-item error-item--resolved">
                  <div className="error-item__head">
                    <span className="error-item__type">[{err.error_type}]</span>
                    <span className="badge--verified">✓ Verified Resolved ({err.verification_method})</span>
                  </div>
                  <div className="error-item__msg">{err.message}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Test Execution Output */}
          {testResult && (
            <div className="intel-card">
              <div className="intel-card__header">
                <span className="intel-card__title">🧪 Test Verification</span>
                <span className={testResult.success ? "badge--passed" : "badge--attention"}>
                  {testResult.passed} Passed / {testResult.failed} Failed ({testResult.duration_sec}s)
                </span>
              </div>
              <pre className="test-output-box">{testResult.output}</pre>
            </div>
          )}

          {/* Controlled Git Synchronization Card */}
          <div className="intel-card">
            <div className="intel-card__header">
              <span className="intel-card__title">🐙 Git & Remote Tracking</span>
              <span className="git-branch-tag">⎇ {gitStatus?.branch || "main"}</span>
            </div>
            <div className="intel-card__body">
              <div className="info-row">
                <span className="info-label">Working Tree:</span>
                <span className="info-value">{gitStatus?.is_clean ? "Clean" : `${gitStatus?.uncommitted_files?.length || 0} modified`}</span>
              </div>
              <div className="info-row">
                <span className="info-label">Sync Rule:</span>
                <span className="info-value text-accent">Controlled (Explicit Approval Only)</span>
              </div>
              {gitStatus?.recent_commits && gitStatus.recent_commits.length > 0 && (
                <div className="recent-commits">
                  <span className="info-label">Latest Commit:</span>
                  <div className="commit-entry">
                    <code>{gitStatus.recent_commits[0].hash}</code> {gitStatus.recent_commits[0].message}
                  </div>
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>

      {/* Review & Finalize Approval Modal */}
      {showFinalizeModal && (
        <div className="modal-backdrop" onClick={() => setShowFinalizeModal(false)}>
          <div className="modal-box modal-box--large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>🚀 Review, Finalize & Synchronize Code Changes</h3>
              <button type="button" className="close-btn" onClick={() => setShowFinalizeModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p className="modal-description">
                ProjectPulse AI strictly prevents premature auto-pushes. Review your accumulated change set, inspect verification checks, and approve the commit.
              </p>

              {/* Verification Checklist */}
              <div className="verification-checklist">
                <div className={`check-item ${openErrors.length === 0 ? "check-item--pass" : "check-item--fail"}`}>
                  <span className="check-icon">{openErrors.length === 0 ? "✓" : "✗"}</span>
                  <span>Syntax & Compiler Checks: {openErrors.length === 0 ? "0 Outstanding Errors" : `${openErrors.length} Blocking Error(s)`}</span>
                </div>
                <div className="check-item check-item--pass">
                  <span className="check-icon">✓</span>
                  <span>Impacted Files: {activeChangeSet?.files_modified?.join(", ") || selectedFile}</span>
                </div>
                <div className="check-item check-item--pass">
                  <span className="check-icon">✓</span>
                  <span>Local Branch: <code>{gitStatus?.branch || "main"}</code></span>
                </div>
              </div>

              {/* Commit Message Input */}
              <div className="form-group">
                <label htmlFor="commitMsgInput">Commit Message (Required for Git Finalization):</label>
                <textarea
                  id="commitMsgInput"
                  rows="3"
                  className="input-textarea"
                  value={commitMessage}
                  onChange={(e) => setCommitMessage(e.target.value)}
                  placeholder="e.g. feat(order): add loyalty points calculation and input validation"
                />
              </div>

              {syncFeedback && (
                <div className={`feedback-alert feedback-alert--${syncFeedback.type}`}>
                  {syncFeedback.text}
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button type="button" className="btn-secondary" onClick={() => setShowFinalizeModal(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={handleFinalizeCommit}
                disabled={finalizing || openErrors.length > 0}
              >
                {finalizing ? "Committing..." : "1. ✅ Commit Locally (Finalize)"}
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={handlePushToRemote}
                disabled={pushing || activeChangeSet?.status !== "FINALIZED"}
              >
                {pushing ? "Pushing to GitHub..." : "2. 🚀 Push Approved Commit to GitHub"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
