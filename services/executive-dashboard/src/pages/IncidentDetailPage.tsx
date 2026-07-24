import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  IncidentDetail,
  Investigation,
  InvestigationContext,
  Proposal,
  RcaReport,
  TimelineEvent,
} from "../api/types";
import { InvestigationGraph } from "../components/InvestigationGraph";
import { getOperator, severityClass, statusClass } from "../lib/metrics";

type Tab = "timeline" | "rca" | "evidence" | "remediations";

export function IncidentDetailPage() {
  const { id = "" } = useParams();
  const [tab, setTab] = useState<Tab>("timeline");
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [rca, setRca] = useState<RcaReport | null>(null);
  const [context, setContext] = useState<InvestigationContext | null>(null);
  const [evidence, setEvidence] = useState<unknown[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setError(null);
    try {
      const [inc, tl] = await Promise.all([api.getIncident(id), api.getTimeline(id)]);
      setIncident(inc);
      setTimeline(tl);

      const [ctx, inv, rems] = await Promise.all([
        api.getContext(id).catch(() => null),
        api.getInvestigation(id).catch(() => null),
        api.listRemediations(id).catch(() => [] as Proposal[]),
      ]);
      setContext(ctx);
      setInvestigation(inv);
      setProposals(rems);

      if (inv) {
        const [r, ev] = await Promise.all([
          api.getRca(inv.id).catch(() => null),
          api.getEvidence(inv.id).catch(() => ({ evidence: [] })),
        ]);
        setRca(r);
        setEvidence(ev.evidence || []);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onPropose() {
    setBusy(true);
    try {
      await api.proposeRemediations(id);
      await load();
      setTab("remediations");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!incident && !error) {
    return <p className="muted">Loading incident…</p>;
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="muted" style={{ marginBottom: "0.35rem" }}>
            <Link to="/incidents">← Incidents</Link>
          </p>
          <h1>{incident?.title || "Incident"}</h1>
          <p className="mono">{id}</p>
        </div>
        <div className="btn-row">
          <button className="btn btn-primary" disabled={busy || !investigation} onClick={onPropose}>
            Propose remediations
          </button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      {incident && (
        <div className="meta-row">
          <span className={`badge ${severityClass(incident.severity)}`}>{incident.severity}</span>
          <span className={`badge ${statusClass(incident.status)}`}>{incident.status}</span>
          <span>
            Service <strong className="mono">{incident.service || "—"}</strong>
          </span>
          <span>
            Occurrences <strong>{incident.occurrence_count}</strong>
          </span>
          <span>
            Created <strong className="mono">{new Date(incident.created_at).toLocaleString()}</strong>
          </span>
        </div>
      )}

      <section className="panel" style={{ marginBottom: "1rem" }}>
        <h2>Investigation graph</h2>
        <InvestigationGraph
          hasContext={Boolean(context)}
          hasInvestigation={Boolean(investigation)}
          hasRca={Boolean(rca)}
          hasRemediation={proposals.length > 0}
        />
      </section>

      <div className="tabs">
        {(
          [
            ["timeline", "Timeline"],
            ["rca", "RCA report"],
            ["evidence", "Evidence"],
            ["remediations", "Remediations"],
          ] as const
        ).map(([k, label]) => (
          <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
      </div>

      {tab === "timeline" && (
        <section className="panel">
          <ul className="timeline">
            {timeline.map((e) => (
              <li key={e.id}>
                <div className="t-type">{e.event_type}</div>
                <p className="t-msg">{e.message}</p>
                <time dateTime={e.created_at}>{new Date(e.created_at).toLocaleString()}</time>
              </li>
            ))}
          </ul>
          {!timeline.length && <p className="empty">No timeline events.</p>}
        </section>
      )}

      {tab === "rca" && (
        <section className="panel">
          {!rca ? (
            <p className="empty">No RCA yet. Run investigation-service first.</p>
          ) : (
            <>
              <p className="rca-lead">{rca.root_cause}</p>
              <div className="meta-row">
                <span>
                  Confidence <strong>{Math.round(rca.confidence <= 1 ? rca.confidence * 100 : rca.confidence)}%</strong>
                </span>
                <span>
                  Fallback <strong>{rca.used_fallback ? "yes" : "no"}</strong>
                </span>
              </div>
              <h2>Business impact</h2>
              <p>{rca.business_impact || "—"}</p>
              <h2>Next steps</h2>
              <ul>
                {(rca.next_steps || []).map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
              {rca.unknowns?.length > 0 && (
                <>
                  <h2>Unknowns</h2>
                  <ul>
                    {rca.unknowns.map((u) => (
                      <li key={u}>{u}</li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </section>
      )}

      {tab === "evidence" && (
        <section className="panel">
          <div className="evidence-grid">
            {context && (
              <>
                {(["metrics", "logs", "kubernetes", "deployment", "system"] as const).map((key) => (
                  <div className="evidence-block" key={key}>
                    <h3>{key}</h3>
                    <pre>{JSON.stringify(context[key] || {}, null, 2)}</pre>
                  </div>
                ))}
              </>
            )}
            {evidence.length > 0 && (
              <div className="evidence-block">
                <h3>Investigation evidence</h3>
                <pre>{JSON.stringify(evidence, null, 2)}</pre>
              </div>
            )}
            {!context && !evidence.length && (
              <p className="empty">No evidence collected for this incident.</p>
            )}
          </div>
        </section>
      )}

      {tab === "remediations" && (
        <section className="panel">
          {proposals.map((p) => (
            <ProposalCard key={p.id} proposal={p} onChanged={load} />
          ))}
          {!proposals.length && (
            <p className="empty">
              No proposals. Use “Propose remediations” after RCA is available.
            </p>
          )}
        </section>
      )}
    </>
  );
}

function ProposalCard({
  proposal: p,
  onChanged,
}: {
  proposal: Proposal;
  onChanged: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const operator = getOperator();

  async function act(kind: "approve" | "reject" | "execute") {
    setBusy(true);
    setErr(null);
    try {
      if (kind === "approve") await api.approveRemediation(p.id, operator);
      if (kind === "reject") await api.rejectRemediation(p.id, operator);
      if (kind === "execute") await api.executeRemediation(p.id, operator, false);
      await onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="proposal">
      <div className="meta-row" style={{ marginBottom: "0.35rem" }}>
        <span className={`badge st-${p.status}`}>{p.status}</span>
        <span className="badge">{p.action_type}</span>
        <span className="badge">{p.risk_level} risk</span>
      </div>
      <h3>{p.title}</h3>
      <p className="muted">{p.rationale}</p>
      {err && <p className="error-banner">{err}</p>}
      <div className="btn-row" style={{ marginTop: "0.75rem" }}>
        {p.status === "proposed" && (
          <>
            <button className="btn btn-primary" disabled={busy} onClick={() => act("approve")}>
              Approve
            </button>
            <button className="btn btn-danger" disabled={busy} onClick={() => act("reject")}>
              Reject
            </button>
          </>
        )}
        {p.status === "approved" && (
          <button className="btn btn-primary" disabled={busy} onClick={() => act("execute")}>
            Execute
          </button>
        )}
      </div>
    </article>
  );
}
