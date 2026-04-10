import uuid
import enum
from typing import Optional
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import String, Text, Numeric, Date, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin


class ExpenseReceiptStatus(str, enum.Enum):
    submitted = "submitted"
    approved = "approved"
    paid = "paid"
    rejected = "rejected"


class ExpenseReceipt(Base, TimestampMixin):
    __tablename__ = "expense_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    receipt_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    merchant: Mapped[Optional[str]] = mapped_column(String(255))
    amount_gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    amount_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("19.00"))
    category: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50))
    reimbursement_iban: Mapped[Optional[str]] = mapped_column(String(34))
    reimbursement_account_holder: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[ExpenseReceiptStatus] = mapped_column(
        SAEnum(ExpenseReceiptStatus, name="expensereceiptstatus"),
        nullable=False,
        default=ExpenseReceiptStatus.submitted,
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    document_path: Mapped[Optional[str]] = mapped_column(String(500))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    submitter: Mapped["User"] = relationship(
        "User", foreign_keys=[submitted_by], lazy="select"
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[approved_by], lazy="select"
    )
