import uuid
from typing import Optional
from decimal import Decimal
from datetime import date
from sqlalchemy import String, Boolean, Text, Numeric, Date, Integer, SmallInteger, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin
import enum


class ContractStatus(str, enum.Enum):
    active = "active"
    terminated = "terminated"
    suspended = "suspended"


class BillingPeriod(str, enum.Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
    one_time = "one-time"


class Contract(Base, TimestampMixin):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    property_ref: Mapped[Optional[str]] = mapped_column(String(255))
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    billing_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[ContractStatus] = mapped_column(
        SAEnum(ContractStatus, name="contractstatus"),
        nullable=False,
        default=ContractStatus.active,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="contracts", lazy="select")
    items: Mapped[list["ContractItem"]] = relationship(
        "ContractItem", back_populates="contract", cascade="all, delete-orphan", lazy="select"
    )
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="contract", lazy="select")


class ContractItem(Base, TimestampMixin):
    __tablename__ = "contract_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id"), nullable=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=Decimal("1.000"))
    override_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    override_vat_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    description_override: Mapped[Optional[str]] = mapped_column(String(500))
    billing_period: Mapped[BillingPeriod] = mapped_column(
        SAEnum(BillingPeriod, name="billingperiod"),
        nullable=False,
        default=BillingPeriod.monthly,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_until: Mapped[Optional[date]] = mapped_column(Date)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="items", lazy="select")
    article: Mapped[Optional["Article"]] = relationship("Article", lazy="select")
