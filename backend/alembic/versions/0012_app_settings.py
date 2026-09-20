"""Add app_settings table

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0012"
# Haengt bewusst an 0010 statt an 0011: Die Migration 0011 (invoice_attachments)
# ist noch nicht committet und existiert nur auf dem Entwicklungsrechner. Mit
# down_revision "0011" bricht Alembic in der Produktion mit KeyError ab.
# Wenn 0011 spaeter committet wird, muss sie auf 0012 umgehaengt werden.
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
