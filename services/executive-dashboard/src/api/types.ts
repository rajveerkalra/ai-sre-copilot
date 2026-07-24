export type IncidentStatus = "open" | "acknowledged" | "resolved" | "suppressed";
export type IncidentSeverity = "critical" | "high" | "warning" | "info";

export interface Incident {
  id: string;
  title: string;
  status: IncidentStatus;
  severity: IncidentSeverity;
  fingerprint: string;
  occurrence_count: number;
  alertname: string | null;
  service: string | null;
  namespace: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface TimelineEvent {
  id: string;
  event_type: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface IncidentDetail extends Incident {
  timeline: TimelineEvent[];
}

export interface IncidentListResponse {
  items: Incident[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Investigation {
  id: string;
  incident_id: string;
  status: string;
  correlation_id: string;
  model_name: string | null;
  prompt_version: string;
  used_fallback: boolean;
  confidence: number | null;
  duration_ms: number | null;
  report: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface RcaReport {
  investigation_id: string;
  root_cause: string;
  confidence: number;
  business_impact: string;
  next_steps: string[];
  evidence_ids: string[];
  unknowns: string[];
  supporting_runbooks: string[];
  used_fallback: boolean;
  full_report: Record<string, unknown>;
}

export interface InvestigationContext {
  id: string;
  incident_id: string;
  status: string;
  correlation_id: string;
  collected_at: string | null;
  duration_ms: number | null;
  context: Record<string, unknown>;
  metrics: Record<string, unknown>;
  logs: Record<string, unknown>;
  kubernetes: Record<string, unknown>;
  deployment: Record<string, unknown>;
  system: Record<string, unknown>;
  metadata: Record<string, unknown>;
  collector_runs: Array<{
    id: string;
    collector_name: string;
    status: string;
    attempt_count: number;
    duration_ms: number | null;
    started_at: string;
    finished_at: string | null;
  }>;
  created_at: string;
}

export interface Proposal {
  id: string;
  incident_id: string;
  investigation_id: string | null;
  action_type: string;
  title: string;
  rationale: string;
  parameters: Record<string, unknown>;
  confidence: number;
  risk_level: string;
  requires_dry_run_default: boolean;
  status: string;
  evidence_ids: unknown[];
  root_cause: string;
  created_at: string;
  updated_at: string;
}
