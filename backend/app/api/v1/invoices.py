from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from datetime import date, datetime, timezone
import os

from app.api.deps import get_db, get_current_user, require_not_readonly
from app.models.user import User
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus, DocumentType
from app.models.customer import Customer
from app.models.status_change_log import StatusChangeLog
from app.schemas.invoice import (
    InvoiceCreate, InvoiceUpdate, InvoiceResponse,
    InvoiceGenerateRequest, InvoiceStatusUpdate, InvoiceItemCreate,
    CreditNoteCreateRequest, LinkedDocumentInfo,
)
from app.services.invoice_service import InvoiceService
from app.services.zugferd_service import ZugferdService
from app.core.number_generator import generate_invoice_number, generate_credit_note_number
from decimal import Decimal

router = APIRouter(prefix="/invoices", tags=["invoices"])

# Aus diesen Status heraus darf eine Rechnung gutgeschrieben werden
_CREDITABLE_STATUSES = {
    InvoiceStatus.issued,
    InvoiceStatus.sent,
    InvoiceStatus.paid,
    InvoiceStatus.overdue,
}


async def _build_invoice_response(invoice: Invoice, db: AsyncSession) -> InvoiceResponse:
    """InvoiceResponse inkl. der Verweise zwischen Rechnung und Gutschrift."""
    response = InvoiceResponse.model_validate(invoice)
    if invoice.credit_note_of_id:
        result = await db.execute(
            select(Invoice.invoice_number).where(Invoice.id == invoice.credit_note_of_id)
        )
        response.credit_note_of_number = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(Invoice)
            .where(Invoice.credit_note_of_id == invoice.id)
            .where(Invoice.status != InvoiceStatus.cancelled)
            .order_by(Invoice.created_at.desc())
        )
        credit_note = result.scalars().first()
        if credit_note:
            response.credit_note = LinkedDocumentInfo.model_validate(credit_note)
    return response


async def _load_document_relations(invoice: Invoice, db: AsyncSession) -> None:
    """Laedt Kunde, Artikel und (bei Gutschriften) die Ursprungsrechnung.

    Die Relationen sind lazy="select" und koennen im Async-Kontext nicht
    nachtraeglich geladen werden - PDF und XML brauchen sie aber.
    """
    from app.models.article import Article

    customer_result = await db.execute(
        select(Customer).where(Customer.id == invoice.customer_id)
    )
    invoice.customer = customer_result.scalar_one_or_none()

    for item in invoice.items:
        if item.article_id:
            art_result = await db.execute(select(Article).where(Article.id == item.article_id))
            item.article = art_result.scalar_one_or_none()

    # BT-25: Rechnungsbezug der Gutschrift
    if invoice.credit_note_of_id:
        source_result = await db.execute(
            select(Invoice).where(Invoice.id == invoice.credit_note_of_id)
        )
        invoice.credit_note_of = source_result.scalar_one_or_none()


@router.get("", response_model=List[InvoiceResponse])
async def list_invoices(
    customer_id: Optional[str] = Query(None),
    status: Optional[InvoiceStatus] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    document_type: str = Query("invoice", pattern="^(invoice|credit_note|all)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Invoice).options(selectinload(Invoice.items))

    # Standard ist "invoice": bestehende Aufrufer (Dashboard, Rechnungsliste)
    # sehen dadurch weiterhin ausschliesslich Ausgangsrechnungen.
    if document_type != "all":
        query = query.where(Invoice.document_type == DocumentType(document_type))

    if search:
        like = f"%{search}%"
        query = query.join(Customer, Invoice.customer_id == Customer.id).where(
            or_(
                Invoice.invoice_number.ilike(like),
                Customer.company_name.ilike(like),
                Customer.first_name.ilike(like),
                Customer.last_name.ilike(like),
            )
        )
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
    if data.credit_note_of_id:
        # Gutschriften mit Rechnungsbezug laufen ueber den dedizierten Endpunkt -
        # nur dort greifen die Pruefungen (Status, keine Doppelgutschrift).
        raise HTTPException(
            status_code=400,
            detail="Gutschriften zu einer Rechnung bitte über "
                   "POST /invoices/{id}/credit-note anlegen.",
        )

    if data.document_type == DocumentType.credit_note:
        if not (data.credit_reason or "").strip():
            raise HTTPException(
                status_code=400, detail="Ein Gutschriftsgrund ist erforderlich."
            )
        invoice_number = await generate_credit_note_number(db)
    else:
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
    return await _build_invoice_response(invoice, db)


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
    # Summen geaendert -> ein bereits erzeugtes PDF/XML ist veraltet
    invoice.pdf_path = None
    invoice.zugferd_xml = None
    await db.flush()


# Rechnungen lassen sich NICHT direkt stornieren: eine ausgestellte Rechnung
# wird ausschliesslich durch eine Gutschrift aufgehoben (_cancel_credited_invoice
# setzt den Status dann selbst). Ein Storno ohne Beleg waere gegenueber Kunde und
# Steuerberater nicht nachvollziehbar und liesse die Soll-Buchung im DATEV-Stapel
# ohne Gegenbuchung stehen.
_ALLOWED_TRANSITIONS: dict[InvoiceStatus, set[InvoiceStatus]] = {
    InvoiceStatus.draft:     {InvoiceStatus.issued},
    InvoiceStatus.issued:    {InvoiceStatus.sent, InvoiceStatus.paid, InvoiceStatus.overdue},
    InvoiceStatus.sent:      {InvoiceStatus.paid, InvoiceStatus.overdue},
    InvoiceStatus.overdue:   {InvoiceStatus.paid},
    InvoiceStatus.paid:      set(),
    InvoiceStatus.cancelled: set(),
}

# Gutschriften kennen kein "overdue" - sie werden nicht faellig, sondern erstattet
_ALLOWED_TRANSITIONS_CREDIT_NOTE: dict[InvoiceStatus, set[InvoiceStatus]] = {
    InvoiceStatus.draft:     {InvoiceStatus.issued},
    InvoiceStatus.issued:    {InvoiceStatus.sent, InvoiceStatus.paid, InvoiceStatus.cancelled},
    InvoiceStatus.sent:      {InvoiceStatus.paid, InvoiceStatus.cancelled},
    InvoiceStatus.overdue:   {InvoiceStatus.paid, InvoiceStatus.cancelled},
    InvoiceStatus.paid:      set(),
    InvoiceStatus.cancelled: set(),
}


def _outgoing_export_dir() -> str:
    from app.config import settings
    return os.path.join(settings.storage_path, "invoices", "outgoing_export")


def _remove_from_outgoing_export(invoice_number: str) -> None:
    """Entfernt einen stornierten Beleg aus dem STB-Export-Ordner.

    Ohne das liegt beim Steuerberater weiterhin die stornierte Rechnung
    als scheinbar gueltiger Beleg.
    """
    path = os.path.join(_outgoing_export_dir(), f"{invoice_number}.pdf")
    try:
        os.remove(path)
    except OSError:
        pass


async def _cancel_credited_invoice(
    credit_note: Invoice, db: AsyncSession, user_id, now
) -> None:
    """Storniert die Ursprungsrechnung, wenn sie vollstaendig gutgeschrieben wurde."""
    if not credit_note.credit_note_of_id:
        return
    result = await db.execute(
        select(Invoice).where(Invoice.id == credit_note.credit_note_of_id)
    )
    source = result.scalar_one_or_none()
    if not source or source.status == InvoiceStatus.cancelled:
        return
    # Teilgutschrift (Positionen im Entwurf gekuerzt): Rechnung bleibt offen
    if credit_note.total_gross != source.total_gross:
        return

    from_status = source.status.value
    source.status = InvoiceStatus.cancelled
    source.cancelled_at = now
    db.add(
        StatusChangeLog(
            entity_type="invoice",
            entity_id=source.id,
            from_status=from_status,
            to_status=InvoiceStatus.cancelled.value,
            changed_by_id=user_id,
            changed_at=now,
            note=f"Automatisch storniert durch Gutschrift {credit_note.invoice_number}",
        )
    )
    _remove_from_outgoing_export(source.invoice_number)


async def _restore_credited_invoice(
    credit_note: Invoice, db: AsyncSession, user_id, now
) -> None:
    """Hebt den Auto-Storno auf, wenn die Gutschrift selbst storniert wird.

    Ohne das bliebe die Rechnung storniert, obwohl es keine gueltige Gutschrift
    mehr gibt - und da stornierte Rechnungen nicht gutgeschrieben werden koennen,
    waere sie dauerhaft blockiert.
    """
    if not credit_note.credit_note_of_id:
        return
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.id == credit_note.credit_note_of_id)
    )
    source = result.scalar_one_or_none()
    if not source or source.status != InvoiceStatus.cancelled:
        return

    # Status vor dem Auto-Storno aus dem Aenderungslog holen
    log_result = await db.execute(
        select(StatusChangeLog.from_status)
        .where(StatusChangeLog.entity_id == source.id)
        .where(StatusChangeLog.to_status == InvoiceStatus.cancelled.value)
        .order_by(StatusChangeLog.changed_at.desc())
    )
    previous = log_result.scalars().first()
    valid = {st.value for st in InvoiceStatus} - {InvoiceStatus.cancelled.value}
    restored = InvoiceStatus(previous) if previous in valid else InvoiceStatus.issued

    source.status = restored
    source.cancelled_at = None
    db.add(
        StatusChangeLog(
            entity_type="invoice",
            entity_id=source.id,
            from_status=InvoiceStatus.cancelled.value,
            to_status=restored.value,
            changed_by_id=user_id,
            changed_at=now,
            note=f"Storno aufgehoben: Gutschrift {credit_note.invoice_number} "
                 f"wurde storniert",
        )
    )
    # Rechnung gehoert wieder in den STB-Export
    await _export_invoice_to_outgoing(source, db)


@router.put("/{invoice_id}/status", response_model=InvoiceResponse)
async def update_invoice_status(
    invoice_id: str,
    data: InvoiceStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    is_credit_note = invoice.document_type == DocumentType.credit_note
    transitions = (
        _ALLOWED_TRANSITIONS_CREDIT_NOTE if is_credit_note else _ALLOWED_TRANSITIONS
    )
    if data.status not in transitions.get(invoice.status, set()):
        if data.status == InvoiceStatus.cancelled and not is_credit_note:
            raise HTTPException(
                status_code=400,
                detail="Rechnungen werden nicht direkt storniert. Erstelle eine "
                       "Gutschrift zu dieser Rechnung - die Rechnung wird beim "
                       "Ausstellen der Gutschrift automatisch storniert.",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Statuswechsel von '{invoice.status.value}' nach "
                   f"'{data.status.value}' ist nicht erlaubt.",
        )

    from_status = invoice.status.value
    invoice.status = data.status
    now = datetime.now(timezone.utc)
    if data.status == InvoiceStatus.sent:
        invoice.sent_at = now
    elif data.status == InvoiceStatus.paid:
        invoice.paid_at = now
    elif data.status == InvoiceStatus.cancelled:
        invoice.cancelled_at = now
        _remove_from_outgoing_export(invoice.invoice_number)
        if is_credit_note:
            await _restore_credited_invoice(invoice, db, current_user.id, now)
    elif data.status == InvoiceStatus.issued:
        await _export_invoice_to_outgoing(invoice, db)
        if is_credit_note:
            await _cancel_credited_invoice(invoice, db, current_user.id, now)

    db.add(
        StatusChangeLog(
            entity_type="credit_note" if is_credit_note else "invoice",
            entity_id=invoice.id,
            from_status=from_status,
            to_status=data.status.value,
            changed_by_id=current_user.id,
            changed_at=now,
            note=data.note,
        )
    )

    await db.flush()
    await db.refresh(invoice)
    return await _build_invoice_response(invoice, db)


@router.post("/{invoice_id}/credit-note", response_model=InvoiceResponse, status_code=201)
async def create_credit_note(
    invoice_id: str,
    data: CreditNoteCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    """Vollgutschrift zu einer Rechnung: uebernimmt alle Positionen als Entwurf.

    Die Gutschrift entsteht bewusst als Entwurf - Positionen bleiben ueber die
    Item-Endpunkte editierbar (= Weg zur Teilgutschrift), das Ausstellen ist ein
    zweiter, bewusster Schritt.
    """
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    if invoice.document_type != DocumentType.invoice:
        raise HTTPException(
            status_code=400,
            detail="Zu einer Gutschrift kann keine weitere Gutschrift erstellt werden.",
        )
    if invoice.status not in _CREDITABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Nur ausgestellte Rechnungen können gutgeschrieben werden.",
        )

    existing = await db.execute(
        select(Invoice.invoice_number)
        .where(Invoice.credit_note_of_id == invoice.id)
        .where(Invoice.status != InvoiceStatus.cancelled)
    )
    existing_number = existing.scalars().first()
    if existing_number:
        raise HTTPException(
            status_code=400,
            detail=f"Zu dieser Rechnung existiert bereits die Gutschrift {existing_number}.",
        )

    credit_reason = (data.credit_reason or "").strip()
    if not credit_reason:
        raise HTTPException(status_code=400, detail="Ein Gutschriftsgrund ist erforderlich.")

    issue_date = data.invoice_date or date.today()
    credit_note = Invoice(
        invoice_number=await generate_credit_note_number(db),
        document_type=DocumentType.credit_note,
        contract_id=invoice.contract_id,
        customer_id=invoice.customer_id,
        invoice_date=issue_date,
        # Eine Gutschrift hat keine Zahlungsfrist, die Spalte ist aber NOT NULL
        due_date=issue_date,
        billing_period_from=invoice.billing_period_from,
        billing_period_to=invoice.billing_period_to,
        status=InvoiceStatus.draft,
        currency=invoice.currency,
        credit_note_of_id=invoice.id,
        credit_reason=credit_reason,
        subtotal_net=invoice.subtotal_net,
        total_vat=invoice.total_vat,
        total_gross=invoice.total_gross,
        generated_by=current_user.id,
    )
    db.add(credit_note)
    await db.flush()

    # Positionen 1:1 uebernehmen - Betraege bleiben positiv (EN16931 TypeCode 381)
    for item in invoice.items:
        db.add(
            InvoiceItem(
                invoice_id=credit_note.id,
                article_id=item.article_id,
                position=item.position,
                description=item.description,
                additional_text=item.additional_text,
                quantity=item.quantity,
                unit=item.unit,
                unit_price_net=item.unit_price_net,
                vat_rate=item.vat_rate,
                total_net=item.total_net,
                total_vat=item.total_vat,
                total_gross=item.total_gross,
            )
        )
    await db.flush()
    await _recalc_invoice_totals(credit_note, db)

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.items))
        .where(Invoice.id == credit_note.id)
    )
    return await _build_invoice_response(result.scalar_one(), db)


async def _export_invoice_to_outgoing(invoice: Invoice, db: AsyncSession):
    """Generiert das PDF (falls nötig) und kopiert es in den STB-Export-Ordner."""
    import shutil
    from app.config import settings

    await _load_document_relations(invoice, db)

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

    outgoing_dir = os.path.join(settings.storage_path, "invoices", "outgoing_export")
    os.makedirs(outgoing_dir, exist_ok=True)
    shutil.copy2(invoice.pdf_path, os.path.join(outgoing_dir, f"{invoice.invoice_number}.pdf"))


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

    await _load_document_relations(invoice, db)

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

    await _load_document_relations(invoice, db)

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
