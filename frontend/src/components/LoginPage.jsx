import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login, hasPMAccount } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e) => {
    if (e) e.preventDefault();
    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const profile = await login(email, password);
      const rolePaths = {
        DEVELOPER: "/developer",
        TESTER: "/tester",
        QA: "/qa",
        PROJECT_MANAGER: "/manager",
      };
      navigate(rolePaths[profile.role] || "/manager");
    } catch (err) {
      setError(err.message || "Invalid credentials.");
    } finally {
      setLoading(false);
    }
  };

  const quickSignIn = async (demoEmail, demoPassword) => {
    if (hasPMAccount === false) {
      setError("Initial setup is required before using demo accounts. Please click 'Create First PM Account' above to initialize.");
      return;
    }
    setEmail(demoEmail);
    setPassword(demoPassword);
    setError("");
    setLoading(true);
    try {
      const profile = await login(demoEmail, demoPassword);
      const rolePaths = {
        DEVELOPER: "/developer",
        TESTER: "/tester",
        QA: "/qa",
        PROJECT_MANAGER: "/manager",
      };
      navigate(rolePaths[profile.role] || "/manager");
    } catch (err) {
      setError(err.message || "Invalid credentials.");
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
        padding: "1rem",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "440px",
          backgroundColor: "#131b2e",
          border: "1px solid #1e293b",
          borderRadius: "16px",
          padding: "2.5rem 2rem",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
        }}
      >
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              background: "linear-gradient(135deg, #2563eb, #3b82f6)",
              marginBottom: "1rem",
            }}
          >
            <div className="brand-pulse-dot" style={{ backgroundColor: "#ffffff" }} />
          </div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: "700", margin: "0 0 0.5rem 0" }}>
            ProjectPulse AI
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8", margin: 0 }}>
            Cross-Functional Project Intelligence System
          </p>
        </div>

        {/* First Run Alert Banner */}
        {!hasPMAccount && (
          <div
            style={{
              backgroundColor: "rgba(59, 130, 246, 0.1)",
              border: "1px solid #3b82f6",
              borderRadius: "8px",
              padding: "1rem",
              marginBottom: "1.5rem",
              fontSize: "0.85rem",
              color: "#93c5fd",
            }}
          >
            <strong>First-Run Setup Required:</strong> No Project Manager account exists yet.
            <div style={{ marginTop: "0.5rem" }}>
              <Link
                to="/setup"
                style={{
                  display: "inline-block",
                  padding: "0.4rem 0.8rem",
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  borderRadius: "6px",
                  textDecoration: "none",
                  fontWeight: "600",
                }}
              >
                Create First PM Account →
              </Link>
            </div>
          </div>
        )}

        {/* Error Alert */}
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

        {/* Login Form */}
        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: "1.25rem" }}>
            <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "600", marginBottom: "0.5rem", color: "#cbd5e1" }}>
              Email or Username
            </label>
            <input
              type="text"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. sarah.pm@pulse.local"
              style={{
                width: "100%",
                padding: "0.75rem 1rem",
                borderRadius: "8px",
                border: "1px solid #334155",
                backgroundColor: "#0f172a",
                color: "#ffffff",
                fontSize: "0.9rem",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "1.5rem" }}>
            <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "600", marginBottom: "0.5rem", color: "#cbd5e1" }}>
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              style={{
                width: "100%",
                padding: "0.75rem 1rem",
                borderRadius: "8px",
                border: "1px solid #334155",
                backgroundColor: "#0f172a",
                color: "#ffffff",
                fontSize: "0.9rem",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              padding: "0.75rem",
              borderRadius: "8px",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              border: "none",
              fontSize: "0.95rem",
              fontWeight: "600",
              cursor: loading ? "not-allowed" : "pointer",
              transition: "background 0.2s",
            }}
          >
            {loading ? "Authenticating..." : "Sign In to ProjectPulse"}
          </button>
        </form>

        {/* Quick Demo Accounts Helper */}
        <div style={{ marginTop: "1.75rem", paddingTop: "1.5rem", borderTop: "1px solid #1e293b", textAlign: "center" }}>
          <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Demo Quick Login
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", justifyContent: "center" }}>
            <button
              id="demo-login-pm"
              type="button"
              onClick={() => quickSignIn("pm@pulse.local", "Password123!")}
              style={{
                padding: "0.3rem 0.6rem",
                fontSize: "0.75rem",
                borderRadius: "6px",
                backgroundColor: "#1e293b",
                color: "#94a3b8",
                border: "1px solid #334155",
                cursor: "pointer",
              }}
            >
              PM
            </button>
            <button
              id="demo-login-dev"
              type="button"
              onClick={() => quickSignIn("dev@pulse.local", "Password123!")}
              style={{
                padding: "0.3rem 0.6rem",
                fontSize: "0.75rem",
                borderRadius: "6px",
                backgroundColor: "#1e293b",
                color: "#94a3b8",
                border: "1px solid #334155",
                cursor: "pointer",
              }}
            >
              Dev
            </button>
            <button
              id="demo-login-tester"
              type="button"
              onClick={() => quickSignIn("tester@pulse.local", "Password123!")}
              style={{
                padding: "0.3rem 0.6rem",
                fontSize: "0.75rem",
                borderRadius: "6px",
                backgroundColor: "#1e293b",
                color: "#94a3b8",
                border: "1px solid #334155",
                cursor: "pointer",
              }}
            >
              Tester
            </button>
            <button
              id="demo-login-qa"
              type="button"
              onClick={() => quickSignIn("qa@pulse.local", "Password123!")}
              style={{
                padding: "0.3rem 0.6rem",
                fontSize: "0.75rem",
                borderRadius: "6px",
                backgroundColor: "#1e293b",
                color: "#94a3b8",
                border: "1px solid #334155",
                cursor: "pointer",
              }}
            >
              QA
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
