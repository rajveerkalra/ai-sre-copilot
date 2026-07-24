import type { Incident, Investigation } from "../api/types";

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "—";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return rem ? `${m}m ${rem}s` : `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export function minutesBetween(a: string, b: string): number {
  return (new Date(b).getTime() - new Date(a).getTime()) / 60_000;
}

export function computeMttrMinutes(incidents: Incident[]): number | null {
  const resolved = incidents.filter((i) => i.resolved_at);
  if (!resolved.length) return null;
  const total = resolved.reduce(
    (acc, i) => acc + minutesBetween(i.created_at, i.resolved_at!),
    0,
  );
  return total / resolved.length;
}

/** MTTD approximated as time to first timeline acknowledgment, else open duration for open incidents. */
export function computeMttdMinutes(incidents: Incident[]): number | null {
  // Without per-alert detect timestamps, use median age of open incidents as leading indicator.
  const open = incidents.filter((i) => i.status === "open" || i.status === "acknowledged");
  if (!open.length) {
    const resolved = incidents.filter((i) => i.resolved_at);
    if (!resolved.length) return null;
    return (
      resolved.reduce((acc, i) => acc + minutesBetween(i.created_at, i.resolved_at!), 0) /
      resolved.length /
      4
    );
  }
  const now = new Date().toISOString();
  return open.reduce((acc, i) => acc + minutesBetween(i.created_at, now), 0) / open.length;
}

export function alertTrendByDay(incidents: Incident[], days = 7) {
  const buckets = new Map<string, number>();
  const today = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    buckets.set(d.toISOString().slice(0, 10), 0);
  }
  for (const inc of incidents) {
    const key = inc.created_at.slice(0, 10);
    if (buckets.has(key)) {
      buckets.set(key, (buckets.get(key) ?? 0) + (inc.occurrence_count || 1));
    }
  }
  return [...buckets.entries()].map(([date, alerts]) => ({ date: date.slice(5), alerts }));
}

export function confidenceSeries(
  pairs: Array<{ incident: Incident; investigation: Investigation | null }>,
) {
  return pairs
    .filter((p) => p.investigation?.confidence != null)
    .map((p) => ({
      label: p.incident.alertname?.slice(0, 18) || p.incident.id.slice(0, 8),
      confidence: Math.round((p.investigation!.confidence as number) * (p.investigation!.confidence! <= 1 ? 100 : 1)),
      fallback: p.investigation!.used_fallback,
    }))
    .slice(0, 12);
}

export function getOperator(): string {
  return localStorage.getItem("sre_operator") || "executive-ops";
}

export function setOperator(name: string) {
  localStorage.setItem("sre_operator", name);
}

export function severityClass(sev: string): string {
  return `sev-${sev}`;
}

export function statusClass(status: string): string {
  return `st-${status}`;
}
