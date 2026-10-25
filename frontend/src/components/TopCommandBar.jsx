import { useEffect, useState } from "react";
import { getAgents, getEvents, getJiraInfo, syncJiraProject } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function TopCommandBar({ projectId, onSearch }) {
  const { user } = useAuth();
  const [jiraConnected, setJiraConnected] = useState(false);
  const [jiraKey, setJiraKey] = useState(projectId || "PP");
  const [activeAgentsCount, setActiveAgentsCount] = useState(0);
  const [hasGitEvents, setHasGitEvents] = useState(false);
  const [hasBuildEvents, setHasBuildEvents] = useState(false);
  const [hasTestEvents, setHasTestEvents] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const refreshIndicators = () => {
    getJiraInfo()
      .then((info) => {
        if (info) {
          setJiraConnected(Boolean(info.connected));
          if (info.project_key) setJiraKey(info.project_key);
        }
      })
      .catch(() => setJiraConnected(false));

    getAgents(projectId)
      .then((agents) => {
        if (Array.isArray(agents)) {
          const active = agents.filter((a) => a.status === "ACTIVE" || a.status === "ONLINE").length;
          setActiveAgentsCount(active);
        }
      })
      .catch(() => setActiveAgentsCount(0));

    // Ground-truth check: verify if real events exist for Git, Build, Test
    getEvents({ project_id: projectId, limit: 50 })
      .then((events) => {
        if (Array.isArray(events)) {
          setHasGitEvents(events.some((e) => e.source === "GIT" || (e.event_type && e.event_type.startsWith("GIT_"))));
          setHasBuildEvents(events.some((e) => e.source === "BUILD" || (e.event_type && e.event_type.startsWith("BUILD_"))));
          setHasTestEvents(events.some((e) => e.source === "TEST" || (e.event_type && e.event_type.startsWith("TEST_"))));
        }
      })
      .catch(() => {
        setHasGitEvents(false);
        setHasBuildEvents(false);
        setHasTestEvents(false);
      });
  };

  useEffect(() => {
    refreshIndicators();
    const interval = setInterval(refreshIndicators, 15000);
    return () => clearInterval(interval);
  }, [projectId]);

  const handleQuickSync = async () => {
    setSyncing(true);
    try {
      await syncJiraProject(jiraKey, jiraKey);
      window.dispatchEvent(new CustomEvent("projectpulse:synced"));
      refreshIndicators();
    } catch (err) {
      console.error("Sync error:", err);
    } finally {
      setSyncing(false);
    }
  };

  const handleSearchChange = (e) => {
    setSearchQuery(e.target.value);
    if (onSearch) onSearch(e.target.value);
  };

  const userInitials = user?.name
    ? user.name
        .split(" ")
        .map((p) => p[0])
        .join("")
        .slice(0, 2)
        .toUpperCase()
    : "U";

  return (
    <header className="command-bar">
      {/* Left: Breadcrumbs & Live Pulse */}
      <div className="command-bar__left">
        <div className="command-breadcrumb">
          PROJECTPULSE / <span>{projectId || "PP"}</span>
        </div>
        <div className="live-observatory-badge">
          <div className="live-pulse-dot" />
          <span>Live Observatory</span>
        </div>
      </div>

      {/* Middle: Global Search */}
      <div className="command-bar__search">
        <div className="search-input-wrap">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            className="command-search-input"
            placeholder="Search tasks, commits, events, risks (Press / to focus)..."
            value={searchQuery}
            onChange={handleSearchChange}
          />
          <span className="search-hotkey">⌘K</span>
        </div>
      </div>

      {/* Right: Live Connection Indicators & User Profile */}
      <div className="command-bar__right">
        <div className="connection-indicators">
          <div className="indicator-chip" title={jiraConnected ? "Jira Cloud Connected" : "Jira Disconnected (Using Local Task Board)"}>
            <span
              className={`indicator-dot ${jiraConnected ? "indicator-dot--online" : "indicator-dot--offline"}`}
            />
            Jira
          </div>
          <div className="indicator-chip" title={`${activeAgentsCount} Desktop Agent(s) Reporting`}>
            <span
              className={`indicator-dot ${activeAgentsCount > 0 ? "indicator-dot--online" : "indicator-dot--offline"}`}
            />
            Agent
          </div>
          <div className="indicator-chip" title={hasGitEvents ? "Git Telemetry Active (Live Commits Recorded)" : "Git: No events yet"}>
            <span
              className={`indicator-dot ${hasGitEvents ? "indicator-dot--online" : "indicator-dot--offline"}`}
            />
            Git
          </div>
          <div className="indicator-chip" title={hasBuildEvents ? "Build Telemetry Active" : "Build: No events yet"}>
            <span
              className={`indicator-dot ${hasBuildEvents ? "indicator-dot--online" : "indicator-dot--offline"}`}
            />
            Build
          </div>
          <div className="indicator-chip" title={hasTestEvents ? "Test Telemetry Active" : "Test: No events yet"}>
            <span
              className={`indicator-dot ${hasTestEvents ? "indicator-dot--online" : "indicator-dot--offline"}`}
            />
            Test
          </div>
        </div>

        {/* Quick Sync Button */}
        {jiraConnected && (
          <button
            type="button"
            className="btn-primary"
            style={{ fontSize: "0.8rem", padding: "0.35rem 0.85rem" }}
            onClick={handleQuickSync}
            disabled={syncing}
            title={`Synchronize latest issues from Jira Cloud ${jiraKey}`}
          >
            {syncing ? "🔄 Syncing..." : `Sync ${jiraKey}`}
          </button>
        )}

        {/* User Badge */}
        <div className="user-profile-badge" title={`${user?.name || "User"} (${user?.role || "Member"})`}>
          <div className="user-avatar-circle">
            {userInitials}
            <div className="user-avatar-presence" />
          </div>
        </div>
      </div>
    </header>
  );
}
