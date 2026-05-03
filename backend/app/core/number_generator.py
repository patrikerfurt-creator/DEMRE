from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.config import settings


async def generate_creditor_number(db: AsyncSession) -> str:
    """Generate a sequential creditor number starting at 100001. Format: KR100001"""
    await db.execute(
        text("CREATE SEQUENCE IF NOT EXISTS creditor_number_seq START 100001")
    )
    result = await db.execute(text("SELECT nextval('creditor_number_seq')"))
    return f"KR{result.scalar()}"


async def generate_document_number(db: AsyncSession, prefix: str) -> str:
    """
    Generate a document number for incoming invoices (ER) or expense receipts (BL).
    Format: ER-YYYY-NNNNNN / BL-YYYY-NNNNNN
    """
    year = date.today().year
    seq_map = {"ER": "incoming_invoice_number_seq", "BL": "expense_receipt_number_seq"}
    seq_name = seq_map.get(prefix, f"{prefix.lower()}_number_seq")
    await db.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1"))
    result = await db.execute(text(f"SELECT nextval('{seq_name}')"))
    return f"{prefix}-{year}-{result.scalar():06d}"


async def generate_contract_number(db: AsyncSession) -> str:
    """Generate a sequential contract number. Format: ABO-NNNNNN"""
    await db.execute(
        text("CREATE SEQUENCE IF NOT EXISTS contract_number_seq START 1")
    )
    result = await db.execute(text("SELECT nextval('contract_number_seq')"))
    return f"ABO-{result.scalar():06d}"


async def generate_customer_number(db: AsyncSession) -> str:
    """Generate a sequential 5-digit customer number starting at 10001."""
    await db.execute(
        text("CREATE SEQUENCE IF NOT EXISTS customer_number_seq START 10001")
    )
    # Ensure sequence is not behind any manually set customer number
    await db.execute(text("""
        SELECT setval(
            'customer_number_seq',
            GREATEST(
                (SELECT last_value FROM customer_number_seq),
                COALESCE(
                    (SELECT MAX(customer_number::bigint) FROM customers
                     WHERE customer_number ~ '^[0-9]+$'),
                    9999
                )
            )
        )
    """))
    result = await db.execute(text("SELECT nextval('customer_number_seq')"))
    return str(result.scalar())


async def generate_invoice_number(db: AsyncSession) -> str:
    """
    Generate a gapless invoice number using a PostgreSQL sequence.
    Format: YYYY-NNNN (z. B. 2026-0311).
    Resets every year. 2026 starts at 311 to continue existing numbering.
    """
    year = date.today().year
    start = 311 if year == 2026 else 1
    seq_name = f"invoice_num_{year}"

    await db.execute(
        text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START {start}")
    )
    result = await db.execute(text(f"SELECT nextval('{seq_name}')"))
    return f"{year}-{result.scalar():04d}"
