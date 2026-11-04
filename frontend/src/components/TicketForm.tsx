import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { jira, tickets } from "../api/endpoints";
import type { IdentityType, IssueType, Severity, Ticket } from "../api/types";
import { ErrorBanner } from "./ErrorBanner";

const SEVERITIES: Severity[] = ["low", "medium", "high", "critical"];
const IDENTITY_TYPES: { value: IdentityType; label: string }[] = [
  { value: "service_account", label: "Service account" },
  { value: "api_key", label: "API key" },
  { value: "service_principal", label: "Service principal" },
  { value: "other", label: "Other" },
];

interface Props {
  projectKey: string;
  onCreated: (ticket: Ticket) => void;
}

/** The NHI finding form. Issue types are loaded per project; "Task" is preselected when available. */
export function TicketForm({ projectKey, onCreated }: Props) {
  const [issueTypes, setIssueTypes] = useState<IssueType[]>([]);
  const [issueType, setIssueType] = useState("Task");
  const [summary, setSummary] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<Severity | "">("");
  const [identityType, setIdentityType] = useState<IdentityType | "">("");
  const [error, setError] = useState<unknown>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setError(null);
    jira
      .issueTypes(projectKey)
      .then((types) => {
        setIssueTypes(types);
        setIssueType(types.some((t) => t.name === "Task") ? "Task" : (types[0]?.name ?? "Task"));
      })
      .catch(setError);
  }, [projectKey]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setFieldErrors({});
    try {
      const ticket = await tickets.create({
        project_key: projectKey,
        summary,
        description,
        issue_type: issueType,
        severity: severity || undefined,
        identity_type: identityType || undefined,
      });
      setSummary("");
      setDescription("");
      setSeverity("");
      setIdentityType("");
      onCreated(ticket);
    } catch (err) {
      setError(err);
      if (err instanceof ApiError) setFieldErrors(err.fieldProblems);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="form">
      <label>
        Title
        <input
          type="text"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          placeholder="Stale service account: svc-deploy-prod"
          maxLength={255}
          required
        />
        {fieldErrors.summary && <span className="field-error">{fieldErrors.summary}</span>}
      </label>
      <label>
        Description
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What was observed, where, and what should be done."
          rows={5}
          required
        />
        {fieldErrors.description && <span className="field-error">{fieldErrors.description}</span>}
      </label>
      <div className="grid-3">
        <label>
          Severity
          <select value={severity} onChange={(e) => setSeverity(e.target.value as Severity | "")}>
            <option value="">Not set</option>
            {SEVERITIES.map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
          </select>
        </label>
        <label>
          Identity type
          <select value={identityType} onChange={(e) => setIdentityType(e.target.value as IdentityType | "")}>
            <option value="">Not set</option>
            {IDENTITY_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </label>
        <label>
          Issue type
          <select value={issueType} onChange={(e) => setIssueType(e.target.value)}>
            {issueTypes.map((t) => <option key={t.id} value={t.name} title={t.description}>{t.name}</option>)}
            {issueTypes.length === 0 && <option value={issueType}>{issueType}</option>}
          </select>
          {fieldErrors.issue_type && <span className="field-error">{fieldErrors.issue_type}</span>}
        </label>
      </div>
      <ErrorBanner error={error} />
      <button className="btn btn-primary" disabled={busy}>{busy ? "Creating in Jira…" : "Create ticket"}</button>
    </form>
  );
}
