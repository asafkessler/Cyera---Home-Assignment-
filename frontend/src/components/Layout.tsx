import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

/** App chrome: brand, navigation, who is logged in, logout. */
export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">IH</span>
          <span>IdentityHub <span className="muted">· Jira Integration</span></span>
        </Link>
        {user && (
          <nav className="nav">
            <NavLink to="/" end>Findings</NavLink>
            <NavLink to="/keys">API keys</NavLink>
            <NavLink to="/connect">Jira connection</NavLink>
            <span className="nav-user" title={user.email}>{user.email}</span>
            <button className="btn btn-ghost" onClick={handleLogout}>Log out</button>
          </nav>
        )}
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
