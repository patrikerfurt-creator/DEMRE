"""Add credit notes (document_type discriminator on invoices)

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


document_type_enum = sa.Enum("invoice", "credit_note", name="documenttype")


def upgrade() -> None:
    document_type_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "invoices",
        sa.Column(
            "document_type",
            document_type_enum,
            nullable=False,
            server_default="invoice",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column("credit_note_of_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column("invoices", sa.Column("credit_reason", sa.Text, nullable=True))

    op.create_foreign_key(
        "fk_invoices_credit_note_of_id",
        "invoices",
        "invoices",
        ["credit_note_of_id"],
        ["id"],
    )
    op.create_index(
        "ix_invoices_credit_note_of_id", "invoices", ["credit_note_of_id"]
    )
    op.create_index("ix_invoices_document_type", "invoices", ["document_type"])


def downgrade() -> None:
    op.drop_index("ix_invoices_document_type", table_name="invoices")
    op.drop_index("ix_invoices_credit_note_of_id", table_name="invoices")
    op.drop_constraint("fk_invoices_credit_note_of_id", "invoices", type_="foreignkey")
    op.drop_column("invoices", "credit_reason")
    op.drop_column("invoices", "credit_note_of_id")
    op.drop_column("invoices", "document_type")
    document_type_enum.drop(op.get_bind(), checkfirst=True)
