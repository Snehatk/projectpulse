import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Sidebar({ projectId, userId, collapsed, onToggle }) {
  const location = useLocation();
  const { user, role, logout } = useAuth();

  // Define role-specific navigation access
  const allGroups = [
    {
      group: "INTELLIGENCE",
      items: [
        {
          label: "Manager Command",
          icon: "📊",
          path: "/manager",
          link: `/manager?project_id=${encodeURIComponent(projectId)}`,
          badge: null,
          roles: ["PROJECT_MANAGER"],
        },
        {
          label: "Tasks Command",
          icon: "⚡",
          path: "/tasks",
          link: `/tasks?project_id=${encodeURIComponent(projectId)}`,
          badge: null,
          roles: ["PROJECT_MANAGER", "DEVELOPER", "TESTER", "QA"],
        },
        {
          label: "AI Copilot",
          icon: "✦",
          path: "/assistant",
          link: `/assistant?project_id=${encodeURIComponent(projectId)}`,
          badge: "AI",
          roles: ["PROJECT_MANAGER", "DEVELOPER", "TESTER", "QA"],
        },
      ],
    },
    {
      group: "ENGINEERING REALITY",
      items: [
        {
          label: "Developer Telemetry",
          icon: "💻",
          path: "/developer",
          link: `/developer?project_id=${encodeURIComponent(projectId)}&user_id=${encodeURIComponent(user?.user_id || userId || "DEV-001")}`,
          badge: null,
          roles: ["PROJECT_MANAGER", "DEVELOPER"],
        },
        {
          label: "Testing Gates",
          icon: "🧪",
          path: "/tester",
          link: `/tester?project_id=${encodeURIComponent(projectId)}`,
          badge: null,
          roles: ["PROJECT_MANAGER", "TESTER", "QA"],
        },
        {
          label: "QA & Blockers",
          icon: "🛡️",
          path: "/qa",
          link: `/qa?project_id=${encodeURIComponent(projectId)}`,
          badge: null,
          roles: ["PROJECT_MANAGER", "QA"],
        },
        {
          label: "Change Explorer",
          icon: "🔍",
          path: "/changes",
          link: `/changes?project_id=${encodeURIComponent(projectId)}`,
          badge: "AST",
          roles: ["PROJECT_MANAGER", "DEVELOPER", "TESTER", "QA"],
        },
      ],
    },
    {
      group: "ADMINISTRATION",
      items: [
        {
          label: "User & Fleet",
          icon: "👥",
          path: "/users",
          link: `/users?project_id=${encodeURIComponent(projectId)}`,
          badge: "Admin",
          roles: ["PROJECT_MANAGER"],
        },
        {
          label: "PM Integrations",
          icon: "🔗",
          path: "/integrations",
          link: `/integrations?project_id=${encodeURIComponent(projectId)}`,
          badge: "Jira",
          roles: ["PROJECT_MANAGER"],
        },
        {
          label: "Connected Agents",
          icon: "🤖",
          path: "/agents",
          link: `/agents?project_id=${encodeURIComponent(projectId)}`,
          badge: null,
          roles: ["PROJECT_MANAGER"],
        },
      ],
    },
  ];

  // Filter groups according to logged-in user role
  const filteredGroups = allGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !role || item.roles.includes(role)),
    }))
    .filter((group) => group.items.length > 0);

  const homePath =
    role === "DEVELOPER"
      ? "/developer"
      : role === "TESTER"
      ? "/tester"
      : role === "QA"
      ? "/qa"
      : "/manager";

  return (
    <aside className={`app-sidebar ${collapsed ? "app-sidebar--collapsed" : ""}`}>
      {/* Brand Header */}
      <div className="sidebar-header">
        <Link to={`${homePath}?project_id=${encodeURIComponent(projectId)}`} className="sidebar-brand">
          <div className="brand-icon-wrap">
            <div className="brand-pulse-dot" />
          </div>
          {!collapsed && <span>ProjectPulse AI</span>}
        </Link>
        <button
          type="button"
          className="sidebar-toggle-btn"
          onClick={onToggle}
          title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>

      {/* Navigation Groups */}
      <nav className="sidebar-nav">
        {filteredGroups.map((group, gIdx) => (
          <div key={gIdx} style={{ marginBottom: "0.25rem" }}>
            {!collapsed && <div className="sidebar-group-title">{group.group}</div>}
            {group.items.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.link}
                  className={`sidebar-link ${isActive ? "sidebar-link--active" : ""}`}
                  title={collapsed ? item.label : undefined}
                >
                  <span className="sidebar-icon">{item.icon}</span>
                  {!collapsed && <span className="sidebar-label">{item.label}</span>}
                  {!collapsed && item.badge && (
                    <span className="sidebar-badge">{item.badge}</span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User Profile & Sign Out Footer */}
      <div className="sidebar-footer" style={{ borderTop: "1px solid #1e293b", padding: "0.75rem" }}>
        {user ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <div
                style={{
                  width: "28px",
                  height: "28px",
                  borderRadius: "50%",
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "0.75rem",
                  fontWeight: "700",
                }}
              >
                {user.name ? user.name.slice(0, 2).toUpperCase() : "U"}
              </div>
              {!collapsed && (
                <div style={{ overflow: "hidden", lineHeight: 1.2 }}>
                  <div style={{ fontSize: "0.8rem", fontWeight: "600", color: "#f8fafc", whiteSpace: "nowrap", textOverflow: "ellipsis", overflow: "hidden" }}>
                    {user.name}
                  </div>
                  <div style={{ fontSize: "0.7rem", color: "#94a3b8" }}>{user.role}</div>
                </div>
              )}
            </div>
            {!collapsed && (
              <button
                type="button"
                onClick={logout}
                style={{
                  padding: "0.3rem 0.6rem",
                  fontSize: "0.75rem",
                  borderRadius: "6px",
                  backgroundColor: "#1e293b",
                  color: "#cbd5e1",
                  border: "1px solid #334155",
                  cursor: "pointer",
                  textAlign: "center",
                }}
              >
                Sign Out
              </button>
            )}
          </div>
        ) : (
          <div className="sidebar-project-badge">
            <span className="project-key-tag">{projectId || "PP"}</span>
          </div>
        )}
      </div>
    </aside>
  );
}
