import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Incident } from "../api/types";
import { severityClass, statusClass } from "../lib/metrics";

export function IncidentsPage() {
  const [items, setItems] = useState<Incident[]>([]);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.listIncidents({
          status: status || undefined,
          page_size: 100,
        });
        if (!cancelled) setItems(res.items);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status]);

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Incidents</h1>
          <p>Browse open and historical incidents from the incident engine.</p>
        </div>
        <select
          className="btn"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </select>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="panel">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Title</th>
                <th>Alert</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} onClick={() => navigate(`/incidents/${i.id}`)}>
                  <td>
                    <Link to={`/incidents/${i.id}`}>{i.title}</Link>
                  </td>
                  <td className="mono">{i.alertname || "—"}</td>
                  <td>
                    <span className={`badge ${severityClass(i.severity)}`}>{i.severity}</span>
                  </td>
                  <td>
                    <span className={`badge ${statusClass(i.status)}`}>{i.status}</span>
                  </td>
                  <td className="mono">{new Date(i.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!items.length && <p className="empty">No incidents match this filter.</p>}
        </div>
      </section>
    </>
  );
}
