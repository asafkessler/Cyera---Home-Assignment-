/**
 * The only module that talks HTTP.
 *
 * Every backend error has the same shape ({error: {code, message, details}}),
 * so one place turns it into a typed ApiError that pages can branch on by
 * `code` or show by `message`. Cookies are sent automatically because the
 * UI and the API share an origin (see vite.config.ts / nginx.conf).
 */

export interface FieldProblem {
  field: string;
  problem: string;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Per-field problems from a 422, keyed by field name, for inline form errors. */
  get fieldProblems(): Record<string, string> {
    const fields = (this.details.fields as FieldProblem[] | undefined) ?? [];
    return Object.fromEntries(fields.map((f) => [f.field, f.problem]));
  }
}

type Method = "GET" | "POST" | "PUT" | "DELETE";

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the server. Is the backend running?");
  }

  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const err = payload?.error;
    throw new ApiError(
      response.status,
      err?.code ?? "unknown_error",
      err?.message ?? `Request failed with status ${response.status}.`,
      err?.details ?? {},
    );
  }
  return payload as T;
}

export const http = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};
