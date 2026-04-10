"""Add customer_type field

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: str = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("customer_type", sa.String(20), nullable=False, server_default="weg"),
    )


def downgrade() -> None:
    op.drop_column("customers", "customer_type")
