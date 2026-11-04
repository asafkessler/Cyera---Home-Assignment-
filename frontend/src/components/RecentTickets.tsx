import type { Ticket } from "../api/types";
import { formatRelative } from "../format";

/** The 10 most recent tickets created from this app in the selected project. */
export function RecentTickets({ tickets, loading }: { tickets: Ticket[]; loading: boolean }) {
  if (loading) return <p className="muted">Loading…</p>;
  if (tickets.length === 0) return <p className="muted">No tickets created from this app yet in this project.</p>;
  return (
    <ul className="ticket-list">
      {tickets.map((t) => (
        <li key={t.id} className="ticket">
          <a href={t.issue_url} target="_blank" rel="noopener noreferrer" className="ticket-link" title="Open in Jira (new tab)">
            <span className="ticket-key">{t.issue_key}</span>
            <span className="ticket-summary">{t.summary}</span>
          </a>
          <span className="ticket-meta">
            <span className={`pill pill-${t.source}`}>{t.source === "api" ? "API" : "Form"}</span>
            <time dateTime={t.created_at} title={new Date(t.created_at).toLocaleString()}>{formatRelative(t.created_at)}</time>
          </span>
        </li>
      ))}
    </ul>
  );
}
