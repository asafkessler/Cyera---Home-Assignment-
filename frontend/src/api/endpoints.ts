// One function per backend endpoint. Pages import these, never `http` directly.
import { http } from "./client";
import type {
  ApiKey, ApiKeyCreated, CreateTicketInput, IssueType, JiraConnection, Project, Ticket, User,
} from "./types";

export const auth = {
  me: () => http.get<User>("/api/auth/me"),
  register: (email: string, password: string) => http.post<User>("/api/auth/register", { email, password }),
  login: (email: string, password: string) => http.post<User>("/api/auth/login", { email, password }),
  logout: () => http.post<void>("/api/auth/logout"),
};

export const jira = {
  connection: () => http.get<JiraConnection>("/api/jira/connection"),
  connect: (site_url: string, email: string, api_token: string) =>
    http.put<JiraConnection>("/api/jira/connection", { site_url, email, api_token }),
  disconnect: () => http.delete<void>("/api/jira/connection"),
  projects: () => http.get<Project[]>("/api/jira/projects"),
  issueTypes: (projectKey: string) => http.get<IssueType[]>(`/api/jira/projects/${encodeURIComponent(projectKey)}/issue-types`),
};

export const tickets = {
  create: (input: CreateTicketInput) => http.post<Ticket>("/api/tickets", input),
  recent: (projectKey: string, limit = 10) =>
    http.get<Ticket[]>(`/api/tickets?project_key=${encodeURIComponent(projectKey)}&limit=${limit}`),
};

export const apiKeys = {
  list: () => http.get<ApiKey[]>("/api/keys"),
  create: (name: string) => http.post<ApiKeyCreated>("/api/keys", { name }),
  revoke: (id: number) => http.delete<void>(`/api/keys/${id}`),
};
