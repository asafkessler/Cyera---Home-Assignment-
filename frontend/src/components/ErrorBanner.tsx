import { ApiError } from "../api/client";

/** Shows a backend error the way the backend phrased it, plus a hint for the common cases. */
export function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  const hint = error instanceof ApiError ? hintFor(error.code) : null;
  return (
    <div className="banner banner-error" role="alert">
      <strong>{message}</strong>
      {hint && <div className="banner-hint">{hint}</div>}
    </div>
  );
}

function hintFor(code: string): string | null {
  switch (code) {
    case "jira_auth_failed":
      return "Tip: the token must belong to the email you entered, and the site URL must be your Atlassian site (…atlassian.net).";
    case "jira_not_connected":
      return "Connect your Jira workspace first.";
    default:
      return null;
  }
}
