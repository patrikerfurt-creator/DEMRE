"""
Einmalig: Kopiert alle bereits genehmigten (approved / scheduled / paid)
Eingangsrechnungen und Belege in den STB-Export-Ordner.
Ausführen: docker exec demre-backend-1 python backfill_stb_export.py
"""
import asyncio
import os
import shutil

from sqlalchemy import select


async def main():
    from app.config import settings
    from app.database import AsyncSessionLocal
    # Alle Modelle importieren damit SQLAlchemy Beziehungen auflösen kann
    import app.models.creditor  # noqa: F401
    import app.models.user      # noqa: F401
    from app.models.incoming_invoice import IncomingInvoice, IncomingInvoiceStatus
    from app.models.expense_receipt import ExpenseReceipt, ExpenseReceiptStatus

    export_dir = settings.stb_export_dir
    if not export_dir:
        print("STB_EXPORT_DIR nicht konfiguriert – abgebrochen.")
        return

    os.makedirs(export_dir, exist_ok=True)

    invoice_statuses = {
        IncomingInvoiceStatus.approved,
        IncomingInvoiceStatus.scheduled,
        IncomingInvoiceStatus.paid,
    }
    receipt_statuses = {
        ExpenseReceiptStatus.approved,
        ExpenseReceiptStatus.paid,
    }

    copied = 0
    skipped = 0

    async with AsyncSessionLocal() as db:
        # Eingangsrechnungen
        result = await db.execute(
            select(IncomingInvoice).where(IncomingInvoice.status.in_(invoice_statuses))
        )
        for inv in result.scalars().all():
            if not inv.document_path or not os.path.isfile(inv.document_path):
                skipped += 1
                continue
            dest = os.path.join(export_dir, os.path.basename(inv.document_path))
            if os.path.exists(dest):
                print(f"  Bereits vorhanden, übersprungen: {os.path.basename(inv.document_path)}")
                skipped += 1
                continue
            shutil.copy2(inv.document_path, dest)
            print(f"  Kopiert (ER): {os.path.basename(inv.document_path)}")
            copied += 1

        # Belege
        result = await db.execute(
            select(ExpenseReceipt).where(ExpenseReceipt.status.in_(receipt_statuses))
        )
        for rec in result.scalars().all():
            if not rec.document_path or not os.path.isfile(rec.document_path):
                skipped += 1
                continue
            dest = os.path.join(export_dir, os.path.basename(rec.document_path))
            if os.path.exists(dest):
                print(f"  Bereits vorhanden, übersprungen: {os.path.basename(rec.document_path)}")
                skipped += 1
                continue
            shutil.copy2(rec.document_path, dest)
            print(f"  Kopiert (BL): {os.path.basename(rec.document_path)}")
            copied += 1

    print(f"\nFertig: {copied} Datei(en) kopiert, {skipped} übersprungen.")
    print(f"Zielordner: {export_dir}")


if __name__ == "__main__":
    asyncio.run(main())
