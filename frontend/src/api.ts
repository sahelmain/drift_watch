import type {
  AuthResponse,
  Suite,
  TestRun,
  DriftScore,
  AlertConfig,
  AlertEvent,
  Policy,
  AuditEvent,
  OrgSettings,
  PaginatedResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL || "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchApi<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = localStorage.getItem("dw_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    localStorage.removeItem("dw_token");
    localStorage.removeItem("dw_user");
    window.location.href = "/login";
    throw new ApiError(401, "Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export { ApiError };

// Auth
export async function login(
  email: string,
  password: string,
): Promise<AuthResponse> {
  return fetchApi<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(
  email: string,
  password: string,
  orgName: string,
): Promise<AuthResponse> {
  return fetchApi<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, org_name: orgName }),
  });
}

// Suites
export async function getSuites(): Promise<Suite[]> {
  const res = await fetchApi<{ items: Suite[] } | Suite[]>("/suites");
  return Array.isArray(res) ? res : (res as { items: Suite[] }).items ?? [];
}

export async function createSuite(
  data: Partial<Suite>,
): Promise<Suite> {
  return fetchApi<Suite>("/suites", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getSuite(id: string): Promise<Suite> {
  return fetchApi<Suite>(`/suites/${id}`);
}

export async function updateSuite(
  id: string,
  data: Partial<Suite>,
): Promise<Suite> {
  return fetchApi<Suite>(`/suites/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteSuite(id: string): Promise<void> {
  return fetchApi<void>(`/suites/${id}`, { method: "DELETE" });
}

// Runs
export async function triggerRun(suiteId: string): Promise<TestRun> {
  return fetchApi<TestRun>(`/suites/${suiteId}/run`, {
    method: "POST",
  });
}

export async function getRuns(params?: {
  suite_id?: string;
  status?: string;
  page?: number;
  limit?: number;
}): Promise<PaginatedResponse<TestRun>> {
  const searchParams = new URLSearchParams();
  if (params?.suite_id) searchParams.set("suite_id", params.suite_id);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  const qs = searchParams.toString();
  return fetchApi<PaginatedResponse<TestRun>>(`/runs${qs ? `?${qs}` : ""}`);
}

export async function getRun(id: string): Promise<TestRun> {
  return fetchApi<TestRun>(`/runs/${id}`);
}

// Drift
export async function getDriftTimeline(
  suiteId: string,
): Promise<DriftScore[]> {
  return fetchApi<DriftScore[]>(`/drift/${suiteId}`);
}

// Alerts
export async function getAlerts(): Promise<AlertConfig[]> {
  return fetchApi<AlertConfig[]>("/alerts");
}

export async function createAlert(
  data: Partial<AlertConfig>,
): Promise<AlertConfig> {
  return fetchApi<AlertConfig>("/alerts", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateAlert(
  id: string,
  data: Partial<AlertConfig>,
): Promise<AlertConfig> {
  return fetchApi<AlertConfig>(`/alerts/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteAlert(id: string): Promise<void> {
  return fetchApi<void>(`/alerts/${id}`, { method: "DELETE" });
}

export async function getAlertEvents(): Promise<AlertEvent[]> {
  return [];
}

export async function testWebhook(data: {
  channel: string;
  destination: string;
}): Promise<{ status: string }> {
  return fetchApi<{ status: string }>("/webhooks/test", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Policies
export async function getPolicies(): Promise<Policy[]> {
  return fetchApi<Policy[]>("/policies");
}

export async function createPolicy(
  data: Partial<Policy>,
): Promise<Policy> {
  return fetchApi<Policy>("/policies", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updatePolicy(
  id: string,
  data: Partial<Policy>,
): Promise<Policy> {
  return fetchApi<Policy>(`/policies/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deletePolicy(id: string): Promise<void> {
  return fetchApi<void>(`/policies/${id}`, { method: "DELETE" });
}

// Audit
export async function getAuditLog(params?: {
  page?: number;
  limit?: number;
}): Promise<PaginatedResponse<AuditEvent>> {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  const qs = searchParams.toString();
  return fetchApi<PaginatedResponse<AuditEvent>>(
    `/audit-log${qs ? `?${qs}` : ""}`,
  );
}

// Settings
export async function getSettings(): Promise<OrgSettings> {
  return fetchApi<OrgSettings>("/settings");
}

export async function updateSettings(
  data: { org?: Partial<OrgSettings["org"]> },
): Promise<OrgSettings> {
  return fetchApi<OrgSettings>("/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function createApiKey(
  name: string,
): Promise<{ key: string }> {
  const res = await fetchApi<{ raw_key: string }>("/settings/api-keys", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  return { key: res.raw_key };
}

export async function revokeApiKey(id: string): Promise<void> {
  return fetchApi<void>(`/settings/api-keys/${id}`, { method: "DELETE" });
}

export async function inviteMember(
  email: string,
  role: string,
): Promise<void> {
  return fetchApi<void>("/settings/members", {
    method: "POST",
    body: JSON.stringify({ email, password: "changeme1", role }),
  });
}
