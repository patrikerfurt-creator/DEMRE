from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from pydantic import BaseModel
from app.models.incoming_invoice import IncomingInvoiceStatus


class IncomingInvoiceBase(BaseModel):
    external_invoice_number: Optional[str] = None
    creditor_id: UUID
    invoice_date: date
    receipt_date: Optional[date] = None
    due_date: Optional[date] = None
    total_net: Decimal = Decimal("0.00")
    total_vat: Decimal = Decimal("0.00")
    total_gross: Decimal = Decimal("0.00")
    currency: str = "EUR"
    description: Optional[str] = None
    cost_account: Optional[str] = None
    notes: Optional[str] = None
    is_direct_debit: bool = False


class IncomingInvoiceCreate(IncomingInvoiceBase):
    source_pending_file: Optional[str] = None  # Dateiname aus dem Staging-Ordner


class IncomingInvoiceUpdate(BaseModel):
    external_invoice_number: Optional[str] = None
    creditor_id: Optional[UUID] = None
    invoice_date: Optional[date] = None
    receipt_date: Optional[date] = None
    due_date: Optional[date] = None
    total_net: Optional[Decimal] = None
    total_vat: Optional[Decimal] = None
    total_gross: Optional[Decimal] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    cost_account: Optional[str] = None
    notes: Optional[str] = None
    is_direct_debit: Optional[bool] = None


class IncomingInvoiceStatusUpdate(BaseModel):
    status: IncomingInvoiceStatus


class CreditorShort(BaseModel):
    id: UUID
    creditor_number: str
    company_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None

    model_config = {"from_attributes": True}


class IncomingInvoiceResponse(IncomingInvoiceBase):
    id: UUID
    document_number: str
    status: IncomingInvoiceStatus
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    document_path: Optional[str] = None
    creditor: Optional[CreditorShort] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IncomingInvoiceListResponse(BaseModel):
    items: List[IncomingInvoiceResponse]
    total: int
    page: int
    page_size: int
