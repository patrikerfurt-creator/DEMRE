from pydantic import BaseModel, EmailStr
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class CustomerBase(BaseModel):
    customer_number: Optional[str] = None
    customer_type: str = "weg"
    company_name: Optional[str] = None
    salutation: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country_code: str = "DE"
    email: Optional[str] = None
    phone: Optional[str] = None
    vat_id: Optional[str] = None
    tax_number: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    sepa_mandate_ref: Optional[str] = None
    sepa_mandate_date: Optional[str] = None
    datev_account_number: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    customer_number: Optional[str] = None
    customer_type: Optional[str] = None
    company_name: Optional[str] = None
    salutation: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country_code: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    vat_id: Optional[str] = None
    tax_number: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    sepa_mandate_ref: Optional[str] = None
    sepa_mandate_date: Optional[str] = None
    datev_account_number: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class CustomerResponse(CustomerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    items: List[CustomerResponse]
    total: int
    page: int
    page_size: int


class CustomerImportRow(BaseModel):
    row_number: int
    customer_number: Optional[str] = None
    company_name: Optional[str] = None
    salutation: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country_code: Optional[str] = "DE"
    email: Optional[str] = None
    phone: Optional[str] = None
    vat_id: Optional[str] = None
    tax_number: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    sepa_mandate_ref: Optional[str] = None
    sepa_mandate_date: Optional[str] = None
    datev_account_number: Optional[str] = None
    notes: Optional[str] = None
    errors: List[str] = []
    is_valid: bool = True
