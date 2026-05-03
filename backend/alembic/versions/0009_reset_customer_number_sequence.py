"""Reset customer number sequence to 5-digit start (10001)

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-03 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS customer_number_seq")
    op.execute("CREATE SEQUENCE customer_number_seq START 10001")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS customer_number_seq")
    op.execute("CREATE SEQUENCE customer_number_seq START 100001")
