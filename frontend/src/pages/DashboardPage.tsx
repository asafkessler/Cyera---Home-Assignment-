import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { jira, tickets as ticketsApi } from "../api/endpoints";
import type { Project, Ticket } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { RecentTickets } from "../components/RecentTickets";
import { TicketForm } from "../components/TicketForm";

const PROJECT_STORAGE_KEY = "identityhub.selectedProject";

export function DashboardPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectKey, setProjectKey] = useState<string>(() => safeGet(PROJECT_STORAGE_KEY) ?? "");
  const [recent, setRecent] = useState<Ticket[]>([]);
  const [loadingRecent, setLoadingRecent] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [justCreated, setJustCreated] = useState<Ticket | null>(null);

  // Projects come live from Jira; remember the last choice per browser.
  useEffect(() => {
    jira
      .projects()
      .then((list) => {
        setProjects(list);
        if (!list.some((p) => p.key === projectKey)) setProjectKey(list[0]?.key ?? "");
      })
      .catch(setError);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadRecent = useCallback(async (key: string) => {
    if (!key) return;
    setLoadingRecent(true);
    try {
      setRecent(await ticketsApi.recent(key));
    } catch (err) {
      setError(err);
    } finally {
      setLoadingRecent(false);
    }
  }, []);

  useEffect(() => {
    if (projectKey) safeSet(PROJECT_STORAGE_KEY, projectKey);
    setJustCreated(null);
    void loadRecent(projectKey);
  }, [projectKey, loadRecent]);

  function handleCreated(ticket: Ticket) {
    setJustCreated(ticket);
    void loadRecent(projectKey);
  }

  return (
    <>
      <div className="page-head">
        <h1>Report an NHI finding</h1>
        <label className="project-select">
          Jira project
          <select value={projectKey} onChange={(e) => setProjectKey(e.target.value)} disabled={!projects}>
            {!projects && <option>Loading projects…</option>}
            {projects?.map((p) => <option key={p.key} value={p.key}>{p.name} ({p.key})</option>)}
          </select>
        </label>
      </div>

      <ErrorBanner error={error} />
      {projects && projects.length === 0 && (
        <div className="banner banner-warn">
          No projects are visible to your Jira account. Create one in Jira or ask for access, then <Link to="/connect">reconnect</Link>.
        </div>
      )}

      <div className="grid-2">
        <section className="card">
          <h2>New finding</h2>
          {justCreated && (
            <div className="banner banner-ok">
              Created <a href={justCreated.issue_url} target="_blank" rel="noopener noreferrer">{justCreated.issue_key}</a> in Jira.
            </div>
          )}
          {projectKey ? <TicketForm projectKey={projectKey} onCreated={handleCreated} /> : <p className="muted">Pick a project to start.</p>}
        </section>

        <section className="card">
          <h2>Recent tickets <span className="muted">· from this app, in {projectKey || "…"}</span></h2>
          <RecentTickets tickets={recent} loading={loadingRecent} />
        </section>
      </div>
    </>
  );
}

// localStorage can be unavailable (private mode, blocked storage); never let that break the page.
function safeGet(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function safeSet(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* ignore */ }
}
