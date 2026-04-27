"""
STB-Downloader: Läuft lokal auf dem Windows-Rechner.
Pollt den Cloud-Server auf neue genehmigte Rechnungen/Belege und
verschiebt sie in den Netzwerk-Ordner des Steuerberaters.

Starten:  python stb_downloader.py
Beenden:  Strg+C
"""

import logging
import os
import time
from pathlib import Path

import requests

# ── Konfiguration ──────────────────────────────────────────────────────────────

SERVER_URL   = "http://87.106.219.148:8081"   # Cloud-Server
EMAIL        = "admin@demre.de"
PASSWORD     = "admin123"

TARGET_DIR   = r"\\192.168.161.11\daten\Patrik_Maurer\Demme Intern\Buchhaltung STB\15444-40005\Rechnungseingang"

POLL_INTERVAL = 60   # Sekunden zwischen den Prüfläufen

# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("stb_downloader")

session = requests.Session()
_token: str | None = None


def _login() -> bool:
    global _token
    try:
        r = session.post(
            f"{SERVER_URL}/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            timeout=15,
        )
        r.raise_for_status()
        _token = r.json()["access_token"]
        session.headers.update({"Authorization": f"Bearer {_token}"})
        log.info("Login erfolgreich")
        return True
    except Exception as e:
        log.error("Login fehlgeschlagen: %s", e)
        return False


def _ensure_authenticated() -> bool:
    """Token prüfen; bei Bedarf neu einloggen."""
    try:
        r = session.get(f"{SERVER_URL}/api/v1/stb-export/count", timeout=10)
        if r.status_code == 401:
            return _login()
        return r.ok
    except Exception:
        return _login()


def _poll() -> None:
    if not _ensure_authenticated():
        return

    # Dateiliste holen
    try:
        r = session.get(f"{SERVER_URL}/api/v1/stb-export/files", timeout=10)
        r.raise_for_status()
        files: list[str] = r.json().get("files", [])
    except Exception as e:
        log.error("Dateiliste konnte nicht abgerufen werden: %s", e)
        return

    if not files:
        log.debug("Keine neuen Dateien")
        return

    log.info("%d neue Datei(en) gefunden", len(files))
    target = Path(TARGET_DIR)

    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        log.error("Zielordner nicht erreichbar (%s): %s", TARGET_DIR, e)
        return

    for filename in files:
        dest = target / filename

        # Namenskonflikt vermeiden
        if dest.exists():
            stem, ext = os.path.splitext(filename)
            ts = time.strftime("%Y%m%d_%H%M%S")
            dest = target / f"{stem}_{ts}{ext}"

        # Datei herunterladen
        try:
            r = session.get(
                f"{SERVER_URL}/api/v1/stb-export/files/{requests.utils.quote(filename)}",
                timeout=60,
                stream=True,
            )
            r.raise_for_status()
        except Exception as e:
            log.error("Download fehlgeschlagen (%s): %s", filename, e)
            continue

        # In Zielordner speichern
        try:
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
            log.info("Gespeichert: %s", dest)
        except Exception as e:
            log.error("Speichern fehlgeschlagen (%s → %s): %s", filename, dest, e)
            continue

        # Erst nach erfolgreichem Speichern vom Server löschen
        try:
            session.delete(
                f"{SERVER_URL}/api/v1/stb-export/files/{requests.utils.quote(filename)}",
                timeout=10,
            )
        except Exception as e:
            log.warning("Konnte Datei nicht vom Server löschen (%s): %s", filename, e)


def main() -> None:
    log.info("STB-Downloader gestartet (Server: %s, Ziel: %s)", SERVER_URL, TARGET_DIR)
    log.info("Prüfintervall: %ds  –  Beenden mit Strg+C", POLL_INTERVAL)

    if not _login():
        log.error("Erster Login fehlgeschlagen – trotzdem weiter versuchen")

    while True:
        try:
            _poll()
        except Exception as e:
            log.error("Unerwarteter Fehler: %s", e)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
