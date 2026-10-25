import { useEffect, useState } from "react";
import {
  createTeamUser,
  generatePairingCode,
  getAuditLogs,
  getPairedDevices,
  getTeamUsers,
  revokePairedDevice,
  updateTeamUser,
} from "../api/client";

export default function UserManagementView({ projectId = "PP" }) {
  const [users, setUsers] = useState([]);
  const [devices, setDevices] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Create user form state
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState("DEVELOPER");
  const [newPassword, setNewPassword] = useState("Password123!");
  const [creating, setCreating] = useState(false);

  // Pairing code modal state
  const [pairingModal, setPairingModal] = useState(null);

  const loadData = async () => {
    try {
      const [u, d, a] = await Promise.all([
        getTeamUsers(),
        getPairedDevices(),
        getAuditLogs(30),
      ]);
      setUsers(u || []);
      setDevices(d || []);
      setAuditLogs(a || []);
    } catch (err) {
      setError(err.message || "Failed to load team data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setCreating(true);
    try {
      await createTeamUser({
        name: newName,
        email: newEmail,
        role: newRole,
        password: newPassword,
      });
      setSuccess(`Created ${newRole} account for ${newName} (${newEmail}).`);
      setNewName("");
      setNewEmail("");
      loadData();
    } catch (err) {
      setError(err.message || "Failed to create user.");
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (user) => {
    try {
      await updateTeamUser(user.user_id, { is_active: !user.is_active });
      loadData();
    } catch (err) {
      setError(err.message || "Failed to update user status.");
    }
  };

  const handleGeneratePairCode = async () => {
    try {
      const res = await generatePairingCode(projectId);
      setPairingModal(res.pairing_code);
    } catch (err) {
      setError(err.message || "Failed to generate pairing code.");
    }
  };

  const handleRevokeDevice = async (deviceId) => {
    if (!window.confirm(`Revoke device ${deviceId}? Desktop agent will lose access immediately.`)) return;
    try {
      await revokePairedDevice(deviceId);
      setSuccess(`Device ${deviceId} revoked.`);
      loadData();
    } catch (err) {
      setError(err.message || "Failed to revoke device.");
    }
  };

  if (loading) {
    return <div className="card" style={{ padding: "2rem", textAlign: "center" }}>Loading User & Fleet Management...</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ fontSize: "1.35rem", fontWeight: "700", margin: "0 0 0.25rem 0" }}>
            User & Fleet Management
          </h2>
          <p style={{ margin: 0, fontSize: "0.85rem", color: "#94a3b8" }}>
            Administer team role memberships, desktop agent pairings, and security audit logs.
          </p>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={handleGeneratePairCode}
          style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.5rem 1rem" }}
        >
          <span>🔑</span> Generate Agent Pairing Code
        </button>
      </div>

      {/* Alerts */}
      {error && <div className="error-panel">{error}</div>}
      {success && (
        <div style={{ padding: "0.75rem 1rem", backgroundColor: "rgba(16, 185, 129, 0.15)", border: "1px solid #10b981", borderRadius: "8px", color: "#6ee7b7", fontSize: "0.85rem" }}>
          {success}
        </div>
      )}

      {/* Pairing Code Modal Banner */}
      {pairingModal && (
        <div
          style={{
            padding: "1.5rem",
            backgroundColor: "#1e1b4b",
            border: "1px solid #6366f1",
            borderRadius: "12px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ fontSize: "0.85rem", color: "#c7d2fe", marginBottom: "0.25rem" }}>
              Active One-Time Desktop Agent Pairing Code:
            </div>
            <div style={{ fontSize: "2rem", fontWeight: "800", letterSpacing: "0.2em", color: "#ffffff", fontFamily: "monospace" }}>
              {pairingModal}
            </div>
            <div style={{ fontSize: "0.75rem", color: "#a5b4fc", marginTop: "0.25rem" }}>
              Enter this code when launching <code>start_agent.bat</code> to bind the workstation to your account. Valid for 10 minutes.
            </div>
          </div>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setPairingModal(null)}
          >
            Done
          </button>
        </div>
      )}

      {/* Grid: Users Table & Add User Form */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "1.5rem" }}>
        {/* Team Members Table */}
        <div className="card" style={{ padding: "1.25rem" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: "600", marginBottom: "1rem" }}>
            Team Accounts ({users.length})
          </h3>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #334155", color: "#94a3b8", textAlign: "left" }}>
                  <th style={{ padding: "0.6rem 0.5rem" }}>User</th>
                  <th style={{ padding: "0.6rem 0.5rem" }}>Role</th>
                  <th style={{ padding: "0.6rem 0.5rem" }}>Status</th>
                  <th style={{ padding: "0.6rem 0.5rem" }}>Last Login</th>
                  <th style={{ padding: "0.6rem 0.5rem", textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const roleColors = {
                    PROJECT_MANAGER: "#8b5cf6",
                    DEVELOPER: "#3b82f6",
                    TESTER: "#f59e0b",
                    QA: "#10b981",
                  };
                  return (
                    <tr key={u.user_id} style={{ borderBottom: "1px solid #1e293b" }}>
                      <td style={{ padding: "0.6rem 0.5rem" }}>
                        <strong>{u.name}</strong>
                        <div style={{ fontSize: "0.75rem", color: "#64748b" }}>{u.email}</div>
                      </td>
                      <td style={{ padding: "0.6rem 0.5rem" }}>
                        <span
                          style={{
                            padding: "0.2rem 0.5rem",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                            fontWeight: "600",
                            backgroundColor: `${roleColors[u.role] || "#64748b"}22`,
                            color: roleColors[u.role] || "#94a3b8",
                            border: `1px solid ${roleColors[u.role] || "#64748b"}55`,
                          }}
                        >
                          {u.role}
                        </span>
                      </td>
                      <td style={{ padding: "0.6rem 0.5rem" }}>
                        <span style={{ color: u.is_active ? "#10b981" : "#ef4444", fontWeight: "500" }}>
                          ● {u.is_active ? "Active" : "Deactivated"}
                        </span>
                      </td>
                      <td style={{ padding: "0.6rem 0.5rem", color: "#64748b" }}>
                        {u.last_login ? new Date(u.last_login).toLocaleDateString() : "Never"}
                      </td>
                      <td style={{ padding: "0.6rem 0.5rem", textAlign: "right" }}>
                        {u.role !== "PROJECT_MANAGER" && (
                          <button
                            type="button"
                            onClick={() => handleToggleActive(u)}
                            style={{
                              padding: "0.25rem 0.5rem",
                              fontSize: "0.75rem",
                              borderRadius: "4px",
                              backgroundColor: u.is_active ? "#ef444422" : "#10b98122",
                              color: u.is_active ? "#f87171" : "#34d399",
                              border: "none",
                              cursor: "pointer",
                            }}
                          >
                            {u.is_active ? "Deactivate" : "Activate"}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Create Member Form */}
        <div className="card" style={{ padding: "1.25rem" }}>
          <h3 style={{ fontSize: "1rem", fontWeight: "600", marginBottom: "1rem" }}>
            Invite Team Member
          </h3>
          <form onSubmit={handleCreateUser}>
            <div style={{ marginBottom: "0.85rem" }}>
              <label style={{ display: "block", fontSize: "0.75rem", fontWeight: "600", marginBottom: "0.3rem", color: "#cbd5e1" }}>
                Full Name
              </label>
              <input
                type="text"
                required
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Maya Patel"
                style={{ width: "100%", padding: "0.55rem 0.75rem", borderRadius: "6px", border: "1px solid #334155", backgroundColor: "#0f172a", color: "#ffffff", fontSize: "0.85rem", boxSizing: "border-box" }}
              />
            </div>
            <div style={{ marginBottom: "0.85rem" }}>
              <label style={{ display: "block", fontSize: "0.75rem", fontWeight: "600", marginBottom: "0.3rem", color: "#cbd5e1" }}>
                Email
              </label>
              <input
                type="email"
                required
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="e.g. maya.dev@pulse.local"
                style={{ width: "100%", padding: "0.55rem 0.75rem", borderRadius: "6px", border: "1px solid #334155", backgroundColor: "#0f172a", color: "#ffffff", fontSize: "0.85rem", boxSizing: "border-box" }}
              />
            </div>
            <div style={{ marginBottom: "0.85rem" }}>
              <label style={{ display: "block", fontSize: "0.75rem", fontWeight: "600", marginBottom: "0.3rem", color: "#cbd5e1" }}>
                Role
              </label>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                style={{ width: "100%", padding: "0.55rem 0.75rem", borderRadius: "6px", border: "1px solid #334155", backgroundColor: "#0f172a", color: "#ffffff", fontSize: "0.85rem", boxSizing: "border-box" }}
              >
                <option value="DEVELOPER">Developer (Watches code, Git, builds)</option>
                <option value="TESTER">Tester (Watches test reports, suites)</option>
                <option value="QA">QA Engineer (Quality gates, defects, coverage)</option>
                <option value="PROJECT_MANAGER">Project Manager (Admin)</option>
              </select>
            </div>
            <div style={{ marginBottom: "1.25rem" }}>
              <label style={{ display: "block", fontSize: "0.75rem", fontWeight: "600", marginBottom: "0.3rem", color: "#cbd5e1" }}>
                Initial Password
              </label>
              <input
                type="password"
                required
                minLength={6}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                style={{ width: "100%", padding: "0.55rem 0.75rem", borderRadius: "6px", border: "1px solid #334155", backgroundColor: "#0f172a", color: "#ffffff", fontSize: "0.85rem", boxSizing: "border-box" }}
              />
            </div>
            <button
              type="submit"
              disabled={creating}
              className="btn-primary"
              style={{ width: "100%", padding: "0.6rem" }}
            >
              {creating ? "Creating Account..." : "Create Team Account"}
            </button>
          </form>
        </div>
      </div>

      {/* Paired Devices Section */}
      <div className="card" style={{ padding: "1.25rem" }}>
        <h3 style={{ fontSize: "1rem", fontWeight: "600", marginBottom: "1rem" }}>
          Paired Agent Devices ({devices.length})
        </h3>
        {devices.length === 0 ? (
          <div style={{ padding: "1.5rem", textAlign: "center", color: "#64748b", fontSize: "0.85rem" }}>
            No agent devices currently paired. Click <strong>Generate Agent Pairing Code</strong> above to connect a desktop agent.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #334155", color: "#94a3b8", textAlign: "left" }}>
                  <th style={{ padding: "0.6rem 0.5rem" }}>Device ID</th>
                  <th style={{ padding: "0.6rem 0.5rem" }}>Machine Name</th>
                  <th style={{ padding: "0.6rem 0.5rem" }}>Bound Role</th>
                  <th style={{ padding: "0.6rem 0.5rem" }}>User</th>
                  <th style={{ padding: "0.6rem 0.5rem" }}>Status</th>
                  <th style={{ padding: "0.6rem 0.5rem" }}>Last Active</th>
                  <th style={{ padding: "0.6rem 0.5rem", textAlign: "right" }}>Revoke</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((d) => (
                  <tr key={d.device_id} style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={{ padding: "0.6rem 0.5rem", fontFamily: "monospace" }}>{d.device_id}</td>
                    <td style={{ padding: "0.6rem 0.5rem" }}><strong>{d.machine_name}</strong></td>
                    <td style={{ padding: "0.6rem 0.5rem" }}>{d.role}</td>
                    <td style={{ padding: "0.6rem 0.5rem", color: "#94a3b8" }}>{d.user_id}</td>
                    <td style={{ padding: "0.6rem 0.5rem" }}>
                      <span style={{ color: d.is_revoked ? "#ef4444" : "#10b981", fontWeight: "600" }}>
                        ● {d.is_revoked ? "Revoked" : "Authorized"}
                      </span>
                    </td>
                    <td style={{ padding: "0.6rem 0.5rem", color: "#64748b" }}>
                      {d.last_used_at ? new Date(d.last_used_at).toLocaleTimeString() : "Never"}
                    </td>
                    <td style={{ padding: "0.6rem 0.5rem", textAlign: "right" }}>
                      {!d.is_revoked && (
                        <button
                          type="button"
                          onClick={() => handleRevokeDevice(d.device_id)}
                          style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem", borderRadius: "4px", backgroundColor: "#ef444422", color: "#f87171", border: "none", cursor: "pointer" }}
                        >
                          Revoke Token
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Security Audit Log */}
      <div className="card" style={{ padding: "1.25rem" }}>
        <h3 style={{ fontSize: "1rem", fontWeight: "600", marginBottom: "1rem" }}>
          Security Audit Ledger (Recent {auditLogs.length} Events)
        </h3>
        <div style={{ maxHeight: "240px", overflowY: "auto", fontSize: "0.8rem", fontFamily: "monospace" }}>
          {auditLogs.map((log) => (
            <div key={log.id} style={{ padding: "0.4rem 0", borderBottom: "1px solid #1e293b", display: "flex", gap: "1rem" }}>
              <span style={{ color: "#64748b" }}>{new Date(log.timestamp).toLocaleTimeString()}</span>
              <span style={{ color: "#38bdf8", fontWeight: "600" }}>[{log.action}]</span>
              <span style={{ color: "#cbd5e1" }}>User: {log.user_id}</span>
              <span style={{ color: "#94a3b8" }}>{log.details}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
