"""
Kombinierter SEPA-Zahlungsexport für Eingangsrechnungen und Mitarbeiter-Belege.
"""
from typing import List, Optional
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.api.deps import get_db, require_admin
from app.models.user import User
from app.models.incoming_invoice import IncomingInvoice, IncomingInvoiceStatus
from app.models.expense_receipt import ExpenseReceipt, ExpenseReceiptStatus
from app.models.payment_run import PaymentRun, RunType, RunStatus

router = APIRouter(prefix="/sepa", tags=["sepa"])


class PaymentExportRequest(BaseModel):
    incoming_invoice_ids: List[str] = []
    expense_receipt_ids: List[str] = []
    execution_date: Optional[date] = None


@router.post("/payment-export", summary="Kombinierter SEPA-Zahlungsexport")
async def payment_export(
    body: PaymentExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Erstellt eine SEPA pain.001 Überweisung für ausgewählte Eingangsrechnungen
    (Kreditoren) und Mitarbeiter-Belege (Erstattungen) in einer kombinierten Datei.
    """
    from app.services.sepa_service import SepaService

    if not body.incoming_invoice_ids and not body.expense_receipt_ids:
        raise HTTPException(status_code=400, detail="Keine Positionen ausgewählt")

    items = []
    total = Decimal("0")
    now = datetime.now(timezone.utc)

    # ── Eingangsrechnungen ────────────────────────────────────────────────────
    approved_invoices = []
    if body.incoming_invoice_ids:
        result = await db.execute(
            select(IncomingInvoice)
            .options(selectinload(IncomingInvoice.creditor))
            .where(IncomingInvoice.id.in_(body.incoming_invoice_ids))
            .where(IncomingInvoice.status == IncomingInvoiceStatus.approved)
            .where(IncomingInvoice.is_direct_debit.is_(False))
        )
        approved_invoices = result.scalars().all()
        for inv in approved_invoices:
            if not inv.creditor or not inv.creditor.iban:
                continue
            creditor = inv.creditor
            name = (
                creditor.account_holder
                or creditor.company_name
                or f"{creditor.first_name or ''} {creditor.last_name or ''}".strip()
                or "Unbekannt"
            )
            amount = Decimal(str(inv.total_gross))
            ext_ref = inv.external_invoice_number or inv.document_number
            date_str = inv.invoice_date.strftime("%d.%m.%Y") if inv.invoice_date else ""
            description = f"RE {ext_ref} vom {date_str}" if date_str else f"RE {ext_ref}"
            items.append({
                "name": name,
                "iban": creditor.iban,
                "bic": creditor.bic or "NOTPROVIDED",
                "amount": amount,
                "reference": ext_ref,
                "description": description,
            })
            total += amount

    # ── Mitarbeiter-Belege ────────────────────────────────────────────────────
    approved_receipts = []
    if body.expense_receipt_ids:
        result = await db.execute(
            select(ExpenseReceipt)
            .options(selectinload(ExpenseReceipt.submitter))
            .where(ExpenseReceipt.id.in_(body.expense_receipt_ids))
            .where(ExpenseReceipt.status == ExpenseReceiptStatus.approved)
            .where(ExpenseReceipt.payment_method != "Kreditkarte")
        )
        approved_receipts = result.scalars().all()
        for r in approved_receipts:
            if not r.submitter or not r.submitter.iban:
                continue
            amount = Decimal(str(r.amount_gross))
            items.append({
                "name": r.submitter.full_name or "Unbekannt",
                "iban": r.submitter.iban,
                "bic": r.submitter.bic or "NOTPROVIDED",
                "amount": amount,
                "reference": r.receipt_number,
                "description": f"Beleg {r.receipt_number}",
            })
            total += amount

    if not items:
        raise HTTPException(
            status_code=400,
            detail="Keine zahlbaren Positionen — IBAN fehlt oder Status ungültig"
        )

    # ── XML generieren ────────────────────────────────────────────────────────
    sepa = SepaService()
    xml_bytes = sepa._build_credit_transfer_xml(items, body.execution_date or date.today())

    # ── Status aktualisieren ──────────────────────────────────────────────────
    for inv in approved_invoices:
        if inv.creditor and inv.creditor.iban:
            inv.status = IncomingInvoiceStatus.scheduled

    for r in approved_receipts:
        r.status = ExpenseReceiptStatus.paid
        r.paid_at = now

    # ── PaymentRun-Protokoll ──────────────────────────────────────────────────
    run = PaymentRun(
        run_type=RunType.creditor_payment,
        status=RunStatus.completed,
        triggered_by=current_user.id,
        invoice_count=len(items),
        total_amount=total,
        started_at=now,
        completed_at=now,
    )
    db.add(run)
    await db.flush()

    filename = f"sepa_zahlung_{date.today().strftime('%Y%m%d')}.xml"
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
