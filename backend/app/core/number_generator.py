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
    """Generate a sequential 6-digit customer number starting at 100001."""
    await db.execute(
        text("CREATE SEQUENCE IF NOT EXISTS customer_number_seq START 100001")
    )
    result = await db.execute(text("SELECT nextval('customer_number_seq')"))
    return str(result.scalar())


async def generate_invoice_number(db: AsyncSession) -> str:
    """
    Generate a gapless invoice number using a PostgreSQL sequence.
    Format: RE-YYYY-NNNNNN
    """
    year = date.today().year

    if settings.invoice_number_year_reset:
        # Use a per-year sequence
        seq_name = f"invoice_number_seq_{year}"
        # Try to create the sequence if it doesn't exist
        await db.execute(
            text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1")
        )
        result = await db.execute(text(f"SELECT nextval('{seq_name}')"))
    else:
        result = await db.execute(text("SELECT nextval('invoice_number_seq')"))

    seq_val = result.scalar()
    prefix = settings.invoice_number_prefix
    return f"{prefix}-{year}-{seq_val:06d}"
