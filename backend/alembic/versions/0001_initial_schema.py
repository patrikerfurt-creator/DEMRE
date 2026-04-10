"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Invoice number sequences
    op.execute("CREATE SEQUENCE IF NOT EXISTS invoice_number_seq START 1")

    # Enums (idempotent via exception handler)
    for stmt in [
        "CREATE TYPE userrole AS ENUM ('admin', 'user', 'readonly')",
        "CREATE TYPE contractstatus AS ENUM ('active', 'terminated', 'suspended')",
        "CREATE TYPE billingperiod AS ENUM ('monthly', 'quarterly', 'annual', 'one-time')",
        "CREATE TYPE invoicestatus AS ENUM ('draft', 'issued', 'sent', 'paid', 'overdue', 'cancelled')",
        "CREATE TYPE runtype AS ENUM ('invoice_generation', 'sepa_export', 'datev_export')",
        "CREATE TYPE runstatus AS ENUM ('pending', 'running', 'completed', 'failed')",
    ]:
        op.execute(f"DO $$ BEGIN {stmt}; EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", postgresql.ENUM("admin", "user", "readonly", name="userrole", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # customers
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_number", sa.String(50), nullable=False, unique=True),
        sa.Column("company_name", sa.String(255)),
        sa.Column("salutation", sa.String(50)),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("address_line1", sa.String(255)),
        sa.Column("address_line2", sa.String(255)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("city", sa.String(100)),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="DE"),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("vat_id", sa.String(50)),
        sa.Column("tax_number", sa.String(50)),
        sa.Column("iban", sa.String(34)),
        sa.Column("bic", sa.String(11)),
        sa.Column("bank_name", sa.String(255)),
        sa.Column("account_holder", sa.String(255)),
        sa.Column("sepa_mandate_ref", sa.String(100)),
        sa.Column("sepa_mandate_date", sa.String(20)),
        sa.Column("datev_account_number", sa.String(20)),
        sa.Column("notes", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_customers_customer_number", "customers", ["customer_number"])

    # articles
    op.create_table(
        "articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_number", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("unit", sa.String(50)),
        sa.Column("unit_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="19.00"),
        sa.Column("category", sa.String(100)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_articles_article_number", "articles", ["article_number"])

    # contracts
    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contract_number", sa.String(50), nullable=False, unique=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("property_ref", sa.String(255)),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("billing_day", sa.Integer, nullable=False, server_default="1"),
        sa.Column("payment_terms_days", sa.Integer, nullable=False, server_default="14"),
        sa.Column("notes", sa.Text),
        sa.Column("status", postgresql.ENUM("active", "terminated", "suspended", name="contractstatus", create_type=False),
                  nullable=False, server_default="active"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_contracts_contract_number", "contracts", ["contract_number"])
    op.create_index("ix_contracts_customer_id", "contracts", ["customer_id"])

    # contract_items
    op.create_table(
        "contract_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("articles.id"), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False, server_default="1.000"),
        sa.Column("override_price", sa.Numeric(12, 4)),
        sa.Column("override_vat_rate", sa.Numeric(5, 2)),
        sa.Column("description_override", sa.String(500)),
        sa.Column("billing_period",
                  postgresql.ENUM("monthly", "quarterly", "annual", "one-time", name="billingperiod", create_type=False),
                  nullable=False, server_default="monthly"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("valid_from", sa.Date),
        sa.Column("valid_until", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_contract_items_contract_id", "contract_items", ["contract_id"])

    # invoices
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_number", sa.String(50), nullable=False, unique=True),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("contracts.id"), nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("billing_period_from", sa.Date),
        sa.Column("billing_period_to", sa.Date),
        sa.Column("status",
                  postgresql.ENUM("draft", "issued", "sent", "paid", "overdue", "cancelled", name="invoicestatus", create_type=False),
                  nullable=False, server_default="draft"),
        sa.Column("subtotal_net", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("total_vat", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("total_gross", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("notes", sa.Text),
        sa.Column("internal_notes", sa.Text),
        sa.Column("pdf_path", sa.String(500)),
        sa.Column("zugferd_xml", sa.Text),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("generation_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])

    # invoice_items
    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("articles.id"), nullable=True),
        sa.Column("position", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit", sa.String(50)),
        sa.Column("unit_price_net", sa.Numeric(12, 4), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("total_net", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_vat", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_gross", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])

    # payment_runs
    op.create_table(
        "payment_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_type",
                  postgresql.ENUM("invoice_generation", "sepa_export", "datev_export", name="runtype", create_type=False),
                  nullable=False),
        sa.Column("status",
                  postgresql.ENUM("pending", "running", "completed", "failed", name="runstatus", create_type=False),
                  nullable=False, server_default="pending"),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True)),
        sa.Column("period_from", sa.Date),
        sa.Column("period_to", sa.Date),
        sa.Column("invoice_count", sa.Integer),
        sa.Column("total_amount", sa.Numeric(14, 2)),
        sa.Column("file_path", sa.String(500)),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create APScheduler tables
    op.execute("""
        CREATE TABLE IF NOT EXISTS apscheduler_jobs (
            id VARCHAR(191) NOT NULL,
            next_run_time DOUBLE PRECISION,
            job_state BYTEA NOT NULL,
            PRIMARY KEY (id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_apscheduler_jobs_next_run_time ON apscheduler_jobs (next_run_time)")

    # Create updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    for table in ["users", "customers", "articles", "contracts", "contract_items", "invoices"]:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    op.drop_table("payment_runs")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("contract_items")
    op.drop_table("contracts")
    op.drop_table("articles")
    op.drop_table("customers")
    op.drop_table("users")
    op.drop_table("apscheduler_jobs")

    op.execute("DROP SEQUENCE IF EXISTS invoice_number_seq")
    op.execute("DROP TYPE IF EXISTS runstatus")
    op.execute("DROP TYPE IF EXISTS runtype")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    op.execute("DROP TYPE IF EXISTS invoicestatus")
    op.execute("DROP TYPE IF EXISTS billingperiod")
    op.execute("DROP TYPE IF EXISTS contractstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
