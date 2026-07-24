type Node = { id: string; label: string; state: "idle" | "active" | "done" };

export function InvestigationGraph({
  hasContext,
  hasInvestigation,
  hasRca,
  hasRemediation,
}: {
  hasContext: boolean;
  hasInvestigation: boolean;
  hasRca: boolean;
  hasRemediation: boolean;
}) {
  const nodes: Node[] = [
    { id: "alert", label: "Alert", state: "done" },
    {
      id: "context",
      label: "Context",
      state: hasContext ? "done" : hasInvestigation ? "idle" : "active",
    },
    {
      id: "investigate",
      label: "Investigate",
      state: hasInvestigation ? "done" : hasContext ? "active" : "idle",
    },
    {
      id: "rca",
      label: "RCA",
      state: hasRca ? "done" : hasInvestigation ? "active" : "idle",
    },
    {
      id: "remediate",
      label: "Remediate",
      state: hasRemediation ? "done" : hasRca ? "active" : "idle",
    },
  ];

  return (
    <div className="graph" aria-label="Investigation pipeline">
      {nodes.map((n, i) => (
        <span key={n.id} style={{ display: "contents" }}>
          {i > 0 && <span className="graph-arrow">→</span>}
          <span className={`graph-node ${n.state}`}>{n.label}</span>
        </span>
      ))}
    </div>
  );
}
