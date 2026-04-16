from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://demre:demre_secret@db:5432/demre"
    database_url_sync: str = "postgresql+psycopg2://demre:demre_secret@db:5432/demre"

    # JWT
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # Storage
    storage_path: str = "/app/storage"
    incoming_invoices_watch_dir: str = "/app/incoming_invoices"
    expense_receipts_watch_dir: str = "/app/expense_receipts"

    # KI-Rechnungsextraktion
    anthropic_api_key: Optional[str] = None

    # Company defaults
    company_name: str = "Demme Immobilien Verwaltung GmbH"
    company_street: str = "Coventrystraße 32"
    company_zip: str = "65934"
    company_city: str = "Frankfurt am Main"
    company_country: str = "DE"
    company_vat_id: Optional[str] = None
    company_tax_number: Optional[str] = None
    company_phone: Optional[str] = None
    company_email: Optional[str] = "info@demme-immobilien.de"
    company_iban: Optional[str] = None
    company_bic: Optional[str] = None
    company_bank_name: Optional[str] = None

    # Invoice numbering
    invoice_number_prefix: str = "RE"
    invoice_number_year_reset: bool = True


settings = Settings()
