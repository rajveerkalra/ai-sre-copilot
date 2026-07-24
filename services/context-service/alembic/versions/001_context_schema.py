"""Investigation context tables.

Revision ID: 001_context
Revises:
Create Date: 2026-07-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_context"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investigation_context",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("logs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("kubernetes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("deployment", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("system", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investigation_context")),
    )
    op.create_index(
        "ix_investigation_context_incident_id",
        "investigation_context",
        ["incident_id"],
    )
    op.create_index(
        "ix_investigation_context_status", "investigation_context", ["status"]
    )

    op.create_table(
        "collector_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investigation_context_id", sa.Uuid(), nullable=False),
        sa.Column("collector_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["investigation_context_id"],
            ["investigation_context.id"],
            name=op.f("fk_collector_runs_investigation_context_id_investigation_context"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collector_runs")),
    )
    op.create_index(
        "ix_collector_runs_context_id",
        "collector_runs",
        ["investigation_context_id"],
    )
    op.create_index(
        "ix_collector_runs_collector_name", "collector_runs", ["collector_name"]
    )

    op.create_table(
        "collector_errors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("collector_run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("error_type", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["collector_run_id"],
            ["collector_runs.id"],
            name=op.f("fk_collector_errors_collector_run_id_collector_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collector_errors")),
    )
    op.create_index(
        "ix_collector_errors_run_id", "collector_errors", ["collector_run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_collector_errors_run_id", table_name="collector_errors")
    op.drop_table("collector_errors")
    op.drop_index("ix_collector_runs_collector_name", table_name="collector_runs")
    op.drop_index("ix_collector_runs_context_id", table_name="collector_runs")
    op.drop_table("collector_runs")
    op.drop_index("ix_investigation_context_status", table_name="investigation_context")
    op.drop_index(
        "ix_investigation_context_incident_id", table_name="investigation_context"
    )
    op.drop_table("investigation_context")
