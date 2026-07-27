"""Operator feedback on an RCA -- and the case-based learning it feeds.

A "correct" verdict does more than get logged: the RCA and the evidence that
grounded it are pushed into knowledge-service as a new citable precedent, so
future investigations of a similar incident can retrieve and cite it via the
existing RAG path (see app/agents/investigators.py::runbook_investigator).
This is deliberately NOT model fine-tuning -- see docs/eval.md for why a
retrieval-based approach is the appropriate scale of "learning" for this
project's incident volume.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import utcnow
from app.models import FeedbackStatus, RCAReport
from app.services.orchestrator import get_investigation

logger = structlog.get_logger(__name__)


class NoRcaError(Exception):
    pass


def _build_learned_document(run, rca: RCAReport) -> dict[str, str | list[str]]:
    summary = (run.report or {}).get("incident_summary") or {}
    alertname = summary.get("alertname") or "UnknownAlert"
    service = summary.get("service") or "unknown-service"

    evidence_lines = "\n".join(
        f"- {e.evidence_id}: {e.summary}"
        for e in run.evidence_items
        if e.evidence_id in (rca.evidence_ids or [])
    )
    content = (
        f"# Learned incident: {alertname} ({service})\n\n"
        f"## Root cause (operator-verified)\n{rca.root_cause}\n\n"
        f"## Business impact\n{rca.business_impact or 'n/a'}\n\n"
        f"## Evidence that grounded this diagnosis\n{evidence_lines or 'n/a'}\n\n"
        f"## Steps taken\n"
        + "\n".join(f"- {s}" for s in (rca.next_steps or [])) + "\n\n"
        f"## Confidence at time of investigation\n{rca.confidence}\n\n"
        f"## Operator notes\n{rca.feedback_notes or 'n/a'}\n"
    )
    return {
        "title": f"Learned: {alertname} -- {rca.root_cause}"[:256],
        "content": content,
        "tags": ["learned-incident", alertname, service],
    }


async def submit_feedback(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    *,
    status: FeedbackStatus,
    notes: str | None,
    reviewed_by: str | None,
) -> RCAReport:
    run = await get_investigation(db, investigation_id)
    if run.rca_report is None:
        raise NoRcaError(f"Investigation {investigation_id} has no RCA to give feedback on")

    rca = run.rca_report
    rca.feedback_status = status
    rca.feedback_notes = notes
    rca.feedback_by = reviewed_by
    rca.feedback_at = utcnow()

    if status == FeedbackStatus.CORRECT and rca.learned_doc_id is None:
        settings = get_settings()
        doc = _build_learned_document(run, rca)
        try:
            from app.services.resilient_http import get_json_post

            resp = await get_json_post(
                f"{settings.knowledge_service_url.rstrip('/')}/documents",
                json_body=doc,
                name="knowledge-learn",
            )
            rca.learned_doc_id = resp.get("id") or resp.get("doc_id")
            logger.info(
                "rca_learned",
                investigation_id=str(investigation_id),
                doc_id=rca.learned_doc_id,
            )
        except Exception as exc:  # noqa: BLE001
            # Feedback itself must still be recorded even if the knowledge
            # service is temporarily unreachable -- learning is best-effort,
            # the operator's verdict is not.
            logger.warning(
                "rca_learn_failed",
                investigation_id=str(investigation_id),
                error=str(exc),
            )

    await db.commit()
    await db.refresh(rca)
    return rca
