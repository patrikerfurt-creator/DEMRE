from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime
from pydantic import BaseModel
from app.models.expense_receipt import ExpenseReceiptStatus


class ExpenseReceiptBase(BaseModel):
    receipt_date: date
    merchant: Optional[str] = None
    amount_gross: Decimal = Decimal("0.00")
    vat_amount: Decimal = Decimal("0.00")
    amount_net: Decimal = Decimal("0.00")
    vat_rate: Decimal = Decimal("19.00")
    category: Optional[str] = None
    description: Optional[str] = None
    payment_method: Optional[str] = None
    reimbursement_iban: Optional[str] = None
    reimbursement_account_holder: Optional[str] = None
    notes: Optional[str] = None


class ExpenseReceiptCreate(ExpenseReceiptBase):
    source_pending_file: Optional[str] = None  # Dateiname aus dem Staging-Ordner
    submitted_by_id: Optional[UUID] = None      # Falls abweichend vom eingeloggten Nutzer


class ExpenseReceiptUpdate(BaseModel):
    receipt_date: Optional[date] = None
    merchant: Optional[str] = None
    amount_gross: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    amount_net: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    category: Optional[str] = None
    description: Optional[str] = None
    payment_method: Optional[str] = None
    reimbursement_iban: Optional[str] = None
    reimbursement_account_holder: Optional[str] = None
    notes: Optional[str] = None


class ExpenseReceiptStatusUpdate(BaseModel):
    status: ExpenseReceiptStatus
    note: Optional[str] = None


class UserShort(BaseModel):
    id: UUID
    full_name: str
    email: str

    model_config = {"from_attributes": True}


class ExpenseReceiptResponse(ExpenseReceiptBase):
    id: UUID
    receipt_number: str
    submitted_by: UUID
    status: ExpenseReceiptStatus
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    document_path: Optional[str] = None
    submitter: Optional[UserShort] = None
    approver: Optional[UserShort] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExpenseReceiptListResponse(BaseModel):
    items: List[ExpenseReceiptResponse]
    total: int
    page: int
    page_size: int
