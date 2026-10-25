import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children, allowedRoles = [] }) {
  const { user, isAuthenticated, loading, role } = useAuth();

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", color: "#94a3b8" }}>
        <div style={{ textAlign: "center" }}>
          <div className="brand-pulse-dot" style={{ margin: "0 auto 1rem auto" }} />
          <span>Verifying ProjectPulse session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles.length > 0 && !allowedRoles.includes(role)) {
    // Redirect user to their own role's primary landing view
    const defaultRolePaths = {
      DEVELOPER: "/developer",
      TESTER: "/tester",
      QA: "/qa",
      PROJECT_MANAGER: "/manager",
    };
    const targetPath = defaultRolePaths[role] || "/manager";
    return <Navigate to={targetPath} replace />;
  }

  return children;
}
