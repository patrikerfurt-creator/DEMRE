"""
DEMRE Datei-Uploader — Windows-Dienst
Überwacht lokale Ordner, überträgt neue Dateien per SFTP zum Server
und lädt ausgestellte Ausgangsrechnungen alle 10 Minuten herunter.
"""
import sys
import os
import json
import time
import stat as stat_mod
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
    Lädt eine Datei per SFTP mit SSH-Schlüssel hoch.
    Versucht es bei Fehler bis zu 3-mal, dann wird aufgegeben.
    """
    host     = config["sftp_host"]
    port     = int(config.get("sftp_port", 22))
    user     = config["sftp_user"]
    key_file = config["sftp_key_file"]

    for attempt in range(1, 4):
        client = None
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=host,
                port=port,
                username=user,
                key_filename=key_file,
                look_for_keys=False,
                allow_agent=False,
            )
            sftp = client.open_sftp()
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
            if client:
                client.close()

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
        """Verschiebt die hochgeladene Datei in Hochgeladen\\YYYY-MM-DD\\."""
        dest_dir = self.archive_root / datetime.now().strftime("%Y-%m-%d")
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest    = dest_dir / path.name
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{path.stem}_{counter}{path.suffix}"
            counter += 1

        path.rename(dest)
        logging.info(f"Archiviert: {dest}")


# ── Ausgangsrechnungen-Download ───────────────────────────────────────────────
def _download_outgoing_invoices(config: dict, local_dir: Path, remote_dir: str):
    """
    Verbindet per SFTP zum Server, lädt neue PDFs aus `remote_dir` in `local_dir`
    und verschiebt jede heruntergeladene Datei serverseitig nach `remote_dir/Archiv/`.
    """
    host     = config["sftp_host"]
    port     = int(config.get("sftp_port", 22))
    user     = config["sftp_user"]
    key_file = config["sftp_key_file"]
    archive  = f"{remote_dir}/Archiv"

    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=host,
            port=port,
            username=user,
            key_filename=key_file,
            look_for_keys=False,
            allow_agent=False,
        )
        sftp = client.open_sftp()

        # Remote-Ordner prüfen
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            logging.debug(f"Remote-Ordner noch nicht vorhanden: {remote_dir}")
            sftp.close()
            return

        # Archiv-Unterordner anlegen falls nötig
        try:
            sftp.stat(archive)
        except FileNotFoundError:
            sftp.mkdir(archive)

        entries = sftp.listdir_attr(remote_dir)
        downloaded = 0

        for entry in entries:
            # Unterordner (z. B. Archiv) überspringen
            if stat_mod.S_ISDIR(entry.st_mode):
                continue
            if not entry.filename.lower().endswith(".pdf"):
                continue

            remote_path = f"{remote_dir}/{entry.filename}"
            local_path  = local_dir / entry.filename

            # Bereits lokal vorhandene Datei nicht überschreiben, aber trotzdem archivieren
            if not local_path.exists():
                sftp.get(remote_path, str(local_path))
                logging.info(f"Heruntergeladen: {entry.filename}  ←  {host}:{remote_path}")
                downloaded += 1
            else:
                logging.debug(f"Bereits vorhanden, übersprungen: {entry.filename}")

            # Serverseitig archivieren (verhindert erneutes Herunterladen)
            sftp.rename(remote_path, f"{archive}/{entry.filename}")

        if downloaded:
            logging.info(f"{downloaded} Ausgangsrechnung(en) heruntergeladen.")
        else:
            logging.debug("Keine neuen Ausgangsrechnungen gefunden.")

        sftp.close()

    except Exception as exc:
        logging.warning(f"Download Ausgangsrechnungen fehlgeschlagen: {exc}")
    finally:
        if client:
            client.close()


def _outgoing_download_loop(config: dict, stop_event: threading.Event):
    """
    Polling-Thread: ruft `_download_outgoing_invoices` sofort und dann alle
    10 Minuten auf, bis `stop_event` gesetzt wird.
    """
    local_dir  = Path(config["local_outgoing_invoices_folder"])
    remote_dir = config["remote_outgoing_invoices_dir"]
    local_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Ausgangsrechnungen-Downloader aktiv (alle 10 min) → {local_dir}")

    while not stop_event.is_set():
        try:
            _download_outgoing_invoices(config, local_dir, remote_dir)
        except Exception as exc:
            logging.error(f"Unerwarteter Fehler im Download-Thread: {exc}")
        # 10 Minuten warten; stop_event beendet das Warten vorzeitig
        stop_event.wait(600)

    logging.info("Ausgangsrechnungen-Downloader beendet.")


# ── Windows-Dienst ────────────────────────────────────────────────────────────
class DemreUploaderService(win32serviceutil.ServiceFramework):
    _svc_name_        = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY
    _svc_description_ = SERVICE_DESC

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event      = win32event.CreateEvent(None, 0, 0, None)
        self.observer        = None
        self._download_stop  = threading.Event()
        self._download_thread = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self._download_stop.set()
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

        # Polling-Thread für Ausgangsrechnungen-Download
        if config.get("remote_outgoing_invoices_dir") and config.get("local_outgoing_invoices_folder"):
            self._download_thread = threading.Thread(
                target=_outgoing_download_loop,
                args=(config, self._download_stop),
                daemon=True,
            )
            self._download_thread.start()
        else:
            logging.info("Ausgangsrechnungen-Download nicht konfiguriert (Felder fehlen in config.json)")

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
