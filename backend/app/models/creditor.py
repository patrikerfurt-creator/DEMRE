import uuid
from typing import Optional
from sqlalchemy import String, Boolean, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin


class Creditor(Base, TimestampMixin):
    __tablename__ = "creditors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    creditor_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="DE")
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    iban: Mapped[Optional[str]] = mapped_column(String(34))
    bic: Mapped[Optional[str]] = mapped_column(String(11))
    bank_name: Mapped[Optional[str]] = mapped_column(String(255))
    account_holder: Mapped[Optional[str]] = mapped_column(String(255))
    vat_id: Mapped[Optional[str]] = mapped_column(String(50))
    tax_number: Mapped[Optional[str]] = mapped_column(String(50))
    datev_account_number: Mapped[Optional[str]] = mapped_column(String(20))
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    incoming_invoices: Mapped[list["IncomingInvoice"]] = relationship(
        "IncomingInvoice", back_populates="creditor", lazy="select"
    )
