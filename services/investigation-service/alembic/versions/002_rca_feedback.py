"""RCA operator feedback + knowledge-base learning link.

Revision ID: 002_rca_feedback
Revises: 001_investigation
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_rca_feedback"
down_revision: Union[str, None] = "001_investigation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "rca_reports",
        sa.Column(
            "feedback_status",
            sa.String(length=16),
            nullable=False,
            server_default="unreviewed",
        ),
    )
    op.add_column("rca_reports", sa.Column("feedback_notes", sa.Text(), nullable=True))
    op.add_column("rca_reports", sa.Column("feedback_by", sa.String(length=128), nullable=True))
    op.add_column(
        "rca_reports", sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "rca_reports", sa.Column("learned_doc_id", sa.String(length=64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("rca_reports", "learned_doc_id")
    op.drop_column("rca_reports", "feedback_at")
    op.drop_column("rca_reports", "feedback_by")
    op.drop_column("rca_reports", "feedback_notes")
    op.drop_column("rca_reports", "feedback_status")
