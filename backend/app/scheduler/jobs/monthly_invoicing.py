"""
Monthly invoicing job.
Runs on the 1st of each month at 02:00 Europe/Berlin.
"""
import asyncio
from datetime import date, datetime, timezone
from calendar import monthrange
import structlog

logger = structlog.get_logger()


async def run_monthly_invoicing():
    """Main monthly invoicing coroutine."""
    from app.database import AsyncSessionLocal
    from app.models.payment_run import PaymentRun, RunType, RunStatus
    from app.services.invoice_service import InvoiceService
    from app.services.zugferd_service import ZugferdService
    from app.models.invoice import Invoice
    from app.models.customer import Customer
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    import os
    from app.config import settings

    today = date.today()
    # Bill for current month
    period_from = date(today.year, today.month, 1)
    period_to = date(today.year, today.month, monthrange(today.year, today.month)[1])

    logger.info("monthly_invoicing.start", period_from=str(period_from), period_to=str(period_to))

    async with AsyncSessionLocal() as db:
        run = PaymentRun(
            run_type=RunType.invoice_generation,
            status=RunStatus.running,
            period_from=period_from,
            period_to=period_to,
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        try:
            service = InvoiceService(db)
            invoice_ids = await service.generate_invoices_for_period(
                period_from=period_from,
                period_to=period_to,
                auto_issue=True,
                generation_run_id=run.id,
            )

            # Generate PDFs
            zugferd_service = ZugferdService()
            pdf_dir = os.path.join(settings.storage_path, "invoices")
            os.makedirs(pdf_dir, exist_ok=True)

            for invoice_id in invoice_ids:
                try:
                    inv_result = await db.execute(
                        select(Invoice)
                        .options(selectinload(Invoice.items))
                        .where(Invoice.id == invoice_id)
                    )
                    invoice = inv_result.scalar_one_or_none()
                    if not invoice:
                        continue

                    cust_result = await db.execute(
                        select(Customer).where(Customer.id == invoice.customer_id)
                    )
                    invoice.customer = cust_result.scalar_one_or_none()

                    pdf_bytes = zugferd_service.generate_pdf(invoice)
                    pdf_path = os.path.join(pdf_dir, f"{invoice.invoice_number}.pdf")
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_bytes)
                    invoice.pdf_path = pdf_path

                    xml_bytes = zugferd_service.build_xml(invoice)
                    invoice.zugferd_xml = xml_bytes.decode("utf-8")

                except Exception as e:
                    logger.error("monthly_invoicing.pdf_error", invoice_id=str(invoice_id), error=str(e))

            # Compute totals
            inv_result = await db.execute(
                select(Invoice).where(Invoice.id.in_(invoice_ids))
            )
            invoices = inv_result.scalars().all()
            total_amount = sum(inv.total_gross for inv in invoices)

            run.status = RunStatus.completed
            run.invoice_count = len(invoice_ids)
            run.total_amount = total_amount
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                "monthly_invoicing.complete",
                invoice_count=len(invoice_ids),
                total_amount=str(total_amount),
            )

        except Exception as e:
            logger.error("monthly_invoicing.error", error=str(e))
            run.status = RunStatus.failed
            run.error_message = str(e)
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()


def schedule_monthly_job(scheduler):
    """Register the monthly invoicing job with the scheduler."""
    # Check if job already registered
    existing = scheduler.get_job("monthly_invoicing")
    if existing:
        return

    scheduler.add_job(
        run_monthly_invoicing,
        trigger="cron",
        id="monthly_invoicing",
        name="Monatliche Rechnungsstellung",
        day=1,
        hour=2,
        minute=0,
        timezone="Europe/Berlin",
        replace_existing=True,
    )
    logger.info("monthly_invoicing.scheduled")
