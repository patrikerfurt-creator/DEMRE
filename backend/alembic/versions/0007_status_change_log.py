"""Add status_change_log table

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-20 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "status_change_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(50), nullable=False),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column(
            "changed_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_status_change_log_entity",
        "status_change_log",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_status_change_log_entity", table_name="status_change_log")
    op.drop_table("status_change_log")
