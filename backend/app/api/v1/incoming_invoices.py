import json
import os
import shutil
import uuid
from typing import Optional
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.api.deps import get_db, get_current_user, require_not_readonly, require_admin
from app.models.user import User
from app.models.incoming_invoice import IncomingInvoice, IncomingInvoiceStatus
from app.models.creditor import Creditor
from app.schemas.incoming_invoice import (
    IncomingInvoiceCreate, IncomingInvoiceUpdate, IncomingInvoiceStatusUpdate,
    IncomingInvoiceResponse, IncomingInvoiceListResponse,
)
from app.core.number_generator import generate_document_number
from app.config import settings

router = APIRouter(prefix="/incoming-invoices", tags=["incoming-invoices"])

UPLOAD_DIR = os.path.join(settings.storage_path, "uploads", "incoming-invoices")


def _upload_dir() -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    return UPLOAD_DIR


async def _get_invoice_or_404(invoice_id: str, db: AsyncSession) -> IncomingInvoice:
    result = await db.execute(
        select(IncomingInvoice)
        .options(selectinload(IncomingInvoice.creditor), selectinload(IncomingInvoice.approver))
        .where(IncomingInvoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Eingangsrechnung nicht gefunden")
    return inv


@router.get("", response_model=IncomingInvoiceListResponse)
async def list_incoming_invoices(
    creditor_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(IncomingInvoice).options(
        selectinload(IncomingInvoice.creditor), selectinload(IncomingInvoice.approver)
    )
    if creditor_id:
        query = query.where(IncomingInvoice.creditor_id == creditor_id)
    if status_filter:
        query = query.where(IncomingInvoice.status == status_filter)
    if date_from:
        query = query.where(IncomingInvoice.invoice_date >= date_from)
    if date_to:
        query = query.where(IncomingInvoice.invoice_date <= date_to)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    query = query.order_by(IncomingInvoice.invoice_date.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [IncomingInvoiceResponse.model_validate(i) for i in result.scalars().all()]
    return IncomingInvoiceListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=IncomingInvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_incoming_invoice(
    data: IncomingInvoiceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    creditor = await db.get(Creditor, data.creditor_id)
    if not creditor:
        raise HTTPException(status_code=404, detail="Kreditor nicht gefunden")

    document_number = await generate_document_number(db, "ER")
    invoice_data = data.model_dump(exclude={"source_pending_file"})
    invoice = IncomingInvoice(document_number=document_number, **invoice_data)

    # Pending-Datei aus dem Staging-Ordner verknüpfen
    if data.source_pending_file:
        pending_file = os.path.basename(data.source_pending_file)
        staging_dir = os.path.join(settings.storage_path, "invoices", "incoming", "pending")
        src = os.path.join(staging_dir, pending_file)
        if os.path.isfile(src):
            upload_dir = _upload_dir()
            ext = os.path.splitext(pending_file)[1].lower()
            dest_name = f"{document_number}{ext}"
            dest = os.path.join(upload_dir, dest_name)
            shutil.move(src, dest)
            invoice.document_path = dest

    db.add(invoice)
    await db.flush()
    return await _get_invoice_or_404(str(invoice.id), db)


def _staging_dir() -> str:
    path = os.path.join(settings.storage_path, "invoices", "incoming", "pending")
    os.makedirs(path, exist_ok=True)
    return path


def _load_sidecar(staging_dir: str, doc_filename: str) -> dict:
    """Lädt die JSON-Sidecar-Datei zur Dokumentdatei, falls vorhanden."""
    stem = os.path.splitext(doc_filename)[0]
    sidecar_path = os.path.join(staging_dir, f"{stem}.json")
    if os.path.isfile(sidecar_path):
        try:
            with open(sidecar_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


@router.get("/pending", summary="Staging-Dateien aus dem Eingangsordner auflisten")
async def list_pending_files(
    _: User = Depends(get_current_user),
):
    """Gibt alle Dateien zurück, die vom Ordner-Watcher eingesammelt wurden,
    inklusive der extrahierten Rechnungsdaten aus der KI-Analyse."""
    staging_dir = _staging_dir()
    files = []
    for filename in sorted(os.listdir(staging_dir)):
        if filename.endswith(".json"):
            continue
        filepath = os.path.join(staging_dir, filename)
        if not os.path.isfile(filepath):
            continue
        stat = os.stat(filepath)
        sidecar = _load_sidecar(staging_dir, filename)
        files.append({
            "filename": filename,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
            "extracted": sidecar.get("data"),
            "extraction_error": sidecar.get("extraction_error"),
            "matched_creditor": sidecar.get("matched_creditor"),
            "is_direct_debit": sidecar.get("is_direct_debit", False),
        })
    return {"files": files}


@router.post("/pending/{filename}/extract", summary="Rechnungsdaten (erneut) per KI extrahieren")
async def extract_pending_file(
    filename: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Startet die KI-Extraktion für eine Staging-Datei manuell (z.B. nach Fehler)."""
    from app.services.invoice_extractor import extract_invoice_data, find_matching_creditor

    staging_dir = _staging_dir()
    safe_name = os.path.basename(filename)
    filepath = os.path.join(staging_dir, safe_name)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    extracted = await extract_invoice_data(filepath)
    matched_creditor = None
    if "extraction_error" not in extracted:
        matched_creditor = await find_matching_creditor(extracted.get("creditor_name"), db)

    sidecar = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source_file": safe_name,
        "extraction_error": extracted.get("extraction_error"),
        "matched_creditor": matched_creditor,
        "is_direct_debit": bool(extracted.get("is_direct_debit", False)),
        "data": {k: v for k, v in extracted.items() if k != "extraction_error"},
    }
    stem = os.path.splitext(safe_name)[0]
    sidecar_path = os.path.join(staging_dir, f"{stem}.json")
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, ensure_ascii=False, indent=2)

    return sidecar


@router.get("/pending/{filename}/download", summary="Staging-Datei herunterladen / Vorschau")
async def download_pending_file(
    filename: str,
    _: User = Depends(get_current_user),
):
    staging_dir = _staging_dir()
    filepath = os.path.join(staging_dir, os.path.basename(filename))
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return FileResponse(filepath, filename=os.path.basename(filepath))


@router.delete("/pending/{filename}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Staging-Datei löschen")
async def delete_pending_file(
    filename: str,
    _: User = Depends(require_not_readonly),
):
    staging_dir = _staging_dir()
    safe_name = os.path.basename(filename)
    for path in [
        os.path.join(staging_dir, safe_name),
        os.path.join(staging_dir, f"{os.path.splitext(safe_name)[0]}.json"),
    ]:
        if os.path.isfile(path):
            os.remove(path)


@router.get("/{invoice_id}", response_model=IncomingInvoiceResponse)
async def get_incoming_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await _get_invoice_or_404(invoice_id, db)


@router.put("/{invoice_id}", response_model=IncomingInvoiceResponse)
async def update_incoming_invoice(
    invoice_id: str,
    data: IncomingInvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    inv = await _get_invoice_or_404(invoice_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(inv, field, value)
    await db.flush()
    return await _get_invoice_or_404(invoice_id, db)


@router.put("/{invoice_id}/status", response_model=IncomingInvoiceResponse)
async def update_incoming_invoice_status(
    invoice_id: str,
    data: IncomingInvoiceStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    from app.models.status_change_log import StatusChangeLog
    inv = await _get_invoice_or_404(invoice_id, db)
    from_status = inv.status.value
    inv.status = data.status
    now = datetime.now(timezone.utc)
    if data.status == IncomingInvoiceStatus.approved:
        inv.approved_by = current_user.id
        inv.approved_at = now
    elif data.status == IncomingInvoiceStatus.paid:
        inv.paid_at = now
    db.add(StatusChangeLog(
        entity_type="incoming_invoice",
        entity_id=inv.id,
        from_status=from_status,
        to_status=data.status.value,
        changed_by_id=current_user.id,
        changed_at=now,
        note=data.note,
    ))
    await db.flush()
    return await _get_invoice_or_404(invoice_id, db)


@router.get("/{invoice_id}/status-history")
async def get_incoming_invoice_status_history(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.models.status_change_log import StatusChangeLog
    from app.schemas.status_change_log import StatusChangeLogResponse
    result = await db.execute(
        select(StatusChangeLog)
        .options(selectinload(StatusChangeLog.changed_by))
        .where(StatusChangeLog.entity_type == "incoming_invoice")
        .where(StatusChangeLog.entity_id == invoice_id)
        .order_by(StatusChangeLog.changed_at.asc())
    )
    return [StatusChangeLogResponse.model_validate(e) for e in result.scalars().all()]


@router.post("/{invoice_id}/upload")
async def upload_document(
    invoice_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_not_readonly),
):
    inv = await _get_invoice_or_404(invoice_id, db)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".pdf", ".jpg", ".jpeg", ".png"):
        raise HTTPException(status_code=400, detail="Nur PDF, JPG oder PNG erlaubt")

    filename = f"{inv.document_number}{ext}"
    filepath = os.path.join(_upload_dir(), filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    inv.document_path = filepath
    await db.flush()
    return {"document_path": filepath, "filename": filename}


@router.get("/{invoice_id}/document")
async def download_document(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    inv = await _get_invoice_or_404(invoice_id, db)
    if not inv.document_path or not os.path.exists(inv.document_path):
        raise HTTPException(status_code=404, detail="Kein Dokument vorhanden")
    return FileResponse(inv.document_path, filename=os.path.basename(inv.document_path))


@router.post("/sepa-export")
async def sepa_export(
    execution_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    """Export all approved incoming invoices as SEPA pain.001 credit transfer."""
    result = await db.execute(
        select(IncomingInvoice)
        .options(selectinload(IncomingInvoice.creditor))
        .where(IncomingInvoice.status == IncomingInvoiceStatus.approved)
    )
    invoices = result.scalars().all()

    if not invoices:
        raise HTTPException(status_code=400, detail="Keine genehmigten Eingangsrechnungen vorhanden")

    from app.services.sepa_service import SepaService
    sepa = SepaService()
    xml_bytes = sepa.generate_creditor_pain001(invoices, execution_date)

    # Mark as scheduled and record payment run
    from app.models.payment_run import PaymentRun, RunType, RunStatus
    from decimal import Decimal
    total = sum(Decimal(str(i.total_gross)) for i in invoices)
    run = PaymentRun(
        run_type=RunType.creditor_payment,
        status=RunStatus.completed,
        triggered_by=current_user.id,
        invoice_count=len(invoices),
        total_amount=total,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)

    from app.models.status_change_log import StatusChangeLog
    now = datetime.now(timezone.utc)
    for inv in invoices:
        from_status = inv.status.value
        inv.status = IncomingInvoiceStatus.scheduled
        db.add(StatusChangeLog(
            entity_type="incoming_invoice",
            entity_id=inv.id,
            from_status=from_status,
            to_status=IncomingInvoiceStatus.scheduled.value,
            changed_by_id=current_user.id,
            changed_at=now,
            note="Automatisch durch SEPA-Export",
        ))

    await db.flush()

    from fastapi.responses import Response
    filename = f"sepa_eingangsrechnungen_{date.today().strftime('%Y%m%d')}.xml"
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
