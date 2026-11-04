import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { jira } from "../api/endpoints";
import type { JiraConnection } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ErrorBanner } from "../components/ErrorBanner";
import { formatDateTime } from "../format";

const TOKEN_URL = "https://id.atlassian.com/manage-profile/security/api-tokens";

export function ConnectJiraPage() {
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [status, setStatus] = useState<JiraConnection | null>(null);
  const [siteUrl, setSiteUrl] = useState("");
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    jira.connection().then(setStatus).catch(setError);
  }, []);

  async function connect(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await jira.connect(siteUrl, email, token);
      setToken(""); // never keep the token around longer than needed
      await refresh();
      navigate("/");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    if (!confirm("Disconnect this Jira workspace? The stored token will be deleted.")) return;
    setBusy(true);
    try {
      await jira.disconnect();
      setStatus({ connected: false, site_url: null, email: null, display_name: null, connected_at: null, last_verified_at: null });
      await refresh();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card card-narrow">
      <h1>Jira connection</h1>

      {status?.connected ? (
        <div className="banner banner-ok">
          <strong>Connected to {status.site_url}</strong>
          <div>as {status.display_name} ({status.email}) · since {formatDateTime(status.connected_at)}</div>
          <div className="row">
            <button className="btn btn-ghost" onClick={() => navigate("/")}>Go to findings</button>
            <button className="btn btn-danger" onClick={disconnect} disabled={busy}>Disconnect</button>
          </div>
        </div>
      ) : (
        <p className="muted">Connect your Jira Cloud workspace to start reporting findings. The app verifies the details with Jira before saving them, and stores the token encrypted.</p>
      )}

      <form onSubmit={connect} className="form">
        <h2>{status?.connected ? "Replace connection" : "Connect"}</h2>
        <label>
          Site URL
          <input type="text" placeholder="https://your-team.atlassian.net" value={siteUrl} onChange={(e) => setSiteUrl(e.target.value)} required />
        </label>
        <label>
          Atlassian account email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="off" />
        </label>
        <label>
          API token
          <input type="password" value={token} onChange={(e) => setToken(e.target.value)} required autoComplete="off" />
          <span className="hint">
            Create one at <a href={TOKEN_URL} target="_blank" rel="noopener noreferrer">id.atlassian.com</a>. It is shown there only once.
          </span>
        </label>
        <ErrorBanner error={error} />
        <button className="btn btn-primary" disabled={busy}>{busy ? "Checking with Jira…" : "Test and connect"}</button>
      </form>
    </div>
  );
}
