from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.config import settings
from app.services import settings_store

router = APIRouter(prefix="/settings", tags=["settings"])


class CompanySettings(BaseModel):
    company_name: str
    company_street: str
    company_zip: str
    company_city: str
    company_country: str
    company_phone: Optional[str] = None
    company_email: Optional[str] = None
    company_vat_id: Optional[str] = None
    company_tax_number: Optional[str] = None
    company_iban: Optional[str] = None
    company_bic: Optional[str] = None
    company_bank_name: Optional[str] = None
    invoice_number_prefix: Optional[str] = None
    invoice_number_year_reset: Optional[bool] = None
    # Nur lesend: werden serverseitig aus .env.prod gesetzt (siehe update_settings).
    datev_berater_number: Optional[str] = None
    datev_mandant_number: Optional[str] = None


def _current_settings() -> CompanySettings:
    return CompanySettings(
        company_name=settings.company_name,
        company_street=settings.company_street,
        company_zip=settings.company_zip,
        company_city=settings.company_city,
        company_country=settings.company_country,
        company_phone=settings.company_phone,
        company_email=settings.company_email,
        company_vat_id=settings.company_vat_id,
        company_tax_number=settings.company_tax_number,
        company_iban=settings.company_iban,
        company_bic=settings.company_bic,
        company_bank_name=settings.company_bank_name,
        invoice_number_prefix=None,
        invoice_number_year_reset=None,
        datev_berater_number=settings.datev_berater_number,
        datev_mandant_number=settings.datev_mandant_number,
    )


@router.get("", response_model=CompanySettings)
async def get_settings(_: User = Depends(get_current_user)):
    return _current_settings()


@router.put("", response_model=CompanySettings)
async def update_settings(
    data: CompanySettings,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Speichert die Firmendaten dauerhaft in der Tabelle app_settings.

    Frueher wurde hier in eine .env-Datei geschrieben. Die lag im Container
    unter /app/.env, also in keinem Volume, und war nach jedem Rebuild weg.

    Die DATEV-Berater-/Mandantennummer wird bewusst NICHT uebernommen. Sie
    steht in .env.prod und liegt damit als echte Umgebungsvariable vor, die in
    pydantic-settings Vorrang vor allem hier Gespeicherten hat. Ein Schreiben
    waere nur bis zum naechsten Neustart wirksam und wuerde zwischenzeitlich
    einen falschen DATEV-Stapel-Header erzeugen.
    """
    await settings_store.save(
        db, {key: getattr(data, key) for key in settings_store.MANAGED_KEYS}
    )
    return _current_settings()
