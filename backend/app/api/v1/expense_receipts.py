import json
import os
import shutil
from typing import Optional
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.api.deps import get_db, get_current_user, require_not_readonly, require_admin
from app.models.user import User, UserRole
from app.models.expense_receipt import ExpenseReceipt, ExpenseReceiptStatus
from app.schemas.expense_receipt import (
    ExpenseReceiptCreate, ExpenseReceiptUpdate, ExpenseReceiptStatusUpdate,
    ExpenseReceiptResponse, ExpenseReceiptListResponse,
)
from app.core.number_generator import generate_document_number
from app.config import settings

router = APIRouter(prefix="/expense-receipts", tags=["expense-receipts"])

UPLOAD_DIR = os.path.join(settings.storage_path, "uploads", "expense-receipts")


def _upload_dir() -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    return UPLOAD_DIR


async def _get_receipt_or_404(receipt_id: str, db: AsyncSession) -> ExpenseReceipt:
    result = await db.execute(
        select(ExpenseReceipt)
        .options(
            selectinload(ExpenseReceipt.submitter),
            selectinload(ExpenseReceipt.approver),
        )
        .where(ExpenseReceipt.id == receipt_id)
    )
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Beleg nicht gefunden")
    return receipt


def _receipt_staging_dir() -> str:
    path = os.path.join(settings.storage_path, "receipts", "pending")
    os.makedirs(path, exist_ok=True)
    return path


def _load_receipt_sidecar(staging_dir: str, doc_filename: str) -> dict:
    stem = os.path.splitext(doc_filename)[0]
    sidecar_path = os.path.join(staging_dir, f"{stem}.json")
    if os.path.isfile(sidecar_path):
        try:
            with open(sidecar_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


@router.get("/pending", summary="Staging-Belege aus dem Eingangsordner auflisten")
async def list_pending_receipts(
    _: User = Depends(require_admin),
):
    staging_dir = _receipt_staging_dir()
    files = []
    for filename in sorted(os.listdir(staging_dir)):
        if filename.endswith(".json"):
            continue
        filepath = os.path.join(staging_dir, filename)
        if not os.path.isfile(filepath):
            continue
        stat = os.stat(filepath)
        sidecar = _load_receipt_sidecar(staging_dir, filename)
        files.append({
            "filename": filename,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
            "extracted": sidecar.get("data"),
            "extraction_error": sidecar.get("extraction_error"),
        })
    return {"files": files}


@router.post("/pending/{filename}/extract", summary="Belegdaten (erneut) per KI extrahieren")
async def extract_pending_receipt(
    filename: str,
    _: User = Depends(require_admin),
):
    from app.services.invoice_extractor import extract_receipt_data

    staging_dir = _receipt_staging_dir()
    safe_name = os.path.basename(filename)
    filepath = os.path.join(staging_dir, safe_name)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    extracted = await extract_receipt_data(filepath)
    sidecar = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source_file": safe_name,
        "extraction_error": extracted.get("extraction_error"),
        "data": {k: v for k, v in extracted.items() if k != "extraction_error"},
    }
    stem = os.path.splitext(safe_name)[0]
    with open(os.path.join(staging_dir, f"{stem}.json"), "w", encoding="utf-8") as f:
        json.dump(sidecar, f, ensure_ascii=False, indent=2)
    return sidecar


@router.get("/pending/{filename}/download", summary="Staging-Beleg herunterladen / Vorschau")
async def download_pending_receipt(
    filename: str,
    _: User = Depends(require_admin),
):
    staging_dir = _receipt_staging_dir()
    filepath = os.path.join(staging_dir, os.path.basename(filename))
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return FileResponse(filepath, filename=os.path.basename(filepath))


@router.delete("/pending/{filename}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Staging-Beleg löschen")
async def delete_pending_receipt(
    filename: str,
    _: User = Depends(require_admin),
):
    staging_dir = _receipt_staging_dir()
    safe_name = os.path.basename(filename)
    for path in [
        os.path.join(staging_dir, safe_name),
        os.path.join(staging_dir, f"{os.path.splitext(safe_name)[0]}.json"),
    ]:
        if os.path.isfile(path):
            os.remove(path)


@router.get("", response_model=ExpenseReceiptListResponse)
async def list_expense_receipts(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(ExpenseReceipt).options(
        selectinload(ExpenseReceipt.submitter),
        selectinload(ExpenseReceipt.approver),
    )
    # Non-admins only see their own receipts
    if current_user.role != UserRole.admin:
        query = query.where(ExpenseReceipt.submitted_by == current_user.id)
    if status_filter:
        query = query.where(ExpenseReceipt.status == status_filter)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    query = query.order_by(ExpenseReceipt.receipt_date.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = [ExpenseReceiptResponse.model_validate(r) for r in result.scalars().all()]
    return ExpenseReceiptListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ExpenseReceiptResponse, status_code=status.HTTP_201_CREATED)
async def create_expense_receipt(
    data: ExpenseReceiptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    # submitted_by_id erlaubt Admins, einen anderen Nutzer als Einreicher anzugeben
    submitted_by = data.submitted_by_id or current_user.id

    receipt_number = await generate_document_number(db, "BL")
    receipt_data = data.model_dump(exclude={"source_pending_file", "submitted_by_id"})
    receipt = ExpenseReceipt(
        receipt_number=receipt_number,
        submitted_by=submitted_by,
        **receipt_data,
    )

    # Staging-Datei verschieben, falls angegeben
    if data.source_pending_file:
        pending_file = os.path.basename(data.source_pending_file)
        staging_dir = _receipt_staging_dir()
        src = os.path.join(staging_dir, pending_file)
        if os.path.isfile(src):
            upload_dir = _upload_dir()
            ext = os.path.splitext(pending_file)[1].lower()
            dest_name = f"{receipt_number}{ext}"
            dest = os.path.join(upload_dir, dest_name)
            shutil.move(src, dest)
            receipt.document_path = dest
            # Sidecar löschen
            sidecar = os.path.join(staging_dir, f"{os.path.splitext(pending_file)[0]}.json")
            if os.path.isfile(sidecar):
                os.remove(sidecar)

    db.add(receipt)
    await db.flush()
    return await _get_receipt_or_404(str(receipt.id), db)


@router.get("/{receipt_id}", response_model=ExpenseReceiptResponse)
async def get_expense_receipt(
    receipt_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    receipt = await _get_receipt_or_404(receipt_id, db)
    if current_user.role != UserRole.admin and receipt.submitted_by != current_user.id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    return receipt


@router.put("/{receipt_id}", response_model=ExpenseReceiptResponse)
async def update_expense_receipt(
    receipt_id: str,
    data: ExpenseReceiptUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    receipt = await _get_receipt_or_404(receipt_id, db)
    if current_user.role != UserRole.admin and receipt.submitted_by != current_user.id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    if receipt.status != ExpenseReceiptStatus.submitted and current_user.role != UserRole.admin:
        raise HTTPException(status_code=409, detail="Beleg kann nicht mehr bearbeitet werden")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(receipt, field, value)
    await db.flush()
    return await _get_receipt_or_404(receipt_id, db)


@router.put("/{receipt_id}/status", response_model=ExpenseReceiptResponse)
async def update_expense_receipt_status(
    receipt_id: str,
    data: ExpenseReceiptStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    receipt = await _get_receipt_or_404(receipt_id, db)
    receipt.status = data.status
    now = datetime.now(timezone.utc)
    if data.status == ExpenseReceiptStatus.approved:
        receipt.approved_by = current_user.id
        receipt.approved_at = now
    elif data.status == ExpenseReceiptStatus.paid:
        receipt.paid_at = now
    await db.flush()
    return await _get_receipt_or_404(receipt_id, db)


@router.post("/{receipt_id}/upload")
async def upload_receipt_document(
    receipt_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_not_readonly),
):
    receipt = await _get_receipt_or_404(receipt_id, db)
    if current_user.role != UserRole.admin and receipt.submitted_by != current_user.id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".pdf", ".jpg", ".jpeg", ".png"):
        raise HTTPException(status_code=400, detail="Nur PDF, JPG oder PNG erlaubt")

    filename = f"{receipt.receipt_number}{ext}"
    filepath = os.path.join(_upload_dir(), filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    receipt.document_path = filepath
    await db.flush()
    return {"document_path": filepath, "filename": filename}


@router.get("/{receipt_id}/document")
async def download_receipt_document(
    receipt_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    receipt = await _get_receipt_or_404(receipt_id, db)
    if current_user.role != UserRole.admin and receipt.submitted_by != current_user.id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")
    if not receipt.document_path or not os.path.exists(receipt.document_path):
        raise HTTPException(status_code=404, detail="Kein Dokument vorhanden")
    return FileResponse(receipt.document_path, filename=os.path.basename(receipt.document_path))


@router.post("/sepa-export")
async def sepa_export(
    execution_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Export all approved expense receipts as SEPA pain.001 credit transfer."""
    result = await db.execute(
        select(ExpenseReceipt)
        .options(selectinload(ExpenseReceipt.submitter))
        .where(ExpenseReceipt.status == ExpenseReceiptStatus.approved)
        .where(ExpenseReceipt.payment_method != 'Kreditkarte')
    )
    receipts = result.scalars().all()

    if not receipts:
        raise HTTPException(
            status_code=400,
            detail="Keine genehmigten Belege mit IBAN vorhanden"
        )

    from app.services.sepa_service import SepaService
    sepa = SepaService()
    xml_bytes = sepa.generate_expense_pain001(receipts, execution_date)

    from app.models.payment_run import PaymentRun, RunType, RunStatus
    from decimal import Decimal
    total = sum(Decimal(str(r.amount_gross)) for r in receipts)
    run = PaymentRun(
        run_type=RunType.creditor_payment,
        status=RunStatus.completed,
        triggered_by=current_user.id,
        invoice_count=len(receipts),
        total_amount=total,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)

    now = datetime.now(timezone.utc)
    for receipt in receipts:
        receipt.status = ExpenseReceiptStatus.paid
        receipt.paid_at = now

    await db.flush()

    from fastapi.responses import Response
    filename = f"sepa_belege_{date.today().strftime('%Y%m%d')}.xml"
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
