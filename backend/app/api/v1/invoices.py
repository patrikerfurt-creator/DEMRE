from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from datetime import date
import os

from app.api.deps import get_db, get_current_user, require_not_readonly
from app.models.user import User
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.customer import Customer
from app.schemas.invoice import (
    InvoiceCreate, InvoiceUpdate, InvoiceResponse,
    InvoiceGenerateRequest, InvoiceStatusUpdate, InvoiceItemCreate
)
from app.services.invoice_service import InvoiceService
from app.services.zugferd_service import ZugferdService
from app.core.number_generator import generate_invoice_number
from decimal import Decimal

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=List[InvoiceResponse])
async def list_invoices(
    customer_id: Optional[str] = Query(None),
    status: Optional[InvoiceStatus] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Invoice).options(selectinload(Invoice.items))

    if customer_id:
        query = query.where(Invoice.customer_id == customer_id)
    if status:
        query = query.where(Invoice.status == status)
    if date_from:
        query = query.where(Invoice.invoice_date >= date_from)
    if date_to:
        query = query.where(Invoice.invoice_date <= date_to)

    query = query.order_by(Invoice.invoice_date.desc(), Invoice.invoice_number.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return [InvoiceResponse.model_validate(inv) for inv in result.scalars().all()]


@router.post("", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    data: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    invoice_number = await generate_invoice_number(db)

    subtotal_net = sum(item.total_net for item in data.items)
    total_vat = sum(item.total_vat for item in data.items)
    total_gross = sum(item.total_gross for item in data.items)

    invoice_data = data.model_dump(exclude={"items"})
    invoice = Invoice(
        **invoice_data,
        invoice_number=invoice_number,
        subtotal_net=subtotal_net,
        total_vat=total_vat,
        total_gross=total_gross,
        generated_by=current_user.id,
    )
    db.add(invoice)
    await db.flush()

    for pos, item_data in enumerate(data.items, 1):
        item = InvoiceItem(
            invoice_id=invoice.id,
            position=pos,
            **item_data.model_dump(exclude={"position"}),
        )
        db.add(item)

    await db.flush()
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice.id)
    )
    invoice = result.scalar_one()
    return InvoiceResponse.model_validate(invoice)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    return InvoiceResponse.model_validate(invoice)


@router.put("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: str,
    data: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=400, detail="Nur Rechnungen im Entwurfsstatus können bearbeitet werden")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)

    await db.flush()
    await db.refresh(invoice)
    return InvoiceResponse.model_validate(invoice)


@router.post("/{invoice_id}/items", response_model=InvoiceResponse, status_code=201)
async def add_invoice_item(
    invoice_id: str,
    data: InvoiceItemCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=400, detail="Nur Rechnungen im Entwurfsstatus können bearbeitet werden")

    next_pos = max((i.position for i in invoice.items), default=0) + 1
    item = InvoiceItem(invoice_id=invoice.id, position=next_pos, **data.model_dump(exclude={"position"}))
    db.add(item)
    await db.flush()

    await _recalc_invoice_totals(invoice, db)
    result2 = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    return InvoiceResponse.model_validate(result2.scalar_one())


@router.put("/{invoice_id}/items/{item_id}", response_model=InvoiceResponse)
async def update_invoice_item(
    invoice_id: str,
    item_id: str,
    data: InvoiceItemCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=400, detail="Nur Rechnungen im Entwurfsstatus können bearbeitet werden")

    item_result = await db.execute(
        select(InvoiceItem).where(InvoiceItem.id == item_id, InvoiceItem.invoice_id == invoice_id)
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")

    for field, value in data.model_dump().items():
        setattr(item, field, value)
    await db.flush()

    await _recalc_invoice_totals(invoice, db)
    result2 = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    return InvoiceResponse.model_validate(result2.scalar_one())


@router.delete("/{invoice_id}/items/{item_id}", response_model=InvoiceResponse)
async def delete_invoice_item(
    invoice_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=400, detail="Nur Rechnungen im Entwurfsstatus können bearbeitet werden")

    item_result = await db.execute(
        select(InvoiceItem).where(InvoiceItem.id == item_id, InvoiceItem.invoice_id == invoice_id)
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")

    await db.delete(item)
    await db.flush()

    await _recalc_invoice_totals(invoice, db)
    result2 = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    return InvoiceResponse.model_validate(result2.scalar_one())


async def _recalc_invoice_totals(invoice: Invoice, db: AsyncSession):
    from decimal import Decimal
    items_result = await db.execute(
        select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)
    )
    items = items_result.scalars().all()
    invoice.subtotal_net = sum((i.total_net for i in items), Decimal("0.00"))
    invoice.total_vat = sum((i.total_vat for i in items), Decimal("0.00"))
    invoice.total_gross = sum((i.total_gross for i in items), Decimal("0.00"))
    await db.flush()


_ALLOWED_TRANSITIONS: dict[InvoiceStatus, set[InvoiceStatus]] = {
    InvoiceStatus.draft:     {InvoiceStatus.issued},
    InvoiceStatus.issued:    {InvoiceStatus.sent, InvoiceStatus.paid, InvoiceStatus.overdue, InvoiceStatus.cancelled},
    InvoiceStatus.sent:      {InvoiceStatus.paid, InvoiceStatus.overdue, InvoiceStatus.cancelled},
    InvoiceStatus.overdue:   {InvoiceStatus.paid, InvoiceStatus.cancelled},
    InvoiceStatus.paid:      set(),
    InvoiceStatus.cancelled: set(),
}


@router.put("/{invoice_id}/status", response_model=InvoiceResponse)
async def update_invoice_status(
    invoice_id: str,
    data: InvoiceStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    from datetime import datetime, timezone
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    if data.status not in _ALLOWED_TRANSITIONS.get(invoice.status, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Statuswechsel von '{invoice.status}' nach '{data.status}' ist nicht erlaubt.",
        )

    invoice.status = data.status
    now = datetime.now(timezone.utc)
    if data.status == InvoiceStatus.sent:
        invoice.sent_at = now
    elif data.status == InvoiceStatus.paid:
        invoice.paid_at = now
    elif data.status == InvoiceStatus.cancelled:
        invoice.cancelled_at = now
    elif data.status == InvoiceStatus.issued:
        await _export_invoice_to_outgoing(invoice, db)

    await db.flush()
    await db.refresh(invoice)
    return InvoiceResponse.model_validate(invoice)


async def _export_invoice_to_outgoing(invoice: Invoice, db: AsyncSession):
    """Generiert das PDF (falls nötig) und kopiert es in den STB-Export-Ordner."""
    import shutil
    from app.models.customer import Customer
    from app.models.article import Article
    from app.config import settings

    # Kundendaten und Artikel für PDF-Generierung laden
    customer_result = await db.execute(select(Customer).where(Customer.id == invoice.customer_id))
    invoice.customer = customer_result.scalar_one_or_none()
    for item in invoice.items:
        if item.article_id:
            art_result = await db.execute(select(Article).where(Article.id == item.article_id))
            item.article = art_result.scalar_one_or_none()

    pdf_dir = os.path.join(settings.storage_path, "invoices")
    os.makedirs(pdf_dir, exist_ok=True)

    if not invoice.pdf_path or not os.path.exists(invoice.pdf_path):
        service = ZugferdService()
        pdf_bytes = service.generate_pdf(invoice)
        pdf_path = os.path.join(pdf_dir, f"{invoice.invoice_number}.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        invoice.pdf_path = pdf_path
        await db.flush()

    if settings.stb_export_dir:
        os.makedirs(settings.stb_export_dir, exist_ok=True)
        shutil.copy2(invoice.pdf_path, os.path.join(settings.stb_export_dir, f"{invoice.invoice_number}.pdf"))


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    # Load customer
    customer_result = await db.execute(select(Customer).where(Customer.id == invoice.customer_id))
    customer = customer_result.scalar_one_or_none()
    invoice.customer = customer

    # Load article for items
    from app.models.article import Article
    for item in invoice.items:
        if item.article_id:
            art_result = await db.execute(select(Article).where(Article.id == item.article_id))
            item.article = art_result.scalar_one_or_none()

    service = ZugferdService()
    if invoice.pdf_path and os.path.exists(invoice.pdf_path):
        return FileResponse(
            invoice.pdf_path,
            media_type="application/pdf",
            filename=f"{invoice.invoice_number}.pdf",
        )

    pdf_bytes = service.generate_pdf(invoice)
    from app.config import settings
    pdf_dir = os.path.join(settings.storage_path, "invoices")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f"{invoice.invoice_number}.pdf")

    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    invoice.pdf_path = pdf_path
    await db.flush()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
    )


@router.get("/{invoice_id}/xml")
async def download_invoice_xml(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    customer_result = await db.execute(select(Customer).where(Customer.id == invoice.customer_id))
    customer = customer_result.scalar_one_or_none()
    invoice.customer = customer

    service = ZugferdService()
    if invoice.zugferd_xml:
        xml_content = invoice.zugferd_xml.encode("utf-8")
    else:
        xml_content = service.build_xml(invoice)
        invoice.zugferd_xml = xml_content.decode("utf-8")
        await db.flush()

    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.xml"'},
    )


@router.post("/generate", response_model=List[InvoiceResponse])
async def generate_invoices(
    data: InvoiceGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    service = InvoiceService(db)
    invoice_ids = await service.generate_invoices_for_period(
        period_from=data.period_from,
        period_to=data.period_to,
        contract_ids=data.contract_ids,
        auto_issue=data.auto_issue,
        generated_by=current_user.id,
    )

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.id.in_(invoice_ids))
    )
    invoices = result.scalars().all()
    return [InvoiceResponse.model_validate(inv) for inv in invoices]
