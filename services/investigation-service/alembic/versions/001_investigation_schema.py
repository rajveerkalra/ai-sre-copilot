"""Investigation engine tables.

Revision ID: 001_investigation
Revises:
Create Date: 2026-07-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_investigation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investigation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("used_fallback", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "context_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investigation_runs")),
    )
    op.create_index(
        "ix_investigation_runs_incident_id", "investigation_runs", ["incident_id"]
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigation_runs.id"],
            name=op.f("fk_evidence_investigation_id_investigation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
    )
    op.create_index("ix_evidence_investigation_id", "evidence", ["investigation_id"])
    op.create_index("ix_evidence_evidence_id", "evidence", ["evidence_id"])

    op.create_table(
        "agent_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("used_llm", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigation_runs.id"],
            name=op.f("fk_agent_results_investigation_id_investigation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_results")),
    )
    op.create_index(
        "ix_agent_results_investigation_id", "agent_results", ["investigation_id"]
    )

    op.create_table(
        "rca_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("business_impact", sa.Text(), nullable=False),
        sa.Column("next_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("unknowns", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "supporting_runbooks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("used_fallback", sa.Boolean(), nullable=False),
        sa.Column(
            "full_report", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigation_runs.id"],
            name=op.f("fk_rca_reports_investigation_id_investigation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rca_reports")),
        sa.UniqueConstraint("investigation_id", name=op.f("uq_rca_reports_investigation_id")),
    )


def downgrade() -> None:
    op.drop_table("rca_reports")
    op.drop_index("ix_agent_results_investigation_id", table_name="agent_results")
    op.drop_table("agent_results")
    op.drop_index("ix_evidence_evidence_id", table_name="evidence")
    op.drop_index("ix_evidence_investigation_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_investigation_runs_incident_id", table_name="investigation_runs")
    op.drop_table("investigation_runs")
