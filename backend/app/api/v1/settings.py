from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.api.deps import get_current_user, require_admin
from app.models.user import User
from app.config import settings

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
    invoice_number_prefix: str
    invoice_number_year_reset: bool


@router.get("", response_model=CompanySettings)
async def get_settings(_: User = Depends(get_current_user)):
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
        invoice_number_prefix=settings.invoice_number_prefix,
        invoice_number_year_reset=settings.invoice_number_year_reset,
    )


@router.put("", response_model=CompanySettings)
async def update_settings(
    data: CompanySettings,
    _: User = Depends(require_admin),
):
    # Update in-memory settings (persists until restart unless .env is updated)
    settings.company_name = data.company_name
    settings.company_street = data.company_street
    settings.company_zip = data.company_zip
    settings.company_city = data.company_city
    settings.company_country = data.company_country
    settings.company_phone = data.company_phone
    settings.company_email = data.company_email
    settings.company_vat_id = data.company_vat_id
    settings.company_tax_number = data.company_tax_number
    settings.company_iban = data.company_iban
    settings.company_bic = data.company_bic
    settings.company_bank_name = data.company_bank_name
    settings.invoice_number_prefix = data.invoice_number_prefix
    settings.invoice_number_year_reset = data.invoice_number_year_reset

    # Also persist to .env file
    import os
    env_path = ".env"
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()

    env_updates = {
        "COMPANY_NAME": data.company_name,
        "COMPANY_STREET": data.company_street,
        "COMPANY_ZIP": data.company_zip,
        "COMPANY_CITY": data.company_city,
        "COMPANY_COUNTRY": data.company_country,
        "COMPANY_PHONE": data.company_phone or "",
        "COMPANY_EMAIL": data.company_email or "",
        "COMPANY_VAT_ID": data.company_vat_id or "",
        "COMPANY_TAX_NUMBER": data.company_tax_number or "",
        "COMPANY_IBAN": data.company_iban or "",
        "COMPANY_BIC": data.company_bic or "",
        "COMPANY_BANK_NAME": data.company_bank_name or "",
        "INVOICE_NUMBER_PREFIX": data.invoice_number_prefix,
        "INVOICE_NUMBER_YEAR_RESET": str(data.invoice_number_year_reset).lower(),
    }

    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=")[0].strip()
            if key in env_updates:
                new_lines.append(f"{key}={env_updates[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    for key, val in env_updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)

    return data
