import uuid
from typing import Optional
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import String, Text, Numeric, Date, DateTime, Integer, ForeignKey, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
import enum


class RunType(str, enum.Enum):
    invoice_generation = "invoice_generation"
    sepa_export = "sepa_export"
    datev_export = "datev_export"
    creditor_payment = "creditor_payment"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class PaymentRun(Base):
    __tablename__ = "payment_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_type: Mapped[RunType] = mapped_column(
        SAEnum(RunType, name="runtype"), nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(RunStatus, name="runstatus"), nullable=False, default=RunStatus.pending
    )
    triggered_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    period_from: Mapped[Optional[date]] = mapped_column(Date)
    period_to: Mapped[Optional[date]] = mapped_column(Date)
    invoice_count: Mapped[Optional[int]] = mapped_column(Integer)
    total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
