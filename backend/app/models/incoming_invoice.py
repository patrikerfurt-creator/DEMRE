import uuid
import enum
from typing import Optional
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import String, Text, Numeric, Date, DateTime, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin


class IncomingInvoiceStatus(str, enum.Enum):
    open = "open"
    approved = "approved"
    scheduled = "scheduled"
    paid = "paid"
    rejected = "rejected"
    cancelled = "cancelled"


class IncomingInvoice(Base, TimestampMixin):
    __tablename__ = "incoming_invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    external_invoice_number: Mapped[Optional[str]] = mapped_column(String(100))
    creditor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creditors.id"), nullable=False, index=True
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    receipt_date: Mapped[Optional[date]] = mapped_column(Date)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    total_net: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total_gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    description: Mapped[Optional[str]] = mapped_column(Text)
    cost_account: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[IncomingInvoiceStatus] = mapped_column(
        SAEnum(IncomingInvoiceStatus, name="incominginvoicestatus"),
        nullable=False,
        default=IncomingInvoiceStatus.open,
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    document_path: Mapped[Optional[str]] = mapped_column(String(500))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    # Einzugsermächtigung: True = Lastschrift, wird nicht in SEPA-Überweisung aufgenommen
    is_direct_debit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    creditor: Mapped["Creditor"] = relationship("Creditor", back_populates="incoming_invoices", lazy="select")
    approver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[approved_by], lazy="select"
    )
