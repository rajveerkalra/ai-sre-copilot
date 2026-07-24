"""Initial incident engine schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-07-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("alertname", sa.String(length=256), nullable=True),
        sa.Column("service", sa.String(length=256), nullable=True),
        sa.Column("namespace", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
    )
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_fingerprint", "incidents", ["fingerprint"])
    op.create_index(
        "ix_incidents_status_severity", "incidents", ["status", "severity"]
    )
    op.create_index(
        "ux_incidents_open_fingerprint",
        "incidents",
        ["fingerprint"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
        sqlite_where=sa.text("status = 'open'"),
    )

    op.create_table(
        "timeline_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_timeline_events_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_timeline_events")),
    )
    op.create_index(
        "ix_timeline_events_incident_id", "timeline_events", ["incident_id"]
    )
    op.create_index(
        "ix_timeline_events_event_type", "timeline_events", ["event_type"]
    )

    op.create_table(
        "alert_payloads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_alert_payloads_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_payloads")),
    )
    op.create_index(
        "ix_alert_payloads_incident_id", "alert_payloads", ["incident_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_alert_payloads_incident_id", table_name="alert_payloads")
    op.drop_table("alert_payloads")
    op.drop_index("ix_timeline_events_event_type", table_name="timeline_events")
    op.drop_index("ix_timeline_events_incident_id", table_name="timeline_events")
    op.drop_table("timeline_events")
    op.drop_index("ux_incidents_open_fingerprint", table_name="incidents")
    op.drop_index("ix_incidents_status_severity", table_name="incidents")
    op.drop_index("ix_incidents_fingerprint", table_name="incidents")
    op.drop_index("ix_incidents_severity", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_table("incidents")
