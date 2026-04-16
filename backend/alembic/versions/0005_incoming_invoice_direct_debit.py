"""Add is_direct_debit to incoming_invoices

Revision ID: 0005
Revises: 0003
Create Date: 2026-04-15 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Spalte mit IF NOT EXISTS — idempotent, falls bereits durch 0004 angelegt
    op.execute(
        "ALTER TABLE incoming_invoices "
        "ADD COLUMN IF NOT EXISTS is_direct_debit BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.drop_column("incoming_invoices", "is_direct_debit")
