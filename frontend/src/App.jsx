import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import { getAppConfig } from "./api/client";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./components/LoginPage";
import FirstRunSetupPage from "./components/FirstRunSetupPage";
import UserManagementView from "./components/UserManagementView";
import AgentsView from "./components/AgentsView";
import AIAssistantView from "./components/AIAssistantView";
import ChangeExplorerView from "./components/ChangeExplorerView";
import DeveloperView from "./components/DeveloperView";
import IntegrationsView from "./components/IntegrationsView";
import ManagerView from "./components/ManagerView";
import QAView from "./components/QAView";
import Sidebar from "./components/Sidebar";
import SystemStatusStrip from "./components/SystemStatusStrip";
import TasksView from "./components/TasksView";
import TesterView from "./components/TesterView";
import TopCommandBar from "./components/TopCommandBar";

function useIds() {
  const [searchParams] = useSearchParams();
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState(null);
  const { user } = useAuth();

  useEffect(() => {
    getAppConfig()
      .then(setConfig)
      .catch((err) => setConfigError(err.message));
  }, []);

  return useMemo(() => {
    const projectId =
      searchParams.get("project_id") || config?.project_id || "PP";
    const userId =
      user?.user_id || searchParams.get("user_id") || config?.user_id || "DEV-001";
    return { projectId, userId, config, configError };
  }, [searchParams, config, configError, user]);
}

function Layout({ children, projectId, userId }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="app-shell">
      <Sidebar
        projectId={projectId}
        userId={userId}
        collapsed={collapsed}
        onToggle={() => setCollapsed(!collapsed)}
      />
      <div className={`app-main ${collapsed ? "app-main--collapsed" : ""}`}>
        <TopCommandBar projectId={projectId} />
        <SystemStatusStrip projectId={projectId} />
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}

function DeveloperPage() {
  const { projectId, userId, configError } = useIds();
  if (configError && !projectId) return <div className="error-panel">Config error: {configError}</div>;
  return (
    <Layout projectId={projectId} userId={userId}>
      <DeveloperView projectId={projectId} userId={userId} />
    </Layout>
  );
}

function ManagerPage() {
  const { projectId, configError } = useIds();
  if (configError && !projectId) return <div className="error-panel">Config error: {configError}</div>;
  return (
    <Layout projectId={projectId} userId="">
      <ManagerView projectId={projectId} />
    </Layout>
  );
}

function TesterPage() {
  const { projectId, configError } = useIds();
  if (configError && !projectId) return <div className="error-panel">Config error: {configError}</div>;
  return (
    <Layout projectId={projectId} userId="">
      <TesterView projectId={projectId} />
    </Layout>
  );
}

function QAPage() {
  const { projectId, configError } = useIds();
  if (configError && !projectId) return <div className="error-panel">Config error: {configError}</div>;
  return (
    <Layout projectId={projectId} userId="">
      <QAView projectId={projectId} />
    </Layout>
  );
}

function IntegrationsPage() {
  const { projectId, configError } = useIds();
  if (configError && !projectId) return <div className="error-panel">Config error: {configError}</div>;
  return (
    <Layout projectId={projectId} userId="">
      <IntegrationsView projectId={projectId} />
    </Layout>
  );
}

function AgentsPage() {
  const { projectId, configError } = useIds();
  if (configError && !projectId) return <div className="error-panel">Config error: {configError}</div>;
  return (
    <Layout projectId={projectId} userId="">
      <AgentsView projectId={projectId} />
    </Layout>
  );
}

function TasksPage() {
  const { projectId, configError } = useIds();
  if (configError && !projectId) return <div className="error-panel">Config error: {configError}</div>;
  return (
    <Layout projectId={projectId} userId="">
      <TasksView projectId={projectId} />
    </Layout>
  );
}

function AIAssistantPage() {
  const { projectId, configError } = useIds();
  if (configError && !projectId) return <div className="error-panel">Config error: {configError}</div>;
  return (
    <Layout projectId={projectId} userId="">
      <AIAssistantView projectId={projectId} />
    </Layout>
  );
}

function UserManagementPage() {
  const { projectId, configError } = useIds();
  if (configError && !projectId) return <div className="error-panel">Config error: {configError}</div>;
  return (
    <Layout projectId={projectId} userId="">
      <UserManagementView projectId={projectId} />
    </Layout>
  );
}

function ChangeExplorerPage() {
  const { projectId, configError } = useIds();
  if (configError && !projectId) return <div className="error-panel">Config error: {configError}</div>;
  return (
    <Layout projectId={projectId} userId="">
      <ChangeExplorerView projectId={projectId} />
    </Layout>
  );
}

function RootRedirect() {
  const { role, isAuthenticated, hasPMAccount, loading } = useAuth();
  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          backgroundColor: "#0b0f19",
          color: "#94a3b8",
          fontSize: "0.95rem",
        }}
      >
        Initializing ProjectPulse AI...
      </div>
    );
  }
  if (!hasPMAccount) return <Navigate to="/setup" replace />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  const rolePaths = {
    DEVELOPER: "/developer",
    TESTER: "/tester",
    QA: "/qa",
    PROJECT_MANAGER: "/manager",
  };
  return <Navigate to={rolePaths[role] || "/manager"} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public Authentication Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/setup" element={<FirstRunSetupPage />} />

        {/* Root Redirects to User's Role Landing View */}
        <Route path="/" element={<RootRedirect />} />

        {/* Protected Role-Specific Routes */}
        <Route
          path="/manager"
          element={
            <ProtectedRoute allowedRoles={["PROJECT_MANAGER"]}>
              <ManagerPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/developer"
          element={
            <ProtectedRoute allowedRoles={["DEVELOPER", "PROJECT_MANAGER"]}>
              <DeveloperPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tester"
          element={
            <ProtectedRoute allowedRoles={["TESTER", "QA", "PROJECT_MANAGER"]}>
              <TesterPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/qa"
          element={
            <ProtectedRoute allowedRoles={["QA", "PROJECT_MANAGER"]}>
              <QAPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tasks"
          element={
            <ProtectedRoute allowedRoles={["PROJECT_MANAGER", "DEVELOPER", "TESTER", "QA"]}>
              <TasksPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/users"
          element={
            <ProtectedRoute allowedRoles={["PROJECT_MANAGER"]}>
              <UserManagementPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/integrations"
          element={
            <ProtectedRoute allowedRoles={["PROJECT_MANAGER"]}>
              <IntegrationsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/agents"
          element={
            <ProtectedRoute allowedRoles={["PROJECT_MANAGER"]}>
              <AgentsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/assistant"
          element={
            <ProtectedRoute allowedRoles={["PROJECT_MANAGER", "DEVELOPER", "TESTER", "QA"]}>
              <AIAssistantPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/changes"
          element={
            <ProtectedRoute allowedRoles={["PROJECT_MANAGER", "DEVELOPER", "TESTER", "QA"]}>
              <ChangeExplorerPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </AuthProvider>
  );
}
