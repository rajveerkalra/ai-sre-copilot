"""LangGraph investigation workflow."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.investigators import (
    citation_validator,
    evidence_aggregator,
    final_report,
    kubernetes_investigator,
    logs_investigator,
    metrics_investigator,
    rca_synthesizer,
    runbook_investigator,
)
from app.graph.state import InvestigationState


def build_investigation_graph():
    # Node names must not collide with InvestigationState keys (e.g. rca, report).
    graph = StateGraph(InvestigationState)
    graph.add_node("metrics_agent", metrics_investigator)
    graph.add_node("logs_agent", logs_investigator)
    graph.add_node("kubernetes_agent", kubernetes_investigator)
    graph.add_node("runbook_agent", runbook_investigator)
    graph.add_node("aggregate_evidence", evidence_aggregator)
    graph.add_node("synthesize_rca", rca_synthesizer)
    graph.add_node("validate_citations", citation_validator)
    graph.add_node("build_report", final_report)

    graph.set_entry_point("metrics_agent")
    graph.add_edge("metrics_agent", "logs_agent")
    graph.add_edge("logs_agent", "kubernetes_agent")
    graph.add_edge("kubernetes_agent", "runbook_agent")
    graph.add_edge("runbook_agent", "aggregate_evidence")
    graph.add_edge("aggregate_evidence", "synthesize_rca")
    graph.add_edge("synthesize_rca", "validate_citations")
    graph.add_edge("validate_citations", "build_report")
    graph.add_edge("build_report", END)
    return graph.compile()


# Singleton compiled graph
investigation_graph = build_investigation_graph()
