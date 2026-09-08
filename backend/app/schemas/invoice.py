from pydantic import BaseModel, field_serializer
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from app.models.invoice import InvoiceStatus, DocumentType


class InvoiceItemBase(BaseModel):
    article_id: Optional[UUID] = None
    position: int = 1
    description: str
    additional_text: Optional[str] = None
    quantity: Decimal
    unit: Optional[str] = None
    unit_price_net: Decimal
    vat_rate: Decimal
    total_net: Decimal
    total_vat: Decimal
    total_gross: Decimal


class InvoiceItemCreate(InvoiceItemBase):
    pass


class InvoiceItemResponse(InvoiceItemBase):
    id: UUID
    invoice_id: UUID

    @field_serializer("quantity")
    def serialize_quantity(self, value: Decimal) -> str:
        return format(value.normalize(), "f")

    model_config = {"from_attributes": True}


class InvoiceBase(BaseModel):
    document_type: DocumentType = DocumentType.invoice
    contract_id: Optional[UUID] = None
    customer_id: UUID
    invoice_date: date
    due_date: date
    billing_period_from: Optional[date] = None
    billing_period_to: Optional[date] = None
    status: InvoiceStatus = InvoiceStatus.draft
    currency: str = "EUR"
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    credit_note_of_id: Optional[UUID] = None
    credit_reason: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    items: List[InvoiceItemCreate] = []


class InvoiceUpdate(BaseModel):
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    billing_period_from: Optional[date] = None
    billing_period_to: Optional[date] = None
    status: Optional[InvoiceStatus] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None


class InvoiceStatusUpdate(BaseModel):
    status: InvoiceStatus
    note: Optional[str] = None


class CreditNoteCreateRequest(BaseModel):
    """Vollgutschrift zu einer bestehenden Rechnung."""
    credit_reason: str
    invoice_date: Optional[date] = None


class LinkedDocumentInfo(BaseModel):
    id: UUID
    invoice_number: str
    status: InvoiceStatus

    model_config = {"from_attributes": True}


class InvoiceResponse(InvoiceBase):
    id: UUID
    invoice_number: str
    subtotal_net: Decimal
    total_vat: Decimal
    total_gross: Decimal
    pdf_path: Optional[str] = None
    generated_by: Optional[UUID] = None
    generation_run_id: Optional[UUID] = None
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    items: List[InvoiceItemResponse] = []
    # Nur-Lese-Verweise zwischen Rechnung und Gutschrift (im Detailabruf gefüllt)
    credit_note_of_number: Optional[str] = None
    credit_note: Optional[LinkedDocumentInfo] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvoiceGenerateRequest(BaseModel):
    period_from: date
    period_to: date
    contract_ids: Optional[List[UUID]] = None
    auto_issue: bool = False
