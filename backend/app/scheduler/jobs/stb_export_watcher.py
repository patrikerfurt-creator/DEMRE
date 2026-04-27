"""
STB-Export-Watcher: Verschiebt genehmigte Belege und Eingangsrechnungen aus dem
Export-Staging-Ordner (storage/exports/steuerberater/) in den konfigurierten Zielordner
(z.B. N:\\Patrik_Maurer\\... gemountet als /app/stb_target).
Läuft alle 60 Sekunden. Deaktiviert wenn STB_EXPORT_DIR oder STB_TARGET_DIR leer.
"""
import os
import shutil
from datetime import datetime

import structlog

logger = structlog.get_logger()

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


async def run_stb_export_watcher():
    from app.config import settings

    export_dir = settings.stb_export_dir
    target_dir = settings.stb_target_dir

    if not export_dir or not target_dir:
        return

    if not os.path.isdir(export_dir):
        return

    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as exc:
        logger.warning("stb_watcher.target_not_accessible", target=target_dir, error=str(exc))
        return

    for filename in list(os.listdir(export_dir)):
        filepath = os.path.join(export_dir, filename)
        if not os.path.isfile(filepath):
            continue
        if os.path.splitext(filename)[1].lower() not in ALLOWED_EXTENSIONS:
            continue
        try:
            dest = os.path.join(target_dir, filename)
            if os.path.exists(dest):
                stem, ext = os.path.splitext(filename)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = os.path.join(target_dir, f"{stem}_{ts}{ext}")
            shutil.move(filepath, dest)
            logger.info("stb_watcher.file_moved", filename=filename, target=dest)
        except Exception as exc:
            logger.error("stb_watcher.move_failed", filename=filename, error=str(exc))


def schedule_stb_export_watcher(scheduler):
    from app.config import settings

    if not settings.stb_export_dir or not settings.stb_target_dir:
        logger.info("stb_watcher.disabled", reason="STB_EXPORT_DIR oder STB_TARGET_DIR nicht gesetzt")
        return

    existing = scheduler.get_job("stb_export_watcher")
    if existing:
        return

    scheduler.add_job(
        run_stb_export_watcher,
        trigger="interval",
        id="stb_export_watcher",
        name="STB-Export Ordnerüberwachung",
        seconds=60,
        replace_existing=True,
    )
    logger.info("stb_watcher.scheduled", export_dir=settings.stb_export_dir, target_dir=settings.stb_target_dir)
