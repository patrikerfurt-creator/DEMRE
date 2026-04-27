"""Add additional_text to invoice_items

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-27 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoice_items",
        sa.Column("additional_text", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoice_items", "additional_text")
