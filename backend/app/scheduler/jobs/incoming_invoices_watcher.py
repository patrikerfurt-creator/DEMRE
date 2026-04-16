"""
Ordnerüberwachung für Eingangsrechnungen.
Scannt alle 60 Sekunden den konfigurierten Eingangsordner auf neue PDF/Bild-Dateien,
extrahiert die Rechnungsdaten per KI und legt Kreditor + Eingangsrechnung in der DB an.
"""
import json
import os
import shutil
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import structlog

logger = structlog.get_logger()

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return Decimal("0.00")


def _to_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def get_staging_dir(storage_path: str) -> str:
    path = os.path.join(storage_path, "invoices", "incoming", "pending")
    os.makedirs(path, exist_ok=True)
    return path


def get_upload_dir(storage_path: str) -> str:
    path = os.path.join(storage_path, "uploads", "incoming-invoices")
    os.makedirs(path, exist_ok=True)
    return path


async def _find_or_create_creditor(db, extracted: dict) -> object:
    """Sucht einen passenden Kreditor oder legt einen neuen an."""
    from sqlalchemy import text
    from app.models.creditor import Creditor
    from app.core.number_generator import generate_creditor_number

    creditor_name = (extracted.get("creditor_name") or "").strip()

    # Suche nach vorhandenem Kreditor
    if creditor_name:
        result = await db.execute(
            text("""
                SELECT id FROM creditors
                WHERE is_active = true
                  AND (
                      LOWER(company_name) LIKE :pattern
                      OR LOWER(last_name) LIKE :pattern
                  )
                ORDER BY
                    CASE WHEN LOWER(COALESCE(company_name, '')) = :exact THEN 0 ELSE 1 END
                LIMIT 1
            """),
            {"pattern": f"%{creditor_name.lower()}%", "exact": creditor_name.lower()},
        )
        row = result.fetchone()
        if row:
            existing = await db.get(Creditor, row[0])
            logger.info("incoming_watcher.creditor_found", creditor=creditor_name)
            return existing

    # Neuen Kreditor anlegen
    creditor_number = await generate_creditor_number(db)
    creditor = Creditor(
        creditor_number=creditor_number,
        company_name=creditor_name or "Unbekannter Kreditor",
        address_line1=extracted.get("creditor_street"),
        postal_code=extracted.get("creditor_zip"),
        city=extracted.get("creditor_city"),
        country_code=extracted.get("creditor_country") or "DE",
        vat_id=extracted.get("creditor_vat_id"),
        tax_number=extracted.get("creditor_tax_number"),
        iban=extracted.get("creditor_iban"),
        bic=extracted.get("creditor_bic"),
    )
    db.add(creditor)
    await db.flush()
    logger.info("incoming_watcher.creditor_created",
                creditor=creditor.company_name, number=creditor_number)
    return creditor


async def _process_file(filepath: str, original_name: str, storage_path: str):
    """Extrahiert Daten, legt Kreditor + Eingangsrechnung an, verschiebt die Datei."""
    from app.services.invoice_extractor import extract_invoice_data
    from app.database import AsyncSessionLocal
    from app.models.incoming_invoice import IncomingInvoice, IncomingInvoiceStatus
    from app.core.number_generator import generate_document_number

    # 1. Rechnungsdaten per KI extrahieren
    extracted = await extract_invoice_data(filepath)
    if "extraction_error" in extracted:
        logger.error("incoming_watcher.extraction_failed",
                     file=original_name, error=extracted["extraction_error"])
        # Datei bleibt im Staging — Fehler-Sidecar speichern
        stem = os.path.splitext(filepath)[0]
        with open(f"{stem}.json", "w", encoding="utf-8") as f:
            json.dump({"extraction_error": extracted["extraction_error"],
                       "source_file": original_name,
                       "extracted_at": datetime.now(timezone.utc).isoformat()},
                      f, ensure_ascii=False, indent=2)
        return

    async with AsyncSessionLocal() as db:
        # 2. Kreditor finden oder anlegen
        creditor = await _find_or_create_creditor(db, extracted)

        # 3. Eingangsrechnung anlegen
        document_number = await generate_document_number(db, "ER")

        upload_dir = get_upload_dir(storage_path)
        ext = os.path.splitext(original_name)[1].lower()
        dest_name = f"{document_number}{ext}"
        dest_path = os.path.join(upload_dir, dest_name)

        invoice = IncomingInvoice(
            document_number=document_number,
            creditor_id=creditor.id,
            external_invoice_number=extracted.get("external_invoice_number"),
            invoice_date=_to_date(extracted.get("invoice_date")) or date.today(),
            receipt_date=date.today(),
            due_date=_to_date(extracted.get("due_date")),
            total_net=_to_decimal(extracted.get("total_net")),
            total_vat=_to_decimal(extracted.get("total_vat")),
            total_gross=_to_decimal(extracted.get("total_gross")),
            currency=extracted.get("currency") or "EUR",
            description=extracted.get("description"),
            is_direct_debit=bool(extracted.get("is_direct_debit", False)),
            status=IncomingInvoiceStatus.open,
            document_path=dest_path,
        )
        db.add(invoice)

        # 4. Datei in den Upload-Ordner verschieben
        shutil.move(filepath, dest_path)

        await db.commit()

        logger.info(
            "incoming_watcher.invoice_created",
            document_number=document_number,
            creditor=creditor.company_name,
            total_gross=str(invoice.total_gross),
            file=dest_name,
        )

    # Sidecar löschen falls vorhanden
    stem = os.path.splitext(filepath)[0]
    sidecar = f"{stem}.json"
    if os.path.isfile(sidecar):
        os.remove(sidecar)


async def run_incoming_invoices_watcher():
    from app.config import settings

    watch_dir = settings.incoming_invoices_watch_dir
    if not watch_dir or not os.path.isdir(watch_dir):
        if watch_dir:
            logger.warning("incoming_watcher.dir_not_found", path=watch_dir)
        return

    staging_dir = get_staging_dir(settings.storage_path)

    for filename in list(os.listdir(watch_dir)):
        filepath = os.path.join(watch_dir, filename)
        if not os.path.isfile(filepath):
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue

        try:
            # In Staging verschieben
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = os.path.splitext(filename)[0]
            staged_name = f"{ts}_{stem}{ext}"
            staged_path = os.path.join(staging_dir, staged_name)
            shutil.move(filepath, staged_path)
            logger.info("incoming_watcher.file_staged", source=filename, target=staged_name)

            # Verarbeiten (Extraktion + DB)
            await _process_file(staged_path, filename, settings.storage_path)

        except Exception as e:
            logger.error("incoming_watcher.error", filename=filename, error=str(e))


def schedule_incoming_watcher(scheduler):
    existing = scheduler.get_job("incoming_invoices_watcher")
    if existing:
        return
    scheduler.add_job(
        run_incoming_invoices_watcher,
        trigger="interval",
        id="incoming_invoices_watcher",
        name="Eingangsrechnungen Ordnerüberwachung",
        seconds=60,
        replace_existing=True,
    )
    logger.info("incoming_watcher.scheduled")
