from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from app.config import settings

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        jobstores = {
            "default": SQLAlchemyJobStore(
                url=settings.database_url_sync
            )
        }
        executors = {
            "default": AsyncIOExecutor(),
        }
        job_defaults = {
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600,
        }
        _scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="Europe/Berlin",
        )
    return _scheduler


def start_scheduler():
    scheduler = get_scheduler()
    from app.scheduler.jobs.monthly_invoicing import schedule_monthly_job
    from app.scheduler.jobs.incoming_invoices_watcher import schedule_incoming_watcher
    from app.scheduler.jobs.expense_receipts_watcher import schedule_expense_receipts_watcher
    schedule_monthly_job(scheduler)
    schedule_incoming_watcher(scheduler)
    schedule_expense_receipts_watcher(scheduler)
    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
