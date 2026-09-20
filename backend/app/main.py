from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.api.v1 import (
    auth, users, customers, articles, contracts, invoices, payment_runs,
    settings as settings_router, creditors, incoming_invoices, expense_receipts, sepa, stb_export,
    query,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("startup.begin")

    # Gespeicherte Firmendaten aus der Datenbank auf das Settings-Objekt legen.
    # Muss vor dem Scheduler laufen: der Rechnungslauf liest settings.company_*.
    try:
        from app.database import AsyncSessionLocal
        from app.services.settings_store import load_into_settings
        async with AsyncSessionLocal() as session:
            count = await load_into_settings(session)
        logger.info("settings.loaded", count=count)
    except Exception as e:
        # Darf den Start nicht verhindern: ohne Datenbankwerte greifen
        # weiterhin die Umgebungsvariablen und die Defaults aus config.py.
        logger.error("settings.load_failed", error=str(e))

    try:
        from app.scheduler.setup import start_scheduler
        start_scheduler()
        logger.info("scheduler.started")
    except Exception as e:
        logger.error("scheduler.start_failed", error=str(e))

    yield

    # Shutdown
    logger.info("shutdown.begin")
    try:
        from app.scheduler.setup import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.error("scheduler.stop_failed", error=str(e))


app = FastAPI(
    title="DEMRE Billing API",
    description="Abrechnungssystem für Demme Immobilien Verwaltung GmbH",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://frontend:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
PREFIX = "/api/v1"
app.include_router(auth.router, prefix=PREFIX)
app.include_router(users.router, prefix=PREFIX)
app.include_router(customers.router, prefix=PREFIX)
app.include_router(articles.router, prefix=PREFIX)
app.include_router(contracts.router, prefix=PREFIX)
app.include_router(invoices.router, prefix=PREFIX)
app.include_router(payment_runs.router, prefix=PREFIX)
app.include_router(settings_router.router, prefix=PREFIX)
app.include_router(creditors.router, prefix=PREFIX)
app.include_router(incoming_invoices.router, prefix=PREFIX)
app.include_router(expense_receipts.router, prefix=PREFIX)
app.include_router(sepa.router, prefix=PREFIX)
app.include_router(stb_export.router, prefix=PREFIX)
app.include_router(query.router, prefix=PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "DEMRE Billing API", "docs": "/docs"}
