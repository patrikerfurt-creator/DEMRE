"""Add iban and bic to users

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-16 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("iban", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("bic", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "bic")
    op.drop_column("users", "iban")
