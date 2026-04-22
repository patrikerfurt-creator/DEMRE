"""
DEMRE Datei-Uploader — Windows-Dienst
Überwacht lokale Ordner, überträgt neue Dateien per SFTP zum Server
und lädt ausgestellte Ausgangsrechnungen sowie STB-Exportdateien
alle 10 Minuten herunter.
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


# ── SFTP-Verbindung ───────────────────────────────────────────────────────────
def _sftp_connect(config: dict) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=config["sftp_host"],
        port=int(config.get("sftp_port", 22)),
        username=config["sftp_user"],
        key_filename=config["sftp_key_file"],
        look_for_keys=False,
        allow_agent=False,
    )
    return client


# ── SFTP Upload ───────────────────────────────────────────────────────────────
def sftp_upload(local_path: Path, remote_dir: str, config: dict) -> bool:
    """
    Lädt eine Datei per SFTP hoch. Erst nach erfolgreichem Upload
    wird die lokale Datei archiviert (→ _archive).
    Versucht es bei Fehler bis zu 3-mal.
    """
    for attempt in range(1, 4):
        client = None
        try:
            client = _sftp_connect(config)
            sftp = client.open_sftp()
            remote_path = f"{remote_dir}/{local_path.name}"
            sftp.put(str(local_path), remote_path)
            sftp.close()
            logging.info(f"OK  {local_path.name}  →  {config['sftp_host']}:{remote_path}")
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
    """Wartet, bis sich die Dateigröße für stable_secs Sekunden nicht mehr verändert."""
    prev_size    = -1
    stable_since = None
    deadline     = time.time() + timeout

    while time.time() < deadline:
        try:
            size = path.stat().st_size
        except OSError:
            # Datei kurzzeitig nicht erreichbar (Netzlaufwerk, Schreibsperre) — weiter warten
            time.sleep(0.5)
            continue

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
    def __init__(self, config: dict, remote_dir: str, archive_root: Path, watch_dir: Path):
        self.config       = config
        self.remote_dir   = remote_dir
        self.archive_root = archive_root
        self.watch_dir    = watch_dir
        self._active: set = set()
        self._lock        = threading.Lock()

    def scan_existing(self):
        """Beim Dienststart bereits vorhandene Dateien hochladen."""
        for path in self.watch_dir.iterdir():
            if path.is_dir():
                continue
            if path.suffix.lower() not in SUPPORTED_EXT:
                continue
            try:
                path.relative_to(self.archive_root)
                continue  # Archiv-Unterordner überspringen
            except ValueError:
                pass
            with self._lock:
                if str(path) in self._active:
                    continue
                self._active.add(str(path))
            logging.info(f"Vorhandene Datei beim Start gefunden: {path.name}")
            threading.Thread(target=self._process, args=(path,), daemon=True).start()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)

        if path.suffix.lower() not in SUPPORTED_EXT:
            return

        # Dateien im Hochgeladen-Archiv ignorieren
        try:
            path.relative_to(self.archive_root)
            return
        except ValueError:
            pass

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

            # Erst hochladen, dann archivieren
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


# ── Generischer SFTP-Download mit serverseitiger Archivierung ─────────────────
def _unique_dest(folder: Path, filename: str) -> Path:
    """Gibt einen kollisionsfreien Zielpfad zurück."""
    dest = folder / filename
    if not dest.exists():
        return dest
    stem, ext = Path(filename).stem, Path(filename).suffix
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return folder / f"{stem}_{ts}{ext}"


def _sftp_download_folder(
    config: dict,
    remote_dir: str,
    local_dirs: list[Path],
    label: str,
    extensions: set[str] | None = None,
):
    """
    Lädt alle Dateien aus `remote_dir` in den ersten Ordner von `local_dirs` herunter
    und kopiert sie anschließend lokal in alle weiteren Ordner.
    Erst nach erfolgreichem Download wird die Datei serverseitig nach
    `remote_dir/Archiv/` verschoben — sie bleibt so lange auf dem Server,
    bis der Download vollständig abgeschlossen ist.

    local_dirs: [primärer Zielordner, optionale weitere Zielordner …]
    extensions: Wenn angegeben, werden nur Dateien mit diesen Endungen geladen.
                None = alle Dateitypen.
    """
    import shutil

    primary = local_dirs[0]
    extras  = local_dirs[1:]
    archive = f"{remote_dir}/Archiv"
    client  = None

    try:
        client = _sftp_connect(config)
        sftp   = client.open_sftp()

        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            logging.debug(f"[{label}] Remote-Ordner noch nicht vorhanden: {remote_dir}")
            sftp.close()
            return

        try:
            sftp.stat(archive)
        except FileNotFoundError:
            sftp.mkdir(archive)

        entries    = sftp.listdir_attr(remote_dir)
        downloaded = 0

        for entry in entries:
            if stat_mod.S_ISDIR(entry.st_mode):
                continue
            if extensions and Path(entry.filename).suffix.lower() not in extensions:
                continue

            remote_path = f"{remote_dir}/{entry.filename}"
            dest        = _unique_dest(primary, entry.filename)

            # 1. In primären Ordner herunterladen
            sftp.get(remote_path, str(dest))
            logging.info(f"[{label}] Heruntergeladen: {entry.filename}  →  {dest}")
            downloaded += 1

            # 2. Erst nach erfolgreichem Download serverseitig archivieren
            sftp.rename(remote_path, f"{archive}/{entry.filename}")

            # 3. Lokal in weitere Zielordner kopieren
            for extra in extras:
                extra_dest = _unique_dest(extra, dest.name)
                try:
                    shutil.copy2(dest, extra_dest)
                    logging.info(f"[{label}] Kopiert nach: {extra_dest}")
                except Exception as exc:
                    logging.warning(f"[{label}] Kopieren nach {extra} fehlgeschlagen: {exc}")

        if downloaded:
            logging.info(f"[{label}] {downloaded} Datei(en) heruntergeladen.")
        else:
            logging.debug(f"[{label}] Keine neuen Dateien.")

        sftp.close()

    except Exception as exc:
        logging.warning(f"[{label}] Download fehlgeschlagen: {exc}")
    finally:
        if client:
            client.close()


# ── Download-Loops ────────────────────────────────────────────────────────────
def _resolve_dirs(value) -> list[Path]:
    """Gibt eine Liste von Paths zurück — akzeptiert String oder Liste."""
    if isinstance(value, list):
        return [Path(p) for p in value]
    return [Path(value)]


def _outgoing_download_loop(config: dict, stop_event: threading.Event):
    local_dirs = _resolve_dirs(config["local_outgoing_invoices_folder"])
    remote_dir = config["remote_outgoing_invoices_dir"]
    for d in local_dirs:
        d.mkdir(parents=True, exist_ok=True)
    logging.info(f"[AR] Ausgangsrechnungen-Download aktiv (alle 10 min) → {', '.join(str(d) for d in local_dirs)}")

    while not stop_event.is_set():
        try:
            _sftp_download_folder(config, remote_dir, local_dirs, "AR", extensions={".pdf"})
        except Exception as exc:
            logging.error(f"[AR] Unerwarteter Fehler: {exc}")
        stop_event.wait(600)

    logging.info("[AR] Ausgangsrechnungen-Downloader beendet.")


def _stb_download_loop(config: dict, stop_event: threading.Event):
    local_dirs = _resolve_dirs(config["local_stb_folder"])
    remote_dir = config["remote_stb_export_dir"]
    for d in local_dirs:
        d.mkdir(parents=True, exist_ok=True)
    logging.info(f"[STB] STB-Export-Download aktiv (alle 10 min) → {', '.join(str(d) for d in local_dirs)}")

    while not stop_event.is_set():
        try:
            _sftp_download_folder(config, remote_dir, local_dirs, "STB")
        except Exception as exc:
            logging.error(f"[STB] Unerwarteter Fehler: {exc}")
        stop_event.wait(600)

    logging.info("[STB] STB-Downloader beendet.")


# ── Windows-Dienst ────────────────────────────────────────────────────────────
class DemreUploaderService(win32serviceutil.ServiceFramework):
    _svc_name_         = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY
    _svc_description_  = SERVICE_DESC

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event       = win32event.CreateEvent(None, 0, 0, None)
        self.observer         = None
        self._download_stop   = threading.Event()
        self._download_thread = None
        self._stb_thread      = None

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

        try:
            config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.error(f"config.json konnte nicht geladen werden: {exc}")
            return

        incoming_dir = Path(config["local_incoming_invoices_folder"])
        receipts_dir = Path(config["local_expense_receipts_folder"])

        for d in (incoming_dir, receipts_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Watchdog für Uploads
        self.observer = Observer()
        handler_incoming = FolderHandler(
            config, config["remote_incoming_invoices_dir"],
            incoming_dir / "Hochgeladen", incoming_dir,
        )
        handler_receipts = FolderHandler(
            config, config["remote_expense_receipts_dir"],
            receipts_dir / "Hochgeladen", receipts_dir,
        )
        self.observer.schedule(handler_incoming, str(incoming_dir), recursive=False)
        self.observer.schedule(handler_receipts, str(receipts_dir), recursive=False)
        self.observer.start()

        # Beim Start bereits vorhandene Dateien hochladen
        handler_incoming.scan_existing()
        handler_receipts.scan_existing()
        logging.info(f"Überwache Eingangsrechnungen : {incoming_dir}")
        logging.info(f"Überwache Belege             : {receipts_dir}")
        logging.info(f"SFTP-Ziel                    : {config['sftp_host']}")

        # Polling-Thread: Ausgangsrechnungen herunterladen
        if config.get("remote_outgoing_invoices_dir") and config.get("local_outgoing_invoices_folder"):
            self._download_thread = threading.Thread(
                target=_outgoing_download_loop,
                args=(config, self._download_stop),
                daemon=True,
            )
            self._download_thread.start()
        else:
            logging.info("[AR] Ausgangsrechnungen-Download nicht konfiguriert")

        # Polling-Thread: STB-Export herunterladen
        if config.get("remote_stb_export_dir") and config.get("local_stb_folder"):
            self._stb_thread = threading.Thread(
                target=_stb_download_loop,
                args=(config, self._download_stop),
                daemon=True,
            )
            self._stb_thread.start()
        else:
            logging.info("[STB] STB-Export-Download nicht konfiguriert")

        # Warten bis Dienst gestoppt wird
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        self.observer.stop()
        self.observer.join()
        logging.info("DEMRE Uploader beendet")


# ── Einstiegspunkt ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(DemreUploaderService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(DemreUploaderService)
