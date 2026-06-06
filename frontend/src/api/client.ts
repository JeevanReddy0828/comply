// Thin typed wrapper over fetch. Carries the JWT, normalizes FastAPI errors,
// and exposes one method per backend endpoint the pilot needs.

import type {
  AISystem,
  Compliance,
  ControlSummary,
  Evidence,
  EvidenceCreate,
  SystemCreate,
  TokenResponse,
} from "./types";

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

const TOKEN_KEY = "comply.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

function extractDetail(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    // FastAPI validation errors come back as a list of {loc, msg, ...}
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join("; ");
    }
  }
  return fallback;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, `Could not reach the Comply API at ${BASE_URL}. Is the backend running?`);
  }

  // Session expiry: a 401 while we were carrying a token means the JWT is no
  // longer valid. Clear it and bounce to login rather than surfacing confusing
  // inline errors. (A 401 with no token is a failed login/register — let it
  // through so the form can show "invalid credentials".)
  if (res.status === 401 && getToken()) {
    setToken(null);
    if (!window.location.pathname.startsWith("/login")) window.location.href = "/login";
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const body = text ? JSON.parse(text) : null;

  if (!res.ok) {
    throw new ApiError(res.status, extractDetail(body, `Request failed (${res.status})`));
  }
  return body as T;
}

export const api = {
  // auth
  register: (body: { organization_name: string; email: string; password: string; name?: string }) =>
    request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => request<TokenResponse["user"]>("/auth/me"),

  // systems
  listSystems: () => request<AISystem[]>("/systems"),
  getSystem: (id: string) => request<AISystem>(`/systems/${id}`),
  createSystem: (body: SystemCreate) =>
    request<AISystem>("/systems", { method: "POST", body: JSON.stringify(body) }),

  // assessments
  runAssessment: (systemId: string) =>
    request<Compliance>(`/assessments/run/${systemId}`, { method: "POST" }),
  getCompliance: (systemId: string) => request<Compliance>(`/systems/${systemId}/compliance`),

  // evidence
  listEvidence: (systemId: string) => request<Evidence[]>(`/systems/${systemId}/evidence`),
  addEvidence: (systemId: string, body: EvidenceCreate) =>
    request<Evidence>(`/systems/${systemId}/evidence`, { method: "POST", body: JSON.stringify(body) }),

  // catalog
  listControls: () => request<ControlSummary[]>("/catalog/controls"),
};
