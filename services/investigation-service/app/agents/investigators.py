"""Specialized investigation agents."""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.config import get_settings
from app.metrics import AGENT_DURATION_SECONDS, FALLBACK_TOTAL
from app.services.fallback import rule_based_rca
from app.services.model_gateway_client import ModelGatewayClient, ModelGatewayError

logger = structlog.get_logger(__name__)


def _timer(agent: str, status: str, started: float) -> float:
    duration = time.perf_counter() - started
    AGENT_DURATION_SECONDS.labels(agent=agent, status=status).observe(duration)
    return round(duration * 1000, 2)


async def metrics_investigator(state: dict[str, Any]) -> dict[str, Any]:
    agent = "metrics_investigator"
    started = time.perf_counter()
    evidence = [e for e in state.get("evidence", []) if e.get("source") == "metrics"]
    observations = [e["summary"] for e in evidence]
    anomalies = []
    metrics = (state.get("context") or {}).get("metrics") or {}
    for name, series in (metrics.get("series") or {}).items():
        if (series or {}).get("trend") == "up" and name in {
            "error_rate",
            "latency_p95",
            "latency_p99",
            "cpu_usage",
            "memory_usage_bytes",
        }:
            anomalies.append({"metric": name, "evidence_id": f"metric-{name}"})

    result = {
        "agent": agent,
        "observations": observations,
        "anomalies": anomalies,
        "evidence_ids": [e["evidence_id"] for e in evidence],
        "confidence": 75.0 if anomalies else 40.0,
        "used_llm": False,
    }
    # Optional LLM enrichment — must still cite existing evidence IDs only
    result = await _maybe_llm_enrich(
        agent,
        result,
        system=(
            "You are an SRE metrics analyst. Respond ONLY with JSON. "
            "Only reference provided evidence_ids. Never invent metrics."
        ),
        prompt=(
            f"Evidence:\n{evidence[:20]}\n"
            "Return JSON: {\"observations\":[],\"evidence_ids\":[],\"confidence\":0-100}"
        ),
        allowed_ids={e["evidence_id"] for e in evidence},
    )
    result["duration_ms"] = _timer(agent, "success", started)
    logger.info(
        "agent_complete",
        agent=agent,
        duration_ms=result["duration_ms"],
        confidence=result.get("confidence"),
        incident_id=state.get("incident_id"),
        investigation_id=state.get("investigation_id"),
    )
    return {"metrics_result": result}


async def logs_investigator(state: dict[str, Any]) -> dict[str, Any]:
    agent = "logs_investigator"
    started = time.perf_counter()
    evidence = [e for e in state.get("evidence", []) if e.get("source") == "logs"]
    logs = (state.get("context") or {}).get("logs") or {}
    result = {
        "agent": agent,
        "top_exceptions": (logs.get("top_error_messages") or [])[:5],
        "error_frequencies": (logs.get("categories") or {}),
        "stack_traces_present": bool((logs.get("summary") or {}).get("has_stack_traces")),
        "evidence_ids": [e["evidence_id"] for e in evidence],
        "confidence": 70.0 if evidence else 20.0,
        "used_llm": False,
    }
    result = await _maybe_llm_enrich(
        agent,
        result,
        system=(
            "You are an SRE log analyst. JSON only. Cite only provided evidence_ids."
        ),
        prompt=f"Log evidence:\n{evidence[:15]}\nReturn JSON with observations, evidence_ids, confidence.",
        allowed_ids={e["evidence_id"] for e in evidence},
    )
    result["duration_ms"] = _timer(agent, "success", started)
    logger.info(
        "agent_complete",
        agent=agent,
        duration_ms=result["duration_ms"],
        confidence=result.get("confidence"),
        incident_id=state.get("incident_id"),
        investigation_id=state.get("investigation_id"),
    )
    return {"logs_result": result}


async def kubernetes_investigator(state: dict[str, Any]) -> dict[str, Any]:
    agent = "kubernetes_investigator"
    started = time.perf_counter()
    evidence = [
        e
        for e in state.get("evidence", [])
        if e.get("source") in {"kubernetes", "deployment", "system"}
    ]
    k8s = (state.get("context") or {}).get("kubernetes") or {}
    result = {
        "agent": agent,
        "findings": k8s.get("issues") or [],
        "available": k8s.get("available"),
        "evidence_ids": [e["evidence_id"] for e in evidence],
        "confidence": 65.0 if k8s.get("issues") else 30.0,
        "used_llm": False,
    }
    result["duration_ms"] = _timer(agent, "success", started)
    logger.info(
        "agent_complete",
        agent=agent,
        duration_ms=result["duration_ms"],
        confidence=result.get("confidence"),
        incident_id=state.get("incident_id"),
        investigation_id=state.get("investigation_id"),
    )
    return {"kubernetes_result": result}


async def runbook_investigator(state: dict[str, Any]) -> dict[str, Any]:
    agent = "runbook_investigator"
    started = time.perf_counter()
    settings = get_settings()
    meta = ((state.get("context") or {}).get("metadata") or {}).get("incident") or {}
    query_parts = [
        meta.get("alertname") or "",
        meta.get("title") or "",
        " ".join(
            e.get("summary", "")[:80]
            for e in (state.get("evidence") or [])[:8]
        ),
    ]
    query = " ".join(p for p in query_parts if p).strip() or "production incident"
    hits: list[dict[str, Any]] = []
    try:
        from app.services.resilient_http import get_json_post

        data = await get_json_post(
            f"{settings.knowledge_service_url.rstrip('/')}/search",
            json_body={"query": query, "top_k": 5},
            name="knowledge-search",
        )
        hits = data.get("results") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("runbook_search_failed", error=str(exc))

    runbook_evidence = [
        {
            "evidence_id": h.get("evidence_id") or f"runbook-{(h.get('id') or '')[:8]}",
            "source": "runbook",
            "summary": f"Runbook: {h.get('title')} (score={h.get('score')})",
            "raw": h,
        }
        for h in hits
    ]
    result = {
        "agent": agent,
        "query": query,
        "runbooks": hits,
        "evidence_ids": [e["evidence_id"] for e in runbook_evidence],
        "confidence": 60.0 if hits else 10.0,
        "used_llm": False,
        "duration_ms": _timer(agent, "success", started),
    }
    logger.info(
        "agent_complete",
        agent=agent,
        duration_ms=result["duration_ms"],
        confidence=result.get("confidence"),
        incident_id=state.get("incident_id"),
        investigation_id=state.get("investigation_id"),
    )
    return {
        "runbook_result": result,
        "evidence": list(state.get("evidence") or []) + runbook_evidence,
    }


async def evidence_aggregator(state: dict[str, Any]) -> dict[str, Any]:
    agent = "evidence_aggregator"
    started = time.perf_counter()
    pooled: list[dict[str, Any]] = list(state.get("evidence") or [])
    # Ensure uniqueness by evidence_id
    seen: set[str] = set()
    unique = []
    for e in pooled:
        eid = e.get("evidence_id")
        if eid and eid not in seen:
            seen.add(eid)
            unique.append(e)
    _timer(agent, "success", started)
    return {"aggregated_evidence": unique, "evidence": unique}


async def rca_synthesizer(state: dict[str, Any]) -> dict[str, Any]:
    agent = "rca_synthesizer"
    started = time.perf_counter()
    settings = get_settings()
    evidence = state.get("aggregated_evidence") or state.get("evidence") or []
    runbooks = (state.get("runbook_result") or {}).get("runbooks") or []
    agent_outputs = {
        "metrics": state.get("metrics_result"),
        "logs": state.get("logs_result"),
        "kubernetes": state.get("kubernetes_result"),
        "runbooks": state.get("runbook_result"),
    }
    allowed = {e["evidence_id"] for e in evidence}
    used_fallback = False
    rca: dict[str, Any]

    client = ModelGatewayClient(settings)
    try:
        if not await client.available():
            raise ModelGatewayError("Model gateway unavailable")
        system = (
            "You are an experienced SRE producing root cause analysis from monitoring "
            "evidence. Respond ONLY with JSON. Never invent causes, metrics, logs, or IDs "
            "not present in the evidence given to you."
        )
        # Evidence is rendered as readable "- id: summary" lines rather than a raw Python
        # dict repr. On a raw dict repr + a prompt that offers "Insufficient evidence" as
        # an explicit escape hatch, small local models (llama3.2 1B/3B) were found to pick
        # that escape hatch on ~100% of cases regardless of evidence strength -- measured
        # via eval/run_llm_eval.py. Asking a direct question and demanding a concrete
        # diagnosis, with "Insufficient evidence" framed as a last resort rather than a
        # default, fixed this in manual testing; see docs/eval.md for before/after numbers.
        evidence_lines = "\n".join(f"- {e['evidence_id']}: {e['summary']}" for e in evidence[:40])
        prompt = (
            f"Evidence collected for this incident:\n{evidence_lines}\n\n"
            "Based on this evidence, what is the most likely root cause of this incident? "
            "Give a specific, concrete diagnosis -- only answer 'Insufficient evidence' as "
            "a last resort, if the evidence truly contains no relevant signal at all.\n\n"
            "Return JSON with exactly these keys:\n"
            "- root_cause: a plain string diagnosis\n"
            "- confidence: number 0-100\n"
            "- business_impact: plain string\n"
            "- next_steps: array of plain strings\n"
            "- evidence_ids: array containing ONLY entries copied verbatim "
            f"(character-for-character, no added text) from this exact list: {sorted(allowed)}\n"
            "- unknowns: array of plain strings\n\n"
            f"Example of correctly formatted evidence_ids: {sorted(allowed)[:2]} "
            "-- notice these are copied exactly with nothing appended."
        )
        parsed = await client.generate_json(agent=agent, system=system, prompt=prompt)
        cited = [eid for eid in (parsed.get("evidence_ids") or []) if eid in allowed]
        if not cited and parsed.get("root_cause") != "Insufficient evidence":
            raise ModelGatewayError("Model returned no valid citations")
        rca = {
            "root_cause": parsed.get("root_cause") or "Insufficient evidence",
            "confidence": float(parsed.get("confidence") or 0),
            "business_impact": parsed.get("business_impact") or "",
            "next_steps": parsed.get("next_steps") or [],
            "evidence_ids": cited,
            "unknowns": parsed.get("unknowns") or [],
            "supporting_runbooks": runbooks[:3],
            "used_fallback": False,
            "method": "model-gateway",
            "model": client.model,
        }
        if rca["root_cause"] == "Insufficient evidence":
            rca["confidence"] = 0.0
    except ModelGatewayError as exc:
        FALLBACK_TOTAL.labels(agent=agent).inc()
        used_fallback = True
        logger.warning("rca_fallback", error=str(exc), incident_id=state.get("incident_id"))
        rca = rule_based_rca(
            evidence=evidence, agent_outputs=agent_outputs, runbooks=runbooks
        )

    rca["duration_ms"] = _timer(agent, "success", started)
    logger.info(
        "agent_complete",
        agent=agent,
        duration_ms=rca["duration_ms"],
        confidence=rca.get("confidence"),
        used_fallback=used_fallback,
        incident_id=state.get("incident_id"),
        investigation_id=state.get("investigation_id"),
    )
    return {"rca": rca, "used_fallback": used_fallback, "model_name": settings.llm_model}


async def citation_validator(state: dict[str, Any]) -> dict[str, Any]:
    from app.services.fallback import validate_citations

    agent = "citation_validator"
    started = time.perf_counter()
    evidence = state.get("aggregated_evidence") or state.get("evidence") or []
    valid_ids = {e["evidence_id"] for e in evidence}
    rca, removed = validate_citations(dict(state.get("rca") or {}), valid_ids)
    _timer(agent, "success", started)
    if removed:
        logger.warning(
            "citations_removed",
            removed=removed,
            incident_id=state.get("incident_id"),
            investigation_id=state.get("investigation_id"),
        )
    return {"rca": rca}


async def final_report(state: dict[str, Any]) -> dict[str, Any]:
    meta = ((state.get("context") or {}).get("metadata") or {}).get("incident") or {}
    rca = state.get("rca") or {}
    evidence = state.get("aggregated_evidence") or []
    report = {
        "incident_summary": {
            "incident_id": state.get("incident_id"),
            "title": meta.get("title"),
            "alertname": meta.get("alertname"),
            "severity": meta.get("severity"),
            "service": meta.get("service"),
        },
        "timeline": [
            {"agent": "metrics_investigator", "result": state.get("metrics_result")},
            {"agent": "logs_investigator", "result": state.get("logs_result")},
            {"agent": "kubernetes_investigator", "result": state.get("kubernetes_result")},
            {"agent": "runbook_investigator", "result": state.get("runbook_result")},
            {"agent": "rca_synthesizer", "result": {"method": rca.get("method")}},
        ],
        "evidence": evidence,
        "root_cause": rca.get("root_cause"),
        "confidence": rca.get("confidence"),
        "business_impact": rca.get("business_impact"),
        "suggested_actions": rca.get("next_steps"),
        "unknowns": rca.get("unknowns"),
        "supporting_runbooks": rca.get("supporting_runbooks"),
        "evidence_ids": rca.get("evidence_ids"),
        "used_fallback": state.get("used_fallback", False),
        "model_name": state.get("model_name"),
    }
    return {"report": report}


async def _maybe_llm_enrich(
    agent: str,
    base: dict[str, Any],
    *,
    system: str,
    prompt: str,
    allowed_ids: set[str],
) -> dict[str, Any]:
    """Best-effort LLM enrichment; always falls back to deterministic base."""
    settings = get_settings()
    client = ModelGatewayClient(settings)
    try:
        if not await client.available():
            return base
        parsed = await client.generate_json(agent=agent, system=system, prompt=prompt)
        eids = [e for e in (parsed.get("evidence_ids") or base.get("evidence_ids") or []) if e in allowed_ids]
        if not eids and allowed_ids:
            eids = list(base.get("evidence_ids") or [])
        enriched = dict(base)
        if parsed.get("observations"):
            enriched["observations"] = parsed["observations"]
        enriched["evidence_ids"] = eids or list(base.get("evidence_ids") or [])
        if parsed.get("confidence") is not None:
            enriched["confidence"] = float(parsed["confidence"])
        enriched["used_llm"] = True
        return enriched
    except Exception:
        FALLBACK_TOTAL.labels(agent=agent).inc()
        return base
