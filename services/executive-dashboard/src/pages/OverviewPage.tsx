import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Incident, Investigation, Proposal } from "../api/types";
import { AlertTrendChart, ConfidenceChart } from "../components/Charts";
import {
  alertTrendByDay,
  computeMttdMinutes,
  computeMttrMinutes,
  confidenceSeries,
  severityClass,
  statusClass,
} from "../lib/metrics";

export function OverviewPage() {
  const navigate = useNavigate();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [pending, setPending] = useState<Proposal[]>([]);
  const [pairs, setPairs] = useState<
    Array<{ incident: Incident; investigation: Investigation | null }>
  >([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const [list, queue] = await Promise.all([
          api.listIncidents({ page_size: 100 }),
          api.listPendingRemediations().catch(() => [] as Proposal[]),
        ]);
        if (cancelled) return;
        setIncidents(list.items);
        setPending(queue);

        const recent = list.items.slice(0, 15);
        const inv = await Promise.all(
          recent.map(async (incident) => {
            try {
              const investigation = await api.getInvestigation(incident.id);
              return { incident, investigation };
            } catch {
              return { incident, investigation: null };
            }
          }),
        );
        if (!cancelled) setPairs(inv);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const openCount = incidents.filter((i) => i.status === "open" || i.status === "acknowledged").length;
  const mttr = computeMttrMinutes(incidents);
  const mttd = computeMttdMinutes(incidents);
  const trend = alertTrendByDay(incidents);
  const conf = confidenceSeries(pairs);

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Platform overview</h1>
          <p>Executive KPIs across detection, investigation, and remediation.</p>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="kpi-row">
        <div className="kpi">
          <div className="kpi-label">Open incidents</div>
          <div className="kpi-value">{loading ? "…" : openCount}</div>
          <div className="kpi-hint">{incidents.length} total tracked</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">MTTR</div>
          <div className="kpi-value">
            {mttr == null ? "—" : `${Math.round(mttr)}m`}
          </div>
          <div className="kpi-hint">Mean time to resolve</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">MTTD signal</div>
          <div className="kpi-value">
            {mttd == null ? "—" : `${Math.round(mttd)}m`}
          </div>
          <div className="kpi-hint">Open incident age / proxy</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Remediation queue</div>
          <div className="kpi-value">{loading ? "…" : pending.length}</div>
          <div className="kpi-hint">Awaiting human approval</div>
        </div>
      </section>

      <div className="grid-2">
        <section className="panel">
          <h2>Alert trends (7d)</h2>
          <AlertTrendChart data={trend} />
        </section>
        <section className="panel">
          <h2>AI confidence</h2>
          <ConfidenceChart data={conf} />
        </section>
      </div>

      <section className="panel">
        <h2>Recent incidents</h2>
        {incidents.length === 0 && !loading ? (
          <p className="empty">No incidents yet. Trigger a fault or wait for alerts.</p>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Service</th>
                  <th>Occurrences</th>
                </tr>
              </thead>
              <tbody>
                {incidents.slice(0, 8).map((i) => (
                  <tr key={i.id} onClick={() => navigate(`/incidents/${i.id}`)}>
                    <td>
                      <Link to={`/incidents/${i.id}`} onClick={(e) => e.stopPropagation()}>
                        {i.title}
                      </Link>
                    </td>
                    <td>
                      <span className={`badge ${severityClass(i.severity)}`}>{i.severity}</span>
                    </td>
                    <td>
                      <span className={`badge ${statusClass(i.status)}`}>{i.status}</span>
                    </td>
                    <td className="mono">{i.service || "—"}</td>
                    <td>{i.occurrence_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
