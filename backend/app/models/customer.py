import uuid
from typing import Optional
import enum
from sqlalchemy import String, Boolean, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin


class CustomerType(str, enum.Enum):
    weg = "weg"
    company = "company"
    person = "person"


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_type: Mapped[str] = mapped_column(String(20), nullable=False, default="weg")
    company_name: Mapped[Optional[str]] = mapped_column(String(255))
    salutation: Mapped[Optional[str]] = mapped_column(String(50))
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="DE")
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    vat_id: Mapped[Optional[str]] = mapped_column(String(50))
    tax_number: Mapped[Optional[str]] = mapped_column(String(50))
    iban: Mapped[Optional[str]] = mapped_column(String(34))
    bic: Mapped[Optional[str]] = mapped_column(String(11))
    bank_name: Mapped[Optional[str]] = mapped_column(String(255))
    account_holder: Mapped[Optional[str]] = mapped_column(String(255))
    sepa_mandate_ref: Mapped[Optional[str]] = mapped_column(String(100))
    sepa_mandate_date: Mapped[Optional[str]] = mapped_column(String(20))
    datev_account_number: Mapped[Optional[str]] = mapped_column(String(20))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    contracts: Mapped[list["Contract"]] = relationship("Contract", back_populates="customer", lazy="select")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="customer", lazy="select")
