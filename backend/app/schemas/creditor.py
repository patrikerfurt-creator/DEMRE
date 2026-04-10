from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class CreditorBase(BaseModel):
    company_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country_code: str = "DE"
    email: Optional[str] = None
    phone: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    vat_id: Optional[str] = None
    tax_number: Optional[str] = None
    datev_account_number: Optional[str] = None
    payment_terms_days: int = 30
    notes: Optional[str] = None
    is_active: bool = True


class CreditorCreate(CreditorBase):
    pass


class CreditorUpdate(BaseModel):
    company_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country_code: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    vat_id: Optional[str] = None
    tax_number: Optional[str] = None
    datev_account_number: Optional[str] = None
    payment_terms_days: Optional[int] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class CreditorResponse(CreditorBase):
    id: UUID
    creditor_number: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreditorListResponse(BaseModel):
    items: List[CreditorResponse]
    total: int
    page: int
    page_size: int
