"""
DEMRE Datei-Uploader — Windows-Dienst
Überwacht lokale Ordner und überträgt neue Dateien per SFTP zum Server.
"""
import sys
import os
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime

import paramiko
import win32serviceutil
import win32service
import win32event
import servicemanager
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── Konstanten ────────────────────────────────────────────────────────────────
SERVICE_NAME        = "DEMREUploader"
SERVICE_DISPLAY     = "DEMRE Datei-Uploader"
SERVICE_DESC        = "Überwacht lokale Ordner und lädt Belege und Eingangsrechnungen per SFTP hoch."
SUPPORTED_EXT       = {'.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff'}

BASE_DIR    = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
LOG_FILE    = BASE_DIR / "uploader.log"


# ── Logging ───────────────────────────────────────────────────────────────────
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
    )


# ── SFTP ──────────────────────────────────────────────────────────────────────
def sftp_upload(local_path: Path, remote_dir: str, config: dict) -> bool:
    """
    Lädt eine Datei per SFTP hoch.
    Versucht es bei Fehler bis zu 3-mal, dann wird aufgegeben.
    """
    host     = config["sftp_host"]
    port     = int(config.get("sftp_port", 22))
    user     = config["sftp_user"]
    password = config["sftp_password"]

    for attempt in range(1, 4):
        transport = None
        try:
            transport = paramiko.Transport((host, port))
            transport.connect(username=user, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)

            remote_path = f"{remote_dir}/{local_path.name}"
            sftp.put(str(local_path), remote_path)
            sftp.close()

            logging.info(f"OK  {local_path.name}  →  {host}:{remote_path}")
            return True

        except Exception as exc:
            logging.warning(f"Versuch {attempt}/3 fehlgeschlagen ({local_path.name}): {exc}")
            if attempt < 3:
                time.sleep(5)
        finally:
            if transport:
                transport.close()

    logging.error(f"Upload endgültig fehlgeschlagen: {local_path.name}")
    return False


# ── Datei-Stabilität ──────────────────────────────────────────────────────────
def wait_for_stable(path: Path, stable_secs: float = 2.0, timeout: float = 30.0) -> bool:
    """
    Wartet, bis sich die Dateigröße für `stable_secs` Sekunden nicht mehr
    verändert hat (Schreibvorgang des Scanners abgeschlossen).
    """
    prev_size    = -1
    stable_since = None
    deadline     = time.time() + timeout

    while time.time() < deadline:
        try:
            size = path.stat().st_size
        except OSError:
            return False

        if size > 0 and size == prev_size:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= stable_secs:
                return True
        else:
            stable_since = None
            prev_size    = size

        time.sleep(0.5)

    return False


# ── Watchdog-Handler ──────────────────────────────────────────────────────────
class FolderHandler(FileSystemEventHandler):
    def __init__(self, config: dict, remote_dir: str, archive_root: Path):
        self.config       = config
        self.remote_dir   = remote_dir
        self.archive_root = archive_root
        self._active: set = set()
        self._lock        = threading.Lock()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)

        # Nur unterstützte Dateitypen
        if path.suffix.lower() not in SUPPORTED_EXT:
            return

        # Dateien im Hochgeladen-Archiv ignorieren
        try:
            path.relative_to(self.archive_root)
            return
        except ValueError:
            pass

        # Doppelverarbeitung verhindern
        with self._lock:
            if str(path) in self._active:
                return
            self._active.add(str(path))

        threading.Thread(target=self._process, args=(path,), daemon=True).start()

    def _process(self, path: Path):
        try:
            logging.info(f"Neue Datei: {path.name}")

            if not wait_for_stable(path):
                logging.warning(f"Datei nach 30s nicht stabil, übersprungen: {path.name}")
                return

            if sftp_upload(path, self.remote_dir, self.config):
                self._archive(path)

        except Exception as exc:
            logging.error(f"Unerwarteter Fehler bei {path.name}: {exc}")
        finally:
            with self._lock:
                self._active.discard(str(path))

    def _archive(self, path: Path):
        """Verschiebt die hochgeladene Datei in Hochgeladen\YYYY-MM-DD\."""
        dest_dir = self.archive_root / datetime.now().strftime("%Y-%m-%d")
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest    = dest_dir / path.name
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{path.stem}_{counter}{path.suffix}"
            counter += 1

        path.rename(dest)
        logging.info(f"Archiviert: {dest}")


# ── Windows-Dienst ────────────────────────────────────────────────────────────
class DemreUploaderService(win32serviceutil.ServiceFramework):
    _svc_name_        = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY
    _svc_description_ = SERVICE_DESC

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.observer   = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.observer:
            self.observer.stop()
        logging.info("Dienst wird gestoppt …")

    def SvcDoRun(self):
        setup_logging()
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        logging.info("=" * 60)
        logging.info("DEMRE Uploader gestartet")

        # Config laden
        try:
            config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.error(f"config.json konnte nicht geladen werden: {exc}")
            return

        incoming_dir = Path(config["local_incoming_invoices_folder"])
        receipts_dir = Path(config["local_expense_receipts_folder"])

        for d in (incoming_dir, receipts_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Watchdog starten
        self.observer = Observer()
        self.observer.schedule(
            FolderHandler(config, config["remote_incoming_invoices_dir"], incoming_dir / "Hochgeladen"),
            str(incoming_dir),
            recursive=False,
        )
        self.observer.schedule(
            FolderHandler(config, config["remote_expense_receipts_dir"], receipts_dir / "Hochgeladen"),
            str(receipts_dir),
            recursive=False,
        )
        self.observer.start()
        logging.info(f"Überwache Eingangsrechnungen : {incoming_dir}")
        logging.info(f"Überwache Belege             : {receipts_dir}")
        logging.info(f"SFTP-Ziel                    : {config['sftp_host']}")

        # Warten bis Dienst gestoppt wird
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        self.observer.stop()
        self.observer.join()
        logging.info("DEMRE Uploader beendet")


# ── Einstiegspunkt ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Vom Dienst-Manager gestartet
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(DemreUploaderService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # install / start / stop / remove
        win32serviceutil.HandleCommandLine(DemreUploaderService)
