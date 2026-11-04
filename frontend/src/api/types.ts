// Mirrors the backend's response models. Kept by hand (small API) so the
// frontend has one typed view of what the server returns.

export interface User {
  id: number;
  email: string;
  created_at: string;
  jira_connected: boolean;
}

export interface JiraConnection {
  connected: boolean;
  site_url: string | null;
  email: string | null;
  display_name: string | null;
  connected_at: string | null;
  last_verified_at: string | null;
}

export interface Project {
  id: string;
  key: string;
  name: string;
}

export interface IssueType {
  id: string;
  name: string;
  description: string;
}

export type Severity = "low" | "medium" | "high" | "critical";
export type IdentityType = "service_account" | "api_key" | "service_principal" | "other";
export type TicketSource = "ui" | "api";

export interface CreateTicketInput {
  project_key: string;
  summary: string;
  description: string;
  severity?: Severity;
  identity_type?: IdentityType;
  issue_type: string;
}

export interface Ticket {
  id: number;
  issue_key: string;
  issue_url: string;
  summary: string;
  project_key: string;
  source: TicketSource;
  created_at: string;
}

export interface ApiKey {
  id: number;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface ApiKeyCreated extends ApiKey {
  key: string; // present only in the create response
}
