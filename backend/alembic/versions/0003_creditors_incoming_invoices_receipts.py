"""Creditors, incoming invoices and expense receipts

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-08 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sequences
    op.execute("CREATE SEQUENCE IF NOT EXISTS creditor_number_seq START 100001")
    op.execute("CREATE SEQUENCE IF NOT EXISTS incoming_invoice_number_seq START 1")
    op.execute("CREATE SEQUENCE IF NOT EXISTS expense_receipt_number_seq START 1")

    # New enums
    for stmt in [
        "CREATE TYPE incominginvoicestatus AS ENUM ('open','approved','scheduled','paid','rejected','cancelled')",
        "CREATE TYPE expensereceiptstatus AS ENUM ('submitted','approved','paid','rejected')",
    ]:
        op.execute(f"DO $$ BEGIN {stmt}; EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    # Extend runtype enum with creditor_payment
    op.execute(
        "DO $$ BEGIN ALTER TYPE runtype ADD VALUE IF NOT EXISTS 'creditor_payment'; "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    # creditors
    op.create_table(
        "creditors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("creditor_number", sa.String(50), nullable=False, unique=True),
        sa.Column("company_name", sa.String(255)),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("address_line1", sa.String(255)),
        sa.Column("address_line2", sa.String(255)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("city", sa.String(100)),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="DE"),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("iban", sa.String(34)),
        sa.Column("bic", sa.String(11)),
        sa.Column("bank_name", sa.String(255)),
        sa.Column("account_holder", sa.String(255)),
        sa.Column("vat_id", sa.String(50)),
        sa.Column("tax_number", sa.String(50)),
        sa.Column("datev_account_number", sa.String(20)),
        sa.Column("payment_terms_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("notes", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_creditors_creditor_number", "creditors", ["creditor_number"])

    # incoming_invoices
    op.create_table(
        "incoming_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_number", sa.String(50), nullable=False, unique=True),
        sa.Column("external_invoice_number", sa.String(100)),
        sa.Column("creditor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("creditors.id"), nullable=False),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("receipt_date", sa.Date),
        sa.Column("due_date", sa.Date),
        sa.Column("total_net", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("total_vat", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("total_gross", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("description", sa.Text),
        sa.Column("cost_account", sa.String(20)),
        sa.Column("status",
                  postgresql.ENUM("open", "approved", "scheduled", "paid", "rejected", "cancelled",
                                  name="incominginvoicestatus", create_type=False),
                  nullable=False, server_default="open"),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("document_path", sa.String(500)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_incoming_invoices_document_number", "incoming_invoices", ["document_number"])
    op.create_index("ix_incoming_invoices_creditor_id", "incoming_invoices", ["creditor_id"])
    op.create_index("ix_incoming_invoices_status", "incoming_invoices", ["status"])

    # expense_receipts
    op.create_table(
        "expense_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("receipt_number", sa.String(50), nullable=False, unique=True),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("receipt_date", sa.Date, nullable=False),
        sa.Column("merchant", sa.String(255)),
        sa.Column("amount_gross", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("vat_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("amount_net", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="19.00"),
        sa.Column("category", sa.String(100)),
        sa.Column("description", sa.Text),
        sa.Column("payment_method", sa.String(50)),
        sa.Column("reimbursement_iban", sa.String(34)),
        sa.Column("reimbursement_account_holder", sa.String(255)),
        sa.Column("status",
                  postgresql.ENUM("submitted", "approved", "paid", "rejected",
                                  name="expensereceiptstatus", create_type=False),
                  nullable=False, server_default="submitted"),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("document_path", sa.String(500)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_expense_receipts_receipt_number", "expense_receipts", ["receipt_number"])
    op.create_index("ix_expense_receipts_submitted_by", "expense_receipts", ["submitted_by"])
    op.create_index("ix_expense_receipts_status", "expense_receipts", ["status"])

    # updated_at triggers for new tables
    for table in ["creditors", "incoming_invoices", "expense_receipts"]:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    op.drop_table("expense_receipts")
    op.drop_table("incoming_invoices")
    op.drop_table("creditors")

    op.execute("DROP SEQUENCE IF EXISTS expense_receipt_number_seq")
    op.execute("DROP SEQUENCE IF EXISTS incoming_invoice_number_seq")
    op.execute("DROP SEQUENCE IF EXISTS creditor_number_seq")

    op.execute("DROP TYPE IF EXISTS expensereceiptstatus")
    op.execute("DROP TYPE IF EXISTS incominginvoicestatus")
