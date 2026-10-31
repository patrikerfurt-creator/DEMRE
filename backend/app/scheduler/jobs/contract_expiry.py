"""
Contract expiry job.

Runs daily at 02:30 Europe/Berlin and sets every still-active contract whose
end_date has been reached to status 'terminated'. This keeps the visible
contract status in sync with reality — a contract with a past end_date must no
longer appear as "Aktiv".

Note on billing safety: invoice generation already filters on
``end_date >= period_from`` (see InvoiceService.generate_invoices_for_period),
so an expired contract never produces new invoices regardless of this job. The
daily run at 02:30 is intentionally *after* the monthly invoicing run (1st,
02:00), so the final period is still billed before the contract is terminated.
"""
from datetime import date
import structlog

logger = structlog.get_logger()


async def terminate_expired_contracts(db, today: date | None = None) -> int:
    """Set active contracts whose end_date has been reached to 'terminated'.

    A contract is considered expired once ``end_date <= today`` (the end date is
    the last day the contract is in effect). Returns the number of contracts
    that were terminated.
    """
    from sqlalchemy import select
    from app.models.contract import Contract, ContractStatus

    today = today or date.today()
    result = await db.execute(
        select(Contract).where(
            Contract.status == ContractStatus.active,
            Contract.end_date.is_not(None),
            Contract.end_date <= today,
        )
    )
    contracts = result.scalars().all()
    for contract in contracts:
        contract.status = ContractStatus.terminated
    if contracts:
        await db.commit()
        logger.info(
            "contract_expiry.terminated",
            count=len(contracts),
            contract_numbers=[c.contract_number for c in contracts],
        )
    return len(contracts)


async def run_contract_expiry():
    """Scheduler entry point: terminate all expired contracts."""
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        count = await terminate_expired_contracts(db)
    logger.info("contract_expiry.done", terminated=count)


def schedule_contract_expiry(scheduler):
    """Register the daily contract-expiry job with the scheduler."""
    existing = scheduler.get_job("contract_expiry")
    if existing:
        return

    scheduler.add_job(
        run_contract_expiry,
        trigger="cron",
        id="contract_expiry",
        name="Abgelaufene Vertraege kuendigen",
        hour=2,
        minute=30,
        timezone="Europe/Berlin",
        replace_existing=True,
    )
    logger.info("contract_expiry.scheduled")
