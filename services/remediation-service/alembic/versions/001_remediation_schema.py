"""Remediation tables.

Revision ID: 001_remediation
Revises:
Create Date: 2026-07-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_remediation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "remediation_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("investigation_id", sa.Uuid(), nullable=True),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("requires_dry_run_default", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_remediation_proposals")),
    )
    op.create_index(
        "ix_remediation_proposals_incident_id", "remediation_proposals", ["incident_id"]
    )
    op.create_index(
        "ix_remediation_proposals_status", "remediation_proposals", ["status"]
    )

    op.create_table(
        "remediation_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["remediation_proposals.id"],
            name=op.f("fk_remediation_approvals_proposal_id_remediation_proposals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_remediation_approvals")),
    )
    op.create_index(
        "ix_remediation_approvals_proposal_id", "remediation_approvals", ["proposal_id"]
    )

    op.create_table(
        "remediation_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["remediation_proposals.id"],
            name=op.f("fk_remediation_executions_proposal_id_remediation_proposals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_remediation_executions")),
    )
    op.create_index(
        "ix_remediation_executions_proposal_id",
        "remediation_executions",
        ["proposal_id"],
    )

    op.create_table(
        "remediation_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("incident_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_remediation_audit_logs")),
    )
    op.create_index(
        "ix_remediation_audit_logs_proposal_id",
        "remediation_audit_logs",
        ["proposal_id"],
    )
    op.create_index(
        "ix_remediation_audit_logs_incident_id",
        "remediation_audit_logs",
        ["incident_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_remediation_audit_logs_incident_id", table_name="remediation_audit_logs"
    )
    op.drop_index(
        "ix_remediation_audit_logs_proposal_id", table_name="remediation_audit_logs"
    )
    op.drop_table("remediation_audit_logs")
    op.drop_index(
        "ix_remediation_executions_proposal_id", table_name="remediation_executions"
    )
    op.drop_table("remediation_executions")
    op.drop_index(
        "ix_remediation_approvals_proposal_id", table_name="remediation_approvals"
    )
    op.drop_table("remediation_approvals")
    op.drop_index("ix_remediation_proposals_status", table_name="remediation_proposals")
    op.drop_index(
        "ix_remediation_proposals_incident_id", table_name="remediation_proposals"
    )
    op.drop_table("remediation_proposals")
