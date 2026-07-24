import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Proposal } from "../api/types";
import { getOperator, statusClass } from "../lib/metrics";

export function RemediationsPage() {
  const [items, setItems] = useState<Proposal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setItems(await api.listPendingRemediations());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 15_000);
    return () => clearInterval(t);
  }, [load]);

  async function approve(id: string) {
    setBusyId(id);
    try {
      await api.approveRemediation(id, getOperator(), "Approved from executive queue");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  async function reject(id: string) {
    setBusyId(id);
    try {
      await api.rejectRemediation(id, getOperator(), "Rejected from executive queue");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  async function execute(id: string) {
    setBusyId(id);
    try {
      await api.executeRemediation(id, getOperator(), false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Remediation queue</h1>
          <p>Human approval required — nothing executes automatically.</p>
        </div>
        <button className="btn" onClick={() => void load()}>
          Refresh
        </button>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="panel">
        {!items.length ? (
          <p className="empty">Queue is empty. Propose remediations from an incident with RCA.</p>
        ) : (
          items.map((p) => (
            <article className="proposal" key={p.id}>
              <div className="meta-row">
                <span className={`badge ${statusClass(p.status)}`}>{p.status}</span>
                <span className="badge">{p.action_type}</span>
                <span className="badge">{p.risk_level}</span>
                <Link className="mono" to={`/incidents/${p.incident_id}`}>
                  incident {p.incident_id.slice(0, 8)}…
                </Link>
              </div>
              <h3>{p.title}</h3>
              <p className="muted">{p.rationale}</p>
              <div className="btn-row" style={{ marginTop: "0.75rem" }}>
                {p.status === "proposed" && (
                  <>
                    <button
                      className="btn btn-primary"
                      disabled={busyId === p.id}
                      onClick={() => void approve(p.id)}
                    >
                      Approve
                    </button>
                    <button
                      className="btn btn-danger"
                      disabled={busyId === p.id}
                      onClick={() => void reject(p.id)}
                    >
                      Reject
                    </button>
                  </>
                )}
                {p.status === "approved" && (
                  <button
                    className="btn btn-primary"
                    disabled={busyId === p.id}
                    onClick={() => void execute(p.id)}
                  >
                    Execute
                  </button>
                )}
              </div>
            </article>
          ))
        )}
      </section>
    </>
  );
}
