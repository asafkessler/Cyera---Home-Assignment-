import { useEffect, useState, type FormEvent } from "react";
import { apiKeys } from "../api/endpoints";
import type { ApiKey, ApiKeyCreated } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { formatDateTime } from "../format";

export function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  async function load() {
    try { setKeys(await apiKeys.list()); } catch (err) { setError(err); }
  }
  useEffect(() => { void load(); }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const key = await apiKeys.create(name);
      setCreated(key);
      setCopied(false);
      setName("");
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function revoke(key: ApiKey) {
    if (!confirm(`Revoke "${key.name}"? Systems using it will get 401 immediately.`)) return;
    try {
      await apiKeys.revoke(key.id);
      if (created?.id === key.id) setCreated(null);
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); setCopied(true); } catch { setCopied(false); }
  }

  const origin = window.location.origin;
  const curl = created
    ? `curl -X POST ${origin}/api/v1/findings \\
  -H "X-API-Key: ${created.key}" \\
  -H "Content-Type: application/json" \\
  -d '{"project_key": "SCRUM", "summary": "Stale service account: svc-deploy-prod", "description": "No authentication events in 94 days.", "severity": "high", "identity_type": "service_account"}'`
    : "";

  return (
    <>
      <div className="page-head"><h1>API keys</h1></div>
      <p className="muted">
        Let scanners and CI/CD pipelines report findings without the form. Requests made with a key act as you and create tickets in your Jira workspace.
        See the <a href="/api/docs" target="_blank" rel="noopener noreferrer">API documentation</a>.
      </p>

      <div className="grid-2">
        <section className="card">
          <h2>Create a key</h2>
          <form onSubmit={create} className="form">
            <label>
              Name
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="nightly-nhi-scanner" maxLength={100} required />
              <span className="hint">Something that tells you which system uses it.</span>
            </label>
            <ErrorBanner error={error} />
            <button className="btn btn-primary" disabled={busy}>Create key</button>
          </form>

          {created && (
            <div className="banner banner-warn key-reveal">
              <strong>Copy your key now. It will not be shown again.</strong>
              <div className="row">
                <code className="key-value">{created.key}</code>
                <button className="btn btn-ghost" onClick={() => copy(created.key)}>{copied ? "Copied" : "Copy"}</button>
              </div>
              <details>
                <summary>Example request</summary>
                <pre className="code">{curl}</pre>
              </details>
            </div>
          )}
        </section>

        <section className="card">
          <h2>Your keys</h2>
          {keys.length === 0 ? (
            <p className="muted">No keys yet.</p>
          ) : (
            <table className="table">
              <thead>
                <tr><th>Name</th><th>Prefix</th><th>Created</th><th>Last used</th><th></th></tr>
              </thead>
              <tbody>
                {keys.map((k) => (
                  <tr key={k.id} className={k.revoked_at ? "revoked" : ""}>
                    <td>{k.name}</td>
                    <td><code>{k.key_prefix}…</code></td>
                    <td>{formatDateTime(k.created_at)}</td>
                    <td>{k.last_used_at ? formatDateTime(k.last_used_at) : <span className="muted">never</span>}</td>
                    <td>
                      {k.revoked_at
                        ? <span className="pill pill-revoked">revoked</span>
                        : <button className="btn btn-danger btn-sm" onClick={() => revoke(k)}>Revoke</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </>
  );
}
