"""Laden und Speichern der ueber die Oberflaeche aenderbaren Einstellungen.

Quelle der Wahrheit ist die Tabelle `app_settings`. Beim Start des Backends
werden die dort hinterlegten Werte auf das Settings-Objekt aus `app.config`
gelegt, das im uebrigen Code (PDF-Erzeugung, SEPA, Rechnungslauf) gelesen wird.

Rangfolge: Datenbank > Umgebungsvariable > .env-Datei > Default aus config.py

Frueher schrieb der Settings-Endpoint direkt in eine .env-Datei. Das lag im
Container unter /app/.env, also ausserhalb jedes Volumes, und war nach dem
naechsten Rebuild verloren.

Bewusst NICHT enthalten sind die DATEV-Berater- und Mandantennummer: die
kommen ausschliesslich aus .env.prod, siehe app/api/v1/settings.py.
"""
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.app_setting import AppSetting


# Felder, die ueber die Oberflaeche gepflegt und in der Datenbank abgelegt werden.
MANAGED_KEYS: tuple[str, ...] = (
    "company_name",
    "company_street",
    "company_zip",
    "company_city",
    "company_country",
    "company_phone",
    "company_email",
    "company_vat_id",
    "company_tax_number",
    "company_iban",
    "company_bic",
    "company_bank_name",
)

# Diese Felder sind in config.py als `str` typisiert und werden z.B. in jedem
# Rechnungs-PDF ausgegeben. Ein leerer Wert wuerde die PDF-Erzeugung
# beschaedigen, deshalb wird er verworfen statt uebernommen.
_REQUIRED_KEYS = frozenset({
    "company_name",
    "company_street",
    "company_zip",
    "company_city",
    "company_country",
})


def _apply(key: str, value: Optional[str]) -> None:
    """Uebernimmt einen Wert in das laufende Settings-Objekt."""
    if key in _REQUIRED_KEYS:
        if value:
            setattr(settings, key, value)
    else:
        setattr(settings, key, value or None)


async def load_into_settings(db: AsyncSession) -> int:
    """Laedt die gespeicherten Werte und legt sie auf das Settings-Objekt.

    Wird beim Start aufgerufen. Gibt die Anzahl uebernommener Werte zurueck.
    """
    rows = (await db.execute(select(AppSetting))).scalars().all()
    applied = 0
    for row in rows:
        if row.key in MANAGED_KEYS:
            _apply(row.key, row.value)
            applied += 1
    return applied


async def save(db: AsyncSession, values: dict[str, Optional[str]]) -> None:
    """Schreibt die uebergebenen Werte in die Datenbank und uebernimmt sie sofort.

    Unbekannte Schluessel werden ignoriert, fehlende Schluessel unveraendert
    gelassen.
    """
    for key in MANAGED_KEYS:
        if key not in values:
            continue
        value = values[key]
        await db.execute(
            pg_insert(AppSetting)
            .values(key=key, value=value)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": value, "updated_at": func.now()},
            )
        )
        _apply(key, value)
    await db.flush()
