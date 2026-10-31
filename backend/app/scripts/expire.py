"""One-off runner: terminate all contracts whose end_date has been reached.

Usage (inside the backend container):
    python -m app.scripts.expire

Runs the same logic as the daily contract-expiry scheduler job once, so already
expired contracts get their status set to 'terminated' immediately instead of
waiting for the next scheduled run.
"""
import asyncio

from app.scheduler.jobs.contract_expiry import run_contract_expiry


if __name__ == "__main__":
    asyncio.run(run_contract_expiry())
