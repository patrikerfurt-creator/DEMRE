"""
Ordnerüberwachung für Belege (Mitarbeiter-Ausgaben).
Scannt alle 60 Sekunden den konfigurierten Beleg-Ordner auf neue PDF/Bild-Dateien,
extrahiert die Belegdaten per KI und legt einen Sidecar ab — ohne DB-Datensatz anzulegen.
Der Admin überprüft die Belege im Frontend und übernimmt sie manuell.
"""
import json
import os
import shutil
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger()

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def get_receipt_staging_dir(storage_path: str) -> str:
    path = os.path.join(storage_path, "receipts", "pending")
    os.makedirs(path, exist_ok=True)
    return path


async def _process_receipt_file(filepath: str, original_name: str):
    """Extrahiert Belegdaten per KI und speichert den Sidecar. Legt keinen DB-Datensatz an."""
    from app.services.invoice_extractor import extract_receipt_data

    extracted = await extract_receipt_data(filepath)
    sidecar = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source_file": original_name,
        "extraction_error": extracted.get("extraction_error"),
        "data": {k: v for k, v in extracted.items() if k != "extraction_error"},
    }
    stem = os.path.splitext(filepath)[0]
    with open(f"{stem}.json", "w", encoding="utf-8") as f:
        json.dump(sidecar, f, ensure_ascii=False, indent=2)

    if "extraction_error" in extracted:
        logger.error("receipt_watcher.extraction_failed",
                     file=original_name, error=extracted["extraction_error"])
    else:
        logger.info("receipt_watcher.file_staged",
                    file=original_name,
                    merchant=extracted.get("merchant"),
                    amount=extracted.get("amount_gross"))


async def run_expense_receipts_watcher():
    from app.config import settings

    watch_dir = settings.expense_receipts_watch_dir
    if not watch_dir or not os.path.isdir(watch_dir):
        if watch_dir:
            logger.warning("receipt_watcher.dir_not_found", path=watch_dir)
        return

    staging_dir = get_receipt_staging_dir(settings.storage_path)

    for filename in list(os.listdir(watch_dir)):
        filepath = os.path.join(watch_dir, filename)
        if not os.path.isfile(filepath):
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue

        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = os.path.splitext(filename)[0]
            staged_name = f"{ts}_{stem}{ext}"
            staged_path = os.path.join(staging_dir, staged_name)
            shutil.move(filepath, staged_path)
            logger.info("receipt_watcher.file_moved", source=filename, target=staged_name)

            await _process_receipt_file(staged_path, filename)

        except Exception as e:
            logger.error("receipt_watcher.error", filename=filename, error=str(e))


def schedule_expense_receipts_watcher(scheduler):
    existing = scheduler.get_job("expense_receipts_watcher")
    if existing:
        return
    scheduler.add_job(
        run_expense_receipts_watcher,
        trigger="interval",
        id="expense_receipts_watcher",
        name="Belege Ordnerüberwachung",
        seconds=60,
        replace_existing=True,
    )
    logger.info("receipt_watcher.scheduled")
