import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { auth } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { ErrorBanner } from "../components/ErrorBanner";

export function LoginPage({ mode }: { mode: "login" | "register" }) {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const isRegister = mode === "register";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = isRegister ? await auth.register(email, password) : await auth.login(email, password);
      setUser(user);
      navigate(user.jira_connected ? "/" : "/connect");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card card-narrow">
      <h1>{isRegister ? "Create your account" : "Log in"}</h1>
      <p className="muted">
        {isRegister
          ? "Each account connects its own Jira workspace and sees only its own tickets."
          : "Welcome back. Your Jira connection and tickets are waiting."}
      </p>
      <form onSubmit={submit} className="form">
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus autoComplete="email" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete={isRegister ? "new-password" : "current-password"}
          />
          {isRegister && <span className="hint">At least 8 characters.</span>}
        </label>
        <ErrorBanner error={error} />
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Please wait…" : isRegister ? "Create account" : "Log in"}
        </button>
      </form>
      <p className="muted">
        {isRegister ? (
          <>Already have an account? <Link to="/login">Log in</Link></>
        ) : (
          <>New here? <Link to="/register">Create an account</Link></>
        )}
      </p>
    </div>
  );
}
