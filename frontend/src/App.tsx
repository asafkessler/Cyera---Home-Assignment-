import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { ApiKeysPage } from "./pages/ApiKeysPage";
import { ConnectJiraPage } from "./pages/ConnectJiraPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";

/** Pages that need a logged-in user. The findings page additionally needs a Jira connection. */
function RequireAuth({ children, needsJira = false }: { children: ReactNode; needsJira?: boolean }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="muted">Loading…</p>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (needsJira && !user.jira_connected) return <Navigate to="/connect" replace />;
  return <>{children}</>;
}

function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to={user.jira_connected ? "/" : "/connect"} replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/login" element={<RedirectIfAuthed><LoginPage mode="login" /></RedirectIfAuthed>} />
            <Route path="/register" element={<RedirectIfAuthed><LoginPage mode="register" /></RedirectIfAuthed>} />
            <Route path="/connect" element={<RequireAuth><ConnectJiraPage /></RequireAuth>} />
            <Route path="/keys" element={<RequireAuth><ApiKeysPage /></RequireAuth>} />
            <Route path="/" element={<RequireAuth needsJira><DashboardPage /></RequireAuth>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
