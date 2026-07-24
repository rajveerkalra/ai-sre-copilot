async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("sre_access_token");
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("sre_access_token");
    localStorage.removeItem("sre_auth_user");
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${text ? `: ${text.slice(0, 200)}` : ""}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const I = "/proxy/incident";
const C = "/proxy/context";
const V = "/proxy/investigation";
const R = "/proxy/remediation";

export const api = {
  listIncidents: (params?: { status?: string; page_size?: number; page?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    q.set("page_size", String(params?.page_size ?? 50));
    q.set("page", String(params?.page ?? 1));
    return request<import("./types").IncidentListResponse>(`${I}/incidents?${q}`);
  },

  getIncident: (id: string) =>
    request<import("./types").IncidentDetail>(`${I}/incidents/${id}`),

  getTimeline: (id: string) =>
    request<import("./types").TimelineEvent[]>(`${I}/incidents/${id}/timeline`),

  getContext: (id: string) =>
    request<import("./types").InvestigationContext>(`${C}/incidents/${id}/context`),

  getInvestigation: (incidentId: string) =>
    request<import("./types").Investigation>(`${V}/incidents/${incidentId}/investigation`),

  getRca: (investigationId: string) =>
    request<import("./types").RcaReport>(`${V}/investigations/${investigationId}/rca`),

  getEvidence: (investigationId: string) =>
    request<{ investigation_id: string; evidence: unknown[] }>(
      `${V}/investigations/${investigationId}/evidence`,
    ),

  listPendingRemediations: () =>
    request<import("./types").Proposal[]>(`${R}/remediations/pending`),

  listRemediations: (incidentId: string) =>
    request<import("./types").Proposal[]>(`${R}/incidents/${incidentId}/remediations`),

  proposeRemediations: (incidentId: string) =>
    request<{ count: number; proposals: import("./types").Proposal[] }>(
      `${R}/incidents/${incidentId}/remediations/propose`,
      { method: "POST" },
    ),

  approveRemediation: (id: string, approved_by: string, comment = "") =>
    request<import("./types").Proposal>(`${R}/remediations/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved_by, comment }),
    }),

  rejectRemediation: (id: string, rejected_by: string, comment = "") =>
    request<import("./types").Proposal>(`${R}/remediations/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ rejected_by, comment }),
    }),

  executeRemediation: (id: string, actor: string, dry_run?: boolean) =>
    request<{ status: string; dry_run: boolean; error?: string }>(
      `${R}/remediations/${id}/execute`,
      {
        method: "POST",
        body: JSON.stringify({ actor, dry_run }),
      },
    ),
};
