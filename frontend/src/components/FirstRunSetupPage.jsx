import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createTeamUser } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function FirstRunSetupPage() {
  const { setupPM, hasPMAccount, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState("Sarah Chen");
  const [email, setEmail] = useState("pm@pulse.local");
  const [password, setPassword] = useState("Password123!");
  const [projectName, setProjectName] = useState("Showcase Order Service");
  const [projectFolder, setProjectFolder] = useState("showcase_project");
  const [seedDemoTeam, setSeedDemoTeam] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!authLoading && hasPMAccount === true) {
      navigate("/login", { replace: true });
    }
  }, [hasPMAccount, authLoading, navigate]);

  const handleSetup = async (e) => {
    e.preventDefault();
    if (!email || !password || !name) {
      setError("Please fill out all required fields.");
      return;
    }
    setError("");
    setLoading(true);

    try {
      // 1. Setup First PM
      await setupPM({
        name,
        email,
        password,
        project_id: "PP",
        project_name: projectName,
        project_folder: projectFolder,
      });

      // 2. Optionally seed standard demonstration team members
      if (seedDemoTeam) {
        const team = [
          { name: "Alex Rivera", email: "dev@pulse.local", role: "DEVELOPER", password: "Password123!" },
          { name: "Dave Miller", email: "tester@pulse.local", role: "TESTER", password: "Password123!" },
          { name: "Liam Johnson", email: "qa@pulse.local", role: "QA", password: "Password123!" },
        ];
        for (const member of team) {
          try {
            await createTeamUser(member);
          } catch (err) {
            console.warn("Demo team creation warning:", err);
          }
        }
      }

      navigate("/manager");
    } catch (err) {
      setError(err.message || "Failed to initialize ProjectPulse PM account.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        backgroundColor: "#0b0f19",
        color: "#f8fafc",
        padding: "1.5rem",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "520px",
          backgroundColor: "#131b2e",
          border: "1px solid #1e293b",
          borderRadius: "16px",
          padding: "2.5rem 2rem",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              background: "linear-gradient(135deg, #10b981, #059669)",
              marginBottom: "1rem",
            }}
          >
            <span style={{ fontSize: "1.5rem" }}>🚀</span>
          </div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: "700", margin: "0 0 0.5rem 0" }}>
            Initial Project Setup
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8", margin: 0 }}>
            Configure the primary Project Manager account and showcase project.
          </p>
        </div>

        {error && (
          <div
            style={{
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              border: "1px solid #ef4444",
              borderRadius: "8px",
              padding: "0.75rem",
              marginBottom: "1.25rem",
              fontSize: "0.85rem",
              color: "#fca5a5",
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSetup}>
          <div style={{ marginBottom: "1rem" }}>
            <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "600", marginBottom: "0.4rem", color: "#cbd5e1" }}>
              Project Manager Full Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Sarah Chen"
              style={{
                width: "100%",
                padding: "0.65rem 0.85rem",
                borderRadius: "8px",
                border: "1px solid #334155",
                backgroundColor: "#0f172a",
                color: "#ffffff",
                fontSize: "0.9rem",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "1rem" }}>
            <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "600", marginBottom: "0.4rem", color: "#cbd5e1" }}>
              Admin Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. pm@pulse.local"
              style={{
                width: "100%",
                padding: "0.65rem 0.85rem",
                borderRadius: "8px",
                border: "1px solid #334155",
                backgroundColor: "#0f172a",
                color: "#ffffff",
                fontSize: "0.9rem",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "1rem" }}>
            <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "600", marginBottom: "0.4rem", color: "#cbd5e1" }}>
              Admin Password (min. 6 characters)
            </label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter secure password"
              style={{
                width: "100%",
                padding: "0.65rem 0.85rem",
                borderRadius: "8px",
                border: "1px solid #334155",
                backgroundColor: "#0f172a",
                color: "#ffffff",
                fontSize: "0.9rem",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "1rem" }}>
            <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "600", marginBottom: "0.4rem", color: "#cbd5e1" }}>
              Showcase Project Name
            </label>
            <input
              type="text"
              required
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              style={{
                width: "100%",
                padding: "0.65rem 0.85rem",
                borderRadius: "8px",
                border: "1px solid #334155",
                backgroundColor: "#0f172a",
                color: "#ffffff",
                fontSize: "0.9rem",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "1.25rem" }}>
            <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "600", marginBottom: "0.4rem", color: "#cbd5e1" }}>
              Showcase Folder Path (Local)
            </label>
            <input
              type="text"
              required
              value={projectFolder}
              onChange={(e) => setProjectFolder(e.target.value)}
              placeholder="e.g. showcase_project"
              style={{
                width: "100%",
                padding: "0.65rem 0.85rem",
                borderRadius: "8px",
                border: "1px solid #334155",
                backgroundColor: "#0f172a",
                color: "#ffffff",
                fontSize: "0.9rem",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "1.5rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <input
              type="checkbox"
              id="seedDemoTeam"
              checked={seedDemoTeam}
              onChange={(e) => setSeedDemoTeam(e.target.checked)}
              style={{ cursor: "pointer" }}
            />
            <label htmlFor="seedDemoTeam" style={{ fontSize: "0.825rem", color: "#94a3b8", cursor: "pointer" }}>
              Pre-create demo team accounts (<code>dev@pulse.local</code>, <code>tester@pulse.local</code>, <code>qa@pulse.local</code>)
            </label>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              padding: "0.75rem",
              borderRadius: "8px",
              backgroundColor: "#10b981",
              color: "#ffffff",
              border: "none",
              fontSize: "0.95rem",
              fontWeight: "600",
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Initializing System..." : "Complete Setup & Launch Dashboard"}
          </button>
        </form>
      </div>
    </div>
  );
}
