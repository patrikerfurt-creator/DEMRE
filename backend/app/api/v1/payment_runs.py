from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import os
import uuid

from app.api.deps import get_db, get_current_user, require_not_readonly
from app.models.user import User
from app.models.payment_run import PaymentRun, RunType, RunStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.schemas.payment_run import PaymentRunResponse, SepaExportRequest, DatevExportRequest
from app.services.sepa_service import SepaService
from app.services.datev_service import DatevService

router = APIRouter(prefix="/payment-runs", tags=["payment-runs"])


@router.get("", response_model=List[PaymentRunResponse])
async def list_payment_runs(
    run_type: Optional[RunType] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(PaymentRun)
    if run_type:
        query = query.where(PaymentRun.run_type == run_type)
    query = query.order_by(PaymentRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return [PaymentRunResponse.model_validate(r) for r in result.scalars().all()]


@router.get("/{run_id}", response_model=PaymentRunResponse)
async def get_payment_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(PaymentRun).where(PaymentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Export-Lauf nicht gefunden")
    return PaymentRunResponse.model_validate(run)


@router.post("/sepa", response_model=PaymentRunResponse)
async def create_sepa_export(
    data: SepaExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    # Load invoices
    result = await db.execute(
        select(Invoice).where(Invoice.id.in_(data.invoice_ids))
    )
    invoices = result.scalars().all()

    if not invoices:
        raise HTTPException(status_code=400, detail="Keine Rechnungen gefunden")

    run = PaymentRun(
        run_type=RunType.sepa_export,
        status=RunStatus.running,
        triggered_by=current_user.id,
        started_at=datetime.now(timezone.utc),
        invoice_count=len(invoices),
        total_amount=sum(inv.total_gross for inv in invoices),
    )
    db.add(run)
    await db.flush()

    try:
        # Load customers for invoices
        from app.models.customer import Customer
        customer_ids = list(set(str(inv.customer_id) for inv in invoices))
        cust_result = await db.execute(
            select(Customer).where(Customer.id.in_(customer_ids))
        )
        customers = {str(c.id): c for c in cust_result.scalars().all()}
        for inv in invoices:
            inv.customer = customers.get(str(inv.customer_id))

        service = SepaService()
        xml_bytes = service.generate_pain001(invoices, execution_date=data.execution_date)

        from app.config import settings
        export_dir = os.path.join(settings.storage_path, "exports", "sepa")
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, f"sepa_{run.id}.xml")

        with open(file_path, "wb") as f:
            f.write(xml_bytes)

        run.file_path = file_path
        run.status = RunStatus.completed
        run.completed_at = datetime.now(timezone.utc)
    except Exception as e:
        run.status = RunStatus.failed
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(run)
    return PaymentRunResponse.model_validate(run)


@router.post("/datev", response_model=PaymentRunResponse)
async def create_datev_export(
    data: DatevExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    query = select(Invoice)
    if data.invoice_ids:
        query = query.where(Invoice.id.in_(data.invoice_ids))
    else:
        query = query.where(
            Invoice.invoice_date >= data.period_from,
            Invoice.invoice_date <= data.period_to,
            Invoice.status.in_([InvoiceStatus.issued, InvoiceStatus.sent, InvoiceStatus.paid]),
        )

    result = await db.execute(query)
    invoices = result.scalars().all()

    run = PaymentRun(
        run_type=RunType.datev_export,
        status=RunStatus.running,
        triggered_by=current_user.id,
        period_from=data.period_from,
        period_to=data.period_to,
        started_at=datetime.now(timezone.utc),
        invoice_count=len(invoices),
        total_amount=sum(inv.total_gross for inv in invoices) if invoices else 0,
    )
    db.add(run)
    await db.flush()

    try:
        from app.models.customer import Customer
        from sqlalchemy.orm import selectinload
        invoice_ids = [inv.id for inv in invoices]
        inv_result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.items))
            .where(Invoice.id.in_(invoice_ids))
        )
        invoices_with_items = inv_result.scalars().all()

        customer_ids = list(set(str(inv.customer_id) for inv in invoices_with_items))
        cust_result = await db.execute(
            select(Customer).where(Customer.id.in_(customer_ids))
        )
        customers = {str(c.id): c for c in cust_result.scalars().all()}
        for inv in invoices_with_items:
            inv.customer = customers.get(str(inv.customer_id))

        service = DatevService()
        csv_bytes = service.generate_datev_export(
            invoices_with_items,
            period_from=data.period_from,
            period_to=data.period_to,
        )

        from app.config import settings
        export_dir = os.path.join(settings.storage_path, "exports", "datev")
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, f"datev_{run.id}.csv")

        with open(file_path, "wb") as f:
            f.write(csv_bytes)

        run.file_path = file_path
        run.status = RunStatus.completed
        run.completed_at = datetime.now(timezone.utc)
    except Exception as e:
        run.status = RunStatus.failed
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(run)
    return PaymentRunResponse.model_validate(run)


@router.get("/{run_id}/download")
async def download_payment_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(PaymentRun).where(PaymentRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Export-Lauf nicht gefunden")
    if not run.file_path or not os.path.exists(run.file_path):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    ext = os.path.splitext(run.file_path)[1]
    media_type = "application/xml" if ext == ".xml" else "text/csv"
    filename = f"export_{run_id}{ext}"

    return FileResponse(run.file_path, media_type=media_type, filename=filename)
